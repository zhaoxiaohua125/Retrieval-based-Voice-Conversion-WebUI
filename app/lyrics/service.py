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

    def load_lrc(self, path: str | Path, offset_ms: int | None = None):
        doc = load_lrc_file(path)
        self.document = doc
        self.matcher.set_document(doc)
        off = int(offset_ms if offset_ms is not None else self._load_cfg().get('offset_ms', 0))
        self.matcher.set_offset_ms(off)
        self._last_index = -1
        self._publish(SignalType.STATUS, {'action': 'lyrics_loaded', 'count': len(doc.lines), 'title': doc.title})
        return doc

    def set_offset_ms(self, offset_ms: int):
        self.matcher.set_offset_ms(int(offset_ms))
        self.config_store.set('lyrics.offset_ms', int(offset_ms))
        self.config_store.save()

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

    def start(self, source: str | None = None):
        self._ensure_hook()
        if self._running:
            return self
        self._build_clock(source)
        if hasattr(self._clock, 'start'):
            self._clock.start()
        self._running = True
        self._worker = threading.Thread(target=self._tick_loop, name='lyrics-sync', daemon=True)
        self.scheduler.register_thread('lyrics-sync', self._worker)
        self._worker.start()
        self._publish(SignalType.STATUS, {'action': 'lyrics_sync_started', 'clock': self._clock_source})
        return self

    def stop(self):
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._worker = None
        self.scheduler.unregister_thread('lyrics-sync')
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
                if hit.index != self._last_index:
                    self._last_index = hit.index
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
