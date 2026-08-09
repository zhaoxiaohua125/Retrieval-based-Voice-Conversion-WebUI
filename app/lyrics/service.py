"""歌词同步服务：LRC + 时钟 + 调度总线。"""

import logging
import threading
import time
import traceback
from pathlib import Path

from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.lyrics.lrc_parser import load_lrc_file
from app.lyrics.matcher import LyricMatcher
from app.lyrics.mtc_reader import MtcPlaybackClock
from app.lyrics.osc_client import ManualPlaybackClock, OscPlaybackClock, SimPlaybackClock
from app.lyrics.types import LyricDocument
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client.lyrics')


class LyricsService:
    """任务 6：解析 LRC、读取 OSC/MTC 时间 T、推送高亮索引。"""

    def __init__(self, scheduler: AppScheduler | None = None, config: ConfigStore | None = None):
        self.scheduler = scheduler or AppScheduler.instance()
        self.config_store = config or ConfigStore().load()
        self.document = LyricDocument()
        self.matcher = LyricMatcher()
        self._clock = ManualPlaybackClock()
        self._clock_source = 'manual'
        self._worker = None
        self._running = False
        self._last_index = -1
        self._last_word = -1
        self._loaded_path = ''
        self._timing_from_file = False
        self._hook_registered = False
        self._tick_handler = None

    def _publish(self, signal: SignalType, payload: dict):
        self.scheduler.publish(BusMessage(signal, ModuleId.LYRICS, payload))

    def _ensure_hook(self):
        if self._hook_registered:
            return
        self.scheduler.add_shutdown_hook(self.stop)
        self._hook_registered = True

    def _load_cfg(self):
        return self.config_store.get('lyrics', {}) or {}

    def load_lrc(self, path: str | Path, offset_ms: int | None = None, force: bool = False, vocal_path: str | Path | None = None):
        resolved = str(Path(path).resolve())
        if not force and resolved == self._loaded_path and self.document.lines:
            return self.document
        doc = load_lrc_file(path)
        from app.lyrics.aligner import normalize_line_words, prepare_word_timing

        # 进歌：已有字级则保留；否则只做 energy/even 快速补齐（Whisper 仅「生成逐字」）
        from_file = bool(doc.has_words)
        if not doc.has_words:
            prepare_word_timing(doc, vocal_path=vocal_path)
        else:
            for ln in doc.lines:
                normalize_line_words(ln)
        self.document = doc
        self._loaded_path = resolved
        self._timing_from_file = from_file
        self.matcher.set_document(doc)
        cfg = self._load_cfg()
        off = int(offset_ms if offset_ms is not None else cfg.get('offset_ms', 0))
        lead = int(cfg.get('lead_ms', 0))
        self.matcher.set_offset_ms(off + lead)
        self._last_index = -1
        self._last_word = -1
        self._publish(
            SignalType.STATUS,
            {
                'action': 'lyrics_loaded',
                'count': len(doc.lines),
                'title': doc.title,
                'has_words': doc.has_words,
                'align_mode': doc.align_mode,
                'timing_from_file': from_file,
            },
        )
        return doc

    def clear(self):
        self.document = LyricDocument()
        self.matcher.set_document(self.document)
        self._loaded_path = ''
        self._timing_from_file = False
        self._last_index = -1
        self._last_word = -1

    def set_offset_ms(self, offset_ms: int):
        self.config_store.set('lyrics.offset_ms', int(offset_ms))
        self.config_store.save()
        lead = int(self._load_cfg().get('lead_ms', 0))
        self.matcher.set_offset_ms(int(offset_ms) + lead)

    @property
    def running(self):
        return self._running

    def set_tick_handler(self, callback):
        """UI 层可选注册：callback(match_dict)。"""
        self._tick_handler = callback

    def _build_clock(self, source: str | None = None):
        cfg = self._load_cfg()
        src = (source or cfg.get('clock_source') or 'manual').lower()
        self._clock_source = src
        if src == 'osc':
            addrs = cfg.get('osc_addresses') or None
            self._clock = OscPlaybackClock(port=int(cfg.get('osc_port', 9000)), addresses=addrs)
        elif src == 'mtc':
            self._clock = MtcPlaybackClock(port_name=str(cfg.get('mtc_port') or ''))
        elif src == 'sim':
            self._clock = SimPlaybackClock(speed=float(cfg.get('sim_speed', 1.0)))
        else:
            self._clock = ManualPlaybackClock()
        return self._clock

    def start(self, source: str | None = None, enable_tick: bool = True):
        self._ensure_hook()
        if self._running:
            if enable_tick and self._worker is None:
                self._worker = threading.Thread(target=self._tick_loop, name='lyrics-sync', daemon=True)
                self.scheduler.register_thread('lyrics-sync', self._worker)
                self._worker.start()
            return self
        self._build_clock(source)
        if hasattr(self._clock, 'start'):
            self._clock.start()
        self._running = True
        if enable_tick:
            self._worker = threading.Thread(target=self._tick_loop, name='lyrics-sync', daemon=True)
            self.scheduler.register_thread('lyrics-sync', self._worker)
            self._worker.start()
        else:
            self._worker = None
        self._publish(SignalType.STATUS, {'action': 'lyrics_sync_started', 'clock': self._clock_source})
        return self

    def sync_at(self, time_sec: float, force: bool = False):
        if not self._running:
            return
        if isinstance(self._clock, ManualPlaybackClock):
            self._clock.set_time(time_sec)
        try:
            hit = self.matcher.match(time_sec)
            if force or hit.index != self._last_index or hit.word_index != self._last_word:
                self._last_index = hit.index
                self._last_word = hit.word_index
                payload = {'action': 'lyric_tick', **hit.to_dict()}
                self._publish(SignalType.STATUS, payload)
                if self._tick_handler:
                    self._tick_handler(payload)
        except Exception:
            logger.error('lyrics sync_at failed:\n%s', traceback.format_exc())

    def tick_at(self, time_sec: float):
        self.sync_at(time_sec, force=False)

    def stop(self):
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._worker = None
        try:
            self.scheduler.unregister_thread('lyrics-sync')
        except Exception:
            pass
        if hasattr(self._clock, 'stop'):
            try:
                self._clock.stop()
            except Exception:
                logger.debug('clock stop: %s', traceback.format_exc())
        self._publish(SignalType.STATUS, {'action': 'lyrics_sync_stopped'})

    def set_manual_time(self, time_sec: float):
        if isinstance(self._clock, ManualPlaybackClock):
            self._clock.set_time(time_sec)

    def _tick_loop(self):
        while self._running:
            try:
                t = self._clock.current_time()
                hit = self.matcher.match(t)
                if hit.index != self._last_index or hit.word_index != self._last_word:
                    self._last_index = hit.index
                    self._last_word = hit.word_index
                    payload = {'action': 'lyric_tick', **hit.to_dict()}
                    self._publish(SignalType.STATUS, payload)
                    if self._tick_handler:
                        self._tick_handler(payload)
            except Exception:
                logger.error('lyrics tick failed:\n%s', traceback.format_exc())
            time.sleep(0.05)

    def attach_scheduler(self):
        def on_status(msg: BusMessage):
            if msg.source == ModuleId.LYRICS:
                return
            action = (msg.payload or {}).get('action')
            if action == 'lyrics_load':
                self.load_lrc((msg.payload or {}).get('path', ''), offset_ms=(msg.payload or {}).get('offset_ms'))
            elif action == 'lyrics_start':
                self.start(source=(msg.payload or {}).get('clock_source'))
            elif action == 'lyrics_stop':
                self.stop()
            elif action == 'lyrics_set_time':
                self.set_manual_time((msg.payload or {}).get('time_sec', 0.0))
            elif action == 'lyrics_set_offset':
                self.set_offset_ms((msg.payload or {}).get('offset_ms', 0))

        self.scheduler.subscribe(SignalType.STATUS, on_status)
        self._ensure_hook()
        return self
