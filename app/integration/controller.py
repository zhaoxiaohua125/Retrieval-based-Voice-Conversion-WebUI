"""任务 7：全模块集成控制器（仅路由与生命周期，不含业务实现）。"""

import logging
import queue
import shutil
import threading
import time
import traceback
from pathlib import Path

from app.audio import AudioService
from app.audio.service import inst_gain_from_config, passthrough_gain_from_audio, pitchfix_mix_from_config
from app.audio.stream_manager import PLAYBACK_MODES
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.integration.state import ClientState
from app.lyrics import LyricsService
from app.playback.waveform_peaks import (
    SILENCE_FLOOR,
    inst_segment_span_at,
    is_vocal_energy_region,
    load_waveform_peaks,
    silence_threshold,
)
from app.ops.exceptions import classify_exception
from app.playback import WavPlayer
from app.playback.library import delete_song_from_disk, find_lrc_in_dir, scan_accompaniment_library, scan_song_library, song_lookup_stem
from app.rvc.types import RvcInferParams
from app.rvc.vc_context import discover_first_model, resolve_index_for_model
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client')
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAY_MODES = ('sequential', 'repeat_one', 'shuffle')
PLAY_MODE_LABELS = {'sequential': '顺序播放', 'repeat_one': '单曲循环', 'shuffle': '随机播放'}
MODE_IDS = ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk')


class ClientController:
    """统一接入 UI 调度消息，串联音频 / 实时 RVC / 离线做歌 / 歌词。"""

    def __init__(self, scheduler: AppScheduler | None = None, project_root=None, config: ConfigStore | None = None):
        self.scheduler = scheduler or AppScheduler.instance()
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.config_store = config or ConfigStore().load()
        self.state = ClientState()
        self.audio = AudioService(self.scheduler, self.config_store)
        self.lyrics = LyricsService(self.scheduler, self.config_store)
        self._realtime = None
        self._pitch_follow = None
        self._bridge = None
        self._lyrics_window = None
        self._offline_thread = None
        self._offline_pipeline = None
        self._player = WavPlayer()
        self._sync_playback_output_device()
        self._playback_tick = None
        self._follow_tick = None
        self._playback_stop = threading.Event()
        self._follow_stop = threading.Event()
        self._follow_prepare_cancel = threading.Event()
        self._follow_prepare_thread = None
        self._follow_handoff = False
        self._mix_save_timer = None
        self._library_sing = []
        self._library_inst = []
        self._started = False
        self._lock = threading.RLock()
        self._tick_generation = 0
        self._track_end_busy = False
        self._inst_end_sent = False
        self._switch_queue = queue.Queue()
        self._switch_worker = threading.Thread(target=self._switch_worker_loop, name='mode-switch', daemon=True)
        self._switch_worker.start()
        self._smart_reverb_active = False
        self._smart_user_override = False
        self._smart_switch_busy = False
        self._smart_peaks = None
        self._smart_peaks_dur = 0.0
        self._smart_peaks_thresh = 0.12
        self._smart_silent_acc = 0.0
        self._smart_vocal_acc = 0.0
        self._update_running = False
        self._active_playback_song_key = ''

    @staticmethod
    def _song_key(song: dict | None) -> str:
        if not song:
            return ''
        return '%s:%s' % (str(song.get('library_type') or 'sing'), str(song.get('id') or song.get('play_path') or ''))

    def _mark_playback_song(self, song: dict | None):
        self._active_playback_song_key = self._song_key(song)

    def _clear_playback_song(self):
        self._active_playback_song_key = ''

    def _playback_matches_selection(self) -> bool:
        song = self.state.selected_song or {}
        key = self._song_key(song)
        if not key:
            return True
        if self._active_playback_song_key:
            return self._active_playback_song_key == key
        play_path = str(song.get('play_path') or song.get('cover_path') or '')
        if self.state.mode == 'ai_sing' and self._player.is_active and self._player.path and play_path:
            try:
                return str(Path(self._player.path).resolve()) == str(Path(play_path).resolve())
            except OSError:
                return False
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            inst = str(song.get('instrumental_path') or song.get('play_path') or '')
            loaded = str(getattr(mgr, '_inst_path', '') or '')
            if inst and loaded:
                try:
                    return str(Path(inst).resolve()) == str(Path(loaded).resolve())
                except OSError:
                    return False
        return False

    def _offline_allows_playback(self, song: dict | None = None) -> bool:
        if not self.state.offline_running:
            return True
        song = dict(song or self.state.selected_song or {})
        if str(song.get('library_type') or '') == 'accompaniment':
            p = song.get('play_path') or song.get('instrumental_path') or ''
            return bool(p and Path(p).is_file())
        for key in ('play_path', 'cover_path', 'vocal_path'):
            p = song.get(key) or ''
            if p and Path(p).is_file():
                return True
        return False

    @property
    def pitch_follow(self):
        if self._pitch_follow is None:
            from app.pitchfix import PitchFollowService
            self._pitch_follow = PitchFollowService(self.scheduler, self.config_store)
        return self._pitch_follow

    @property
    def realtime(self):
        if self._realtime is None:
            from app.rvc.realtime_service import RealtimeRvcService
            self._realtime = RealtimeRvcService(self.scheduler, self.audio, self.config_store, project_root=self.project_root)
        return self._realtime

    def set_ui_bridge(self, bridge):
        self._bridge = bridge

    def set_lyrics_window(self, window):
        self._lyrics_window = window
        self.lyrics.set_tick_handler(lambda payload: window.set_lyric_tick(payload))

    @property
    def library(self):
        return list(self._library_sing)

    @property
    def library_inst(self):
        return list(self._library_inst)

    def start(self):
        if self._started:
            return self
        self.scheduler.subscribe(SignalType.STATUS, self._on_status)
        self.scheduler.subscribe(SignalType.PROGRESS, self._on_progress)
        self.scheduler.subscribe(SignalType.ERROR, self._on_error)
        self.scheduler.add_shutdown_hook(self.shutdown)
        self._started = True
        self._publish_status('controller_ready', log='集成控制器已就绪')
        return self

    def shutdown(self):
        with self._lock:
            self._stop_playback()
            self.stop_passthrough()
            self.stop_realtime()
            self.stop_ai_follow()
            self._cancel_offline(wait=True)
            self.lyrics.stop()
            self._started = False
            self.state.mode = 'idle'

    def _log_ui(self, text: str):
        if self._bridge and text:
            self._bridge.log_message.emit(str(text))

    def _publish_status(self, action: str, **payload):
        body = {'action': action, **payload}
        if payload.get('log'):
            self._log_ui(str(payload['log']))
        self.scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.SCHEDULER, body))

    def _publish_progress(self, **payload):
        msg = payload.get('message') or payload.get('event') or ''
        if msg:
            self._log_ui(str(msg))
        self.scheduler.publish(BusMessage(SignalType.PROGRESS, ModuleId.SCHEDULER, payload))

    def _publish_error(self, detail: str, exc: Exception | None = None):
        self.state.last_error = detail
        kind = classify_exception(exc) if exc else 'runtime'
        self.scheduler.publish(
            BusMessage(
                SignalType.ERROR,
                ModuleId.SCHEDULER,
                {'action': 'client_error', 'category': kind, 'detail': detail},
            )
        )
        self._log_ui('错误: %s' % detail)

    def _on_status(self, msg: BusMessage):
        if msg.source == ModuleId.SCHEDULER:
            return
        action = (msg.payload or {}).get('action')
        if not action:
            return
        handlers = {
            'offline_cover': self._start_offline_cover,
            'offline_cancel': lambda p: self._cancel_offline_user(),
            'playback_refresh_library': lambda p: self._refresh_library(),
            'playback_delete_song': self._delete_song,
            'playback_select_song': self._select_song,
            'playback_select_mode': self._select_mode,
            'playback_transport': self._playback_transport,
            'playback_ai_sing': lambda p: self._select_mode({**(p or {}), 'mode': 'ai_sing'}),
            'playback_toggle_pause': self._playback_transport,
            'playback_stop': self._stop_playback_all,
            'playback_seek': self._seek_playback,
            'playback_ai_follow': lambda p: self.stop_ai_follow() if (p or {}).get('stop') else self._select_mode({**(p or {}), 'mode': 'ai_follow'}),
            'playback_ai_follow_mix': self._update_ai_follow_mix,
            'realtime_start': self._start_realtime_voice,
            'realtime_stop': self.stop_realtime,
            'playback_normal_talk': lambda p: self._select_mode({**(p or {}), 'mode': 'normal_talk'}),
            'playback_reverb_talk': lambda p: self._select_mode({**(p or {}), 'mode': 'reverb_talk'}),
            'playback_set_play_mode': self._set_play_mode,
            'ai_toggle': self._toggle_ai,
            'lyrics_load': self._load_lyrics,
            'lyrics_start': lambda p: self.lyrics.start(source=(p or {}).get('clock_source')),
            'lyrics_stop': lambda p: self.lyrics.stop(),
            'lyrics_set_offset': lambda p: self.lyrics.set_offset_ms(int((p or {}).get('offset_ms', 0))),
            'lyrics_enhance': self._enhance_lyrics,
            'lyrics_rewrite': self._rewrite_lyrics,
            'check_update': self._check_update,
            'apply_update': self._apply_update,
            'skip_update': self._skip_update,
            'settings_save': self._save_settings,
            'audio_test_mic': self._test_mic,
        }
        handler = handlers.get(action)
        if handler is None:
            return
        try:
            handler(msg.payload or {})
        except Exception as exc:
            logger.error('handle %s failed:\n%s', action, traceback.format_exc())
            self._publish_error('%s: %s' % (action, exc), exc)

    def _on_progress(self, msg: BusMessage):
        payload = msg.payload or {}
        text = payload.get('message') or payload.get('event')
        if text:
            self._log_ui(str(text))

    def _on_error(self, msg: BusMessage):
        detail = (msg.payload or {}).get('detail') or (msg.payload or {}).get('message') or 'unknown'
        self._log_ui('错误: %s' % detail)

    def _is_talk_mode(self) -> bool:
        return self.state.mode in ('normal_talk', 'reverb_talk')

    def snapshot_playback(self) -> dict | None:
        if self.state.mode == 'idle' and not self.state.playback_running and not self.state.passthrough_running:
            if not self.state.ai_follow_running:
                return None
        return {
            'mode': self.state.mode,
            'position': self._current_song_position(),
            'playback_running': self.state.playback_running,
            'passthrough_running': self.state.passthrough_running,
            'ai_follow_running': self.state.ai_follow_running,
        }

    def restore_playback_after_settings(self, snap: dict | None):
        if not snap:
            return
        if self._unified_stream_active():
            mgr = self._unified_mgr()
            if mgr is not None:
                mix = pitchfix_mix_from_config(self.config_store)
                audio_cfg = dict(self.config_store.get('audio', {}) or {})
                if mgr.config.passthrough:
                    mgr.config.passthrough_gain = passthrough_gain_from_audio(audio_cfg)
                mgr.config.reverb_mix = float(audio_cfg.get('reverb_mix', 0.35))
                mgr.config.reverb_decay = float(audio_cfg.get('reverb_decay', 0.72))
                mgr.config.inst_gain = inst_gain_from_config(self.config_store)
                mgr.config.mic_gain = mix['mic_gain']
                mgr.config.ref_vocal_gain = mix['ref_vocal_gain']
                mgr.config.follow_threshold = mix['follow_threshold']
                mgr.config.follow_attenuation = mix['follow_attenuation']
            return
        pos = float(snap.get('position', 0) or 0)
        mode = snap.get('mode')
        if snap.get('ai_follow_running') and not (self._pitch_follow and self._pitch_follow.running):
            song = self.state.selected_song or {}
            if song.get('instrumental_path') and song.get('vocal_path'):
                try:
                    self.pitch_follow.start(song, seek_sec=pos)
                    self.state.ai_follow_running = True
                    self.state.mode = 'ai_follow'
                    self.state.playback_running = True
                    self._ensure_playback_lyrics(pos)
                    if not self._follow_tick or not self._follow_tick.is_alive():
                        self._follow_stop.clear()
                        self._follow_tick = threading.Thread(target=self._follow_tick_loop, name='ai-follow-tick', daemon=True)
                        self.scheduler.register_thread('ai-follow-tick', self._follow_tick)
                        self._follow_tick.start()
                    logger.info('playback resumed after settings: ai_follow pos=%.2fs', pos)
                except Exception as exc:
                    logger.warning('resume ai_follow after settings failed: %s', exc)
            return
        if mode == 'ai_sing' and snap.get('playback_running') and not self._player.is_active:
            try:
                dur = self._player.duration
                if dur > 0 and pos > 0:
                    self._player.seek_ratio(pos / dur)
                if not self._player.play(on_finish=self._on_playback_finished):
                    raise RuntimeError('player not started')
                self.state.playback_running = True
                self.state.mode = 'ai_sing'
                self._restart_playback_tick()
                logger.info('playback resumed after settings: ai_sing pos=%.2fs', pos)
            except Exception as exc:
                logger.warning('resume ai_sing after settings failed: %s', exc)
            return
        if snap.get('passthrough_running') and mode in ('reverb_talk', 'normal_talk'):
            if self.audio.manager and self.audio.manager.running:
                return
            song = self.state.selected_song or {}
            inst = song.get('instrumental_path') or ''
            if inst and not Path(inst).is_file():
                inst = ''
            try:
                self.audio.start_stream(
                    passthrough=True,
                    reverb=(mode == 'reverb_talk'),
                    inst_path=inst or None,
                    inst_seek=pos,
                )
                self.state.mode = mode
                self.state.passthrough_running = True
                if inst:
                    self.state.playback_running = True
                    self._ensure_playback_lyrics(pos)
                    self._restart_playback_tick()
                logger.info('playback resumed after settings: %s pos=%.2fs', mode, pos)
            except Exception as exc:
                logger.warning('resume talk after settings failed: %s', exc)

    def _switch_worker_loop(self):
        while True:
            fn, args, kwargs = self._switch_queue.get()
            name = getattr(fn, '__name__', str(fn))
            logger.info('mode switch begin: %s mode=%s passthrough=%s playback=%s', name, self.state.mode, self.state.passthrough_running, self.state.playback_running)
            try:
                fn(*args, **kwargs)
                logger.info('mode switch done: %s mode=%s player_active=%s', name, self.state.mode, self._player.is_active)
                if name == '_continue_mode_with_song_impl':
                    song = args[1] if len(args) > 1 else {}
                    self._publish_status('song_switched', title=(song or {}).get('title', ''))
            except Exception:
                logger.error('mode switch failed (%s):\n%s', name, traceback.format_exc())
                if name == '_continue_mode_with_song_impl':
                    self._publish_status('song_switched', title='')
            finally:
                self._switch_queue.task_done()

    def _dispatch_mode_switch(self, fn, *args, **kwargs):
        while not self._switch_queue.empty():
            try:
                self._switch_queue.get_nowait()
                self._switch_queue.task_done()
            except queue.Empty:
                break
        self._switch_queue.put((fn, args, kwargs))

    def _halt_playback_tick(self, wait: float = 0.4):
        self._tick_generation += 1
        self._playback_stop.set()
        tick = self._playback_tick
        self._playback_tick = None
        if tick is not None and tick.is_alive() and threading.current_thread() is not tick:
            tick.join(timeout=wait)
        try:
            self.scheduler.unregister_thread('playback-tick')
        except Exception:
            pass

    def _begin_playback_tick(self):
        self._playback_stop.clear()
        gen = self._tick_generation
        self._playback_tick = threading.Thread(
            target=self._playback_tick_loop, args=(gen,), name='playback-tick', daemon=True
        )
        self.scheduler.register_thread('playback-tick', self._playback_tick)
        self._playback_tick.start()

    def _restart_playback_tick(self):
        self._halt_playback_tick(wait=0.25)
        self._playback_stop.clear()
        gen = self._tick_generation
        self._playback_tick = threading.Thread(
            target=self._playback_tick_loop, args=(gen,), name='playback-tick', daemon=True
        )
        self.scheduler.register_thread('playback-tick', self._playback_tick)
        self._playback_tick.start()

    def _reset_smart_switch(self):
        self._smart_reverb_active = False
        self._smart_user_override = False
        self._smart_switch_busy = False
        self._smart_silent_acc = 0.0
        self._smart_vocal_acc = 0.0

    def _load_smart_vocal_peaks(self, path: str):
        path = str(path or '')
        if not path or not Path(path).is_file():
            self._smart_peaks = None
            self._smart_peaks_dur = 0.0
            self._smart_peaks_thresh = 0.12
            return
        try:
            peaks, dur = load_waveform_peaks(path)
        except Exception as exc:
            logger.warning('smart_switch vocal peaks failed: %s', exc)
            self._smart_peaks = None
            self._smart_peaks_dur = 0.0
            self._smart_peaks_thresh = 0.12
            return
        song = self.state.selected_song or {}
        if str(song.get('vocal_path') or '') != path:
            return
        self._smart_peaks = peaks
        self._smart_peaks_dur = float(dur or 0.0)
        self._smart_peaks_thresh = silence_threshold(peaks, SILENCE_FLOOR)
        logger.info(
            'smart_switch peaks ready dur=%.1fs thresh=%.3f path=%s',
            self._smart_peaks_dur,
            self._smart_peaks_thresh,
            Path(path).name,
        )

    def _schedule_smart_peaks(self, song: dict):
        path = str((song or {}).get('vocal_path') or '')
        self._smart_peaks = None
        self._smart_peaks_dur = 0.0
        self._smart_peaks_thresh = 0.12
        self._smart_silent_acc = 0.0
        self._smart_vocal_acc = 0.0
        if not path:
            return
        threading.Thread(
            target=self._load_smart_vocal_peaks,
            args=(path,),
            name='smart-vocal-peaks',
            daemon=True,
        ).start()

    def _smart_switch_enabled(self) -> bool:
        return bool(self.config_store.get('playback.smart_switch', False))

    def _playback_tick_extra(self) -> dict:
        if self._smart_reverb_active and self.state.selected_mode in ('ai_sing', 'ai_follow'):
            return {'smart_overlay': True, 'base_mode': self.state.selected_mode}
        return {}

    def _maybe_smart_switch(self, pos: float, playing: bool, paused: bool = False):
        if self._smart_switch_busy or paused or not playing:
            return
        if not self._smart_switch_enabled() or self._smart_user_override:
            return
        base = self.state.selected_mode
        if base not in ('ai_sing', 'ai_follow'):
            return
        if self._smart_peaks is None or self._smart_peaks_dur <= 0:
            return
        min_hold = float(self.config_store.get('playback.smart_switch_min_gap_sec', 3.0) or 3.0)
        vocal_hold = min(0.25, max(0.12, min_hold * 0.08))
        thresh = self._smart_peaks_thresh
        in_vocal = is_vocal_energy_region(pos, self._smart_peaks, self._smart_peaks_dur, thresh)
        if self._smart_reverb_active:
            if self.state.mode != 'reverb_talk':
                return
            if not in_vocal:
                ahead = min(pos + 0.25, max(0.0, self._smart_peaks_dur - 0.01))
                in_vocal = is_vocal_energy_region(ahead, self._smart_peaks, self._smart_peaks_dur, thresh)
            if in_vocal:
                self._smart_vocal_acc += 0.03
            else:
                self._smart_vocal_acc = 0.0
            if self._smart_vocal_acc >= vocal_hold:
                self._smart_switch_busy = True
                self._smart_vocal_acc = 0.0
                logger.info('smart_switch -> vocal pos=%.2fs base=%s', pos, base)
                self._dispatch_mode_switch(self._smart_switch_to_vocal, float(pos))
            return
        if self.state.mode not in ('ai_sing', 'ai_follow') or not self._is_timeline_playing():
            return
        if in_vocal:
            self._smart_silent_acc = 0.0
        else:
            span = inst_segment_span_at(pos, self._smart_peaks, self._smart_peaks_dur, thresh)
            seg_len = (span[1] - span[0]) if span else 0.0
            if seg_len >= min_hold:
                self._smart_silent_acc += 0.03
            else:
                self._smart_silent_acc = 0.0
        if not in_vocal and self._smart_silent_acc >= min_hold:
            self._smart_switch_busy = True
            self._smart_silent_acc = 0.0
            self._smart_reverb_active = True
            logger.info('smart_switch -> reverb pos=%.2fs mode=%s', pos, base)
            self._dispatch_mode_switch(self._smart_switch_to_reverb, float(pos))

    def _smart_switch_to_reverb(self, pos: float):
        try:
            song = dict(self.state.selected_song or {})
            if not self._switch_unified_playback('reverb_talk', song, float(pos), True, quiet=True):
                self._start_talk({'song': song, 'position': float(pos), 'autoplay': True}, mode='reverb_talk')
        finally:
            self._smart_switch_busy = False

    def _smart_switch_to_vocal(self, pos: float):
        try:
            mode = self.state.selected_mode if self.state.selected_mode in ('ai_sing', 'ai_follow') else 'ai_sing'
            song = dict(self.state.selected_song or {})
            if not self._switch_unified_playback(mode, song, float(pos), True, quiet=True):
                self._continue_mode_with_song_impl(mode, song, float(pos), True)
            self._smart_reverb_active = False
            self._smart_vocal_acc = 0.0
        finally:
            self._smart_switch_busy = False

    def _unified_mgr(self):
        mgr = self.audio.manager
        if mgr is None or not mgr.running or mgr.config.playback_mode not in PLAYBACK_MODES:
            return None
        return mgr

    def _unified_stream_active(self) -> bool:
        return self._unified_mgr() is not None

    def _song_unified_ready(self, song: dict, mode: str) -> bool:
        if mode not in PLAYBACK_MODES:
            return False
        if mode in ('ai_sing', 'ai_follow'):
            inst = song.get('instrumental_path') or ''
            vocal = song.get('vocal_path') or ''
            return bool(inst and Path(inst).is_file() and vocal and Path(vocal).is_file())
        return True

    def _timeline_inst_state(self):
        mgr = self._unified_mgr()
        if mgr is None or mgr.inst_duration <= 0:
            return 0.0, 0.0, False, False
        pos = mgr.inst_position
        dur = mgr.inst_duration
        playing = mgr.inst_playing and not mgr.inst_paused
        paused = mgr.inst_paused and mgr.inst_playing
        return pos, dur, playing, paused

    _reverb_inst_state = _timeline_inst_state

    def _switch_unified_playback(self, mode: str, song: dict, carry_pos: float | None = None, autoplay: bool = True, quiet: bool = False) -> bool:
        song = dict(song or {})
        if not self._song_unified_ready(song, mode):
            return False
        if self._player.is_active:
            self._player.stop()
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            self._release_ai_follow(handoff=True)
        inst_path = song.get('instrumental_path') or ''
        vocal_path = song.get('vocal_path') or ''
        pos = self._current_song_position() if carry_pos is None else max(0.0, float(carry_pos))
        mgr_was = self._unified_stream_active()
        tick_alive = self._playback_tick is not None and self._playback_tick.is_alive()
        try:
            self.audio.switch_playback_mode(
                mode,
                inst_path=inst_path or None,
                vocal_path=vocal_path or None,
                inst_seek=pos,
                reverb=(mode == 'reverb_talk'),
            )
        except Exception as exc:
            self._publish_error('播放切换失败: %s' % exc, exc)
            return False
        mgr = self.audio.manager
        if mgr is None:
            return False
        if not autoplay and mgr.inst_duration > 0 and not mgr.inst_paused:
            mgr.toggle_inst_pause()
        self.state.mode = mode
        self.state.passthrough_running = mode in ('reverb_talk', 'normal_talk')
        self.state.ai_follow_running = mode == 'ai_follow' and autoplay
        self.state.ai_follow_preparing = False
        self.state.playback_running = autoplay or (mgr.inst_duration > 0 and mgr.inst_paused)
        pos, dur, playing, paused = self._timeline_inst_state()
        if pos <= 0.15:
            sync_lyrics = self._reset_playback_lyrics
        else:
            sync_lyrics = self._ensure_playback_lyrics
        if not mgr_was or not tick_alive:
            self._inst_end_sent = False
            sync_lyrics(pos)
            self._restart_playback_tick()
        else:
            sync_lyrics(pos)
        if not quiet:
            self._publish_status('playback_tick', position=pos, duration=dur, playing=playing, paused=paused)
        else:
            self._publish_status(
                'smart_switch_tick',
                position=pos,
                duration=dur,
                playing=playing,
                paused=paused,
                overlay_mode=mode,
                base_mode=self.state.selected_mode,
                smart_overlay=(mode == 'reverb_talk' and self.state.selected_mode in ('ai_sing', 'ai_follow')),
            )
        self._mark_playback_song(song)
        return True

    def _toggle_reverb_talk(self, payload=None):
        if self.state.mode == 'reverb_talk':
            self.stop_passthrough()
            return
        self._dispatch_mode_switch(self._start_talk, self._with_autoplay(payload), mode='reverb_talk')

    def _toggle_normal_talk(self, payload=None):
        if self.state.mode == 'normal_talk':
            self.stop_passthrough()
            return
        self._dispatch_mode_switch(self._start_talk, self._with_autoplay(payload), mode='normal_talk')

    def _start_talk(self, payload=None, mode: str = 'normal_talk'):
        label = '混响说话' if mode == 'reverb_talk' else '普通说话'
        payload = payload or {}
        autoplay = bool(payload.get('autoplay', True))
        if 'position' in payload:
            carry_pos = float(payload.get('position') or 0)
        else:
            carry_pos = self._current_song_position()
        song = self.state.selected_song or {}
        inst_path = song.get('instrumental_path') or ''
        if inst_path and not Path(inst_path).is_file():
            inst_path = ''
        if self.state.realtime_running:
            self.stop_realtime()
        if self.state.offline_running:
            self._publish_status('passthrough_blocked', log='离线做歌进行中，请稍后再试')
            return
        audio_cfg = self.config_store.get('audio', {}) or {}
        from app.audio.devices import resolve_io_devices
        in_dev, out_dev = resolve_io_devices(
            audio_cfg.get('input_device'),
            audio_cfg.get('output_device'),
            hostapi=audio_cfg.get('hostapi'),
        )
        if in_dev is None or out_dev is None:
            self._publish_error('未找到可用音频输入/输出设备，请检查 Voicemeeter 是否已启动')
            self._publish_status('passthrough_blocked', log='%s：未找到音频设备' % label)
            return
        hot = self._unified_stream_active()
        if self._switch_unified_playback(mode, song, carry_pos, autoplay):
            in_dev = self.audio.manager.config.input_device if self.audio.manager else in_dev
            out_dev = self.audio.manager.config.output_device if self.audio.manager else out_dev
            gain = passthrough_gain_from_audio(audio_cfg)
            pos, dur, playing, paused = self._timeline_inst_state()
            has_inst = bool(inst_path)
            if hot:
                log = '已切换为%s' % label
            else:
                inst_hint = '\n伴奏：%s（四模式无缝互切）' % Path(inst_path).name if has_inst else (
                    '\n未找到伴奏轨，仅麦克风' if mode == 'reverb_talk' else '\n未找到伴奏轨，仅干声'
                )
                extra = '\n已叠加房间混响（可调 audio.reverb_mix / reverb_decay）' if mode == 'reverb_talk' else ''
                talk_mode_desc = {
                    'reverb_talk': '伴奏+混响麦' if has_inst else '干声+混响直通',
                    'normal_talk': '伴奏+干声麦' if has_inst else '干声直通已启动（不经 RVC）',
                }
                log = '%s：%s\nIN: %s\nOUT: %s\n监听增益: %.1fx（设置里 %s%%）%s%s' % (
                    label,
                    talk_mode_desc.get(mode, ''),
                    self._device_name(in_dev),
                    self._device_name(out_dev),
                    gain,
                    int(gain * 50),
                    extra,
                    inst_hint,
                )
            self._publish_status(
                'passthrough_started',
                mode=mode,
                input_device=in_dev,
                output_device=out_dev,
                position=pos if has_inst else 0.0,
                duration=dur if has_inst else 0.0,
                playing=playing if has_inst else False,
                paused=paused if has_inst else False,
                log=log,
            )
            return
        self._publish_status('passthrough_blocked', log='%s启动失败' % label)

    def stop_passthrough(self, payload=None, handoff: bool = False):
        if not self.state.passthrough_running and not (self.audio.manager and self.audio.manager.running):
            return
        if handoff:
            self.state.passthrough_running = False
            return
        was_reverb = self.state.mode == 'reverb_talk'
        was_talk = self.state.mode in ('reverb_talk', 'normal_talk')
        label = '混响说话' if was_reverb else '普通说话'
        had_timeline = self.state.playback_running and was_talk
        if had_timeline:
            self._halt_playback_tick(wait=0.4)
        self.audio.stop_stream()
        time.sleep(0.03)
        self.state.passthrough_running = False
        if had_timeline:
            self.state.playback_running = False
            if self.state.lyrics_running:
                self.lyrics.stop()
                self.state.lyrics_running = False
        if self._is_talk_mode():
            self.state.mode = 'idle'
        self._clear_playback_song()
        self._publish_status('passthrough_stopped', log='%s已停止' % label)

    def _stop_playback_all(self, payload=None):
        if self._unified_stream_active():
            self._stop_playback()
            return
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            self.stop_ai_follow()
        if self._is_talk_mode():
            self.stop_passthrough()
        self._stop_playback(payload)

    def _scan_library_blocking(self):
        opt_dir = self.config_store.get('paths.opt_dir', 'opt')
        dirs = [opt_dir, str(Path(opt_dir) / 'task4_offline')]
        self._library_sing = scan_song_library(self.project_root, dirs=dirs)
        self._library_inst = scan_accompaniment_library(self.project_root, opt_dir=opt_dir)

    def _publish_library(self, log: str = ''):
        body = {
            'sing_songs': self._library_sing,
            'inst_songs': self._library_inst,
            'songs': self._library_sing,
        }
        if log:
            body['log'] = log
        self._publish_status('library_updated', **body)

    def _refresh_library(self):
        def _work():
            try:
                self._scan_library_blocking()
                self._publish_library(
                    log='歌库已刷新（唱歌 %s / 原唱 %s）' % (len(self._library_sing), len(self._library_inst))
                )
            except Exception:
                logger.error('library refresh failed:\n%s', traceback.format_exc())
        threading.Thread(target=_work, name='library-scan', daemon=True).start()

    def _delete_song(self, payload: dict = None):
        payload = payload or {}
        song = payload.get('song') or {}
        if not song.get('dir') and not song.get('play_path'):
            self._publish_error('无法删除：无效歌曲')
            return
        title = song.get('title') or Path(song.get('play_path') or '').stem or '未命名'
        cur = self.state.selected_song or {}
        cur_id = cur.get('id') or cur.get('play_path')
        del_id = song.get('id') or song.get('play_path')
        if cur_id and del_id and cur_id == del_id:
            self._stop_playback_all({})
            self.stop_ai_follow()
            if self._is_talk_mode():
                self.stop_passthrough()
        deleted = delete_song_from_disk(song, project_root=self.project_root)
        if not deleted:
            self._publish_error('删除失败：未找到可删文件')
            return
        if cur_id and del_id and cur_id == del_id:
            self.state.selected_song = None
            self.state.playback_running = False
            self.lyrics.clear()
            self.state.loaded_lyrics = False
            self._publish_status('lyrics_loaded', lines=[])
            self._publish_status('playback_stopped', log='当前歌曲已删除')
        self._scan_library_blocking()
        self._publish_library(log='已删除「%s」（%s 个文件）' % (title, len(deleted)))
        if cur_id and del_id and cur_id == del_id:
            self._publish_status('song_deleted', title=title)

    def _is_timeline_playing(self) -> bool:
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            return mgr.inst_playing and not mgr.inst_paused
        if self.state.ai_follow_running:
            pf = self._pitch_follow
            return pf is not None and pf.running
        if self.state.mode == 'ai_sing':
            return self._player.is_playing
        return False

    def _has_paused_session(self) -> bool:
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            return mgr.inst_paused and mgr.inst_playing
        if self.state.mode == 'ai_sing' and self._player.is_active:
            return not self._player.is_playing
        return False

    def _with_autoplay(self, payload=None) -> dict:
        p = dict(payload or {})
        if 'autoplay' not in p:
            p['autoplay'] = self._is_timeline_playing()
        return p

    def _apply_mode(self, mode: str, autoplay: bool = True, song: dict | None = None):
        if mode not in MODE_IDS:
            return
        song = dict(song or self.state.selected_song or {})
        if mode == 'ai_sing' and not song.get('play_path'):
            self._publish_status('playback_idle', log='请先在歌库选择歌曲')
            return
        if mode == 'ai_follow' and (not song.get('instrumental_path') or not song.get('vocal_path')):
            self._publish_error('AI 跟唱需要 instrumental.wav 与 converted_vocal.wav')
            return
        if mode == 'ai_follow' and str(song.get('library_type') or '') == 'accompaniment':
            self._publish_error('原唱条目不支持 AI 跟唱')
            return
        carry = self._current_song_position() if self._is_timeline_playing() or self._has_paused_session() else 0.0
        payload = {'song': song, 'position': carry, 'autoplay': autoplay}
        if mode == 'ai_sing':
            self._dispatch_mode_switch(self._start_ai_sing_impl, payload)
        elif mode == 'ai_follow':
            self._dispatch_mode_switch(self._start_ai_follow, payload)
        else:
            self._dispatch_mode_switch(self._start_talk, payload, mode=mode)

    def _select_mode(self, payload=None):
        payload = payload or {}
        mode = str(payload.get('mode') or '')
        if mode not in MODE_IDS:
            return
        song = payload.get('song') or self.state.selected_song or {}
        if mode == 'ai_sing' and not song.get('play_path'):
            self._publish_status('playback_idle', log='请先在歌库选择歌曲')
            return
        self.state.selected_mode = mode
        if mode in ('reverb_talk', 'normal_talk'):
            self._smart_user_override = True
            self._smart_reverb_active = False
            self._smart_silent_acc = 0.0
            self._smart_vocal_acc = 0.0
        elif mode in ('ai_sing', 'ai_follow'):
            self._smart_user_override = False
            self._smart_reverb_active = False
            self._smart_silent_acc = 0.0
            self._smart_vocal_acc = 0.0
        self._publish_status('mode_selected', mode=mode)
        if self._is_timeline_playing() and mode == self.state.mode:
            return
        if self._has_paused_session() and mode == self.state.mode:
            return
        if self._is_timeline_playing():
            self._apply_mode(mode, autoplay=True, song=song)
        elif self._has_paused_session():
            self._apply_mode(mode, autoplay=False, song=song)

    def _pause_timeline(self):
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            if mgr.inst_paused:
                return
            mgr.toggle_inst_pause()
            pos, dur, playing, paused = self._timeline_inst_state()
            self.state.playback_running = playing
            self._publish_status('playback_paused', playing=playing, paused=paused, position=pos, duration=dur)
            self._publish_status('playback_tick', position=pos, duration=dur, playing=playing, paused=paused)
            return
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            self.stop_ai_follow()
            self._publish_status('playback_paused', playing=False, paused=True)
            return
        if self.state.mode == 'ai_sing' and self._player.is_playing:
            self._player.pause()
            self._publish_status(
                'playback_paused',
                playing=False,
                paused=True,
                position=self._player.position,
                duration=self._player.duration,
            )
            self._publish_status(
                'playback_tick',
                position=self._player.position,
                duration=self._player.duration,
                playing=False,
                paused=True,
            )

    def _resume_timeline(self):
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            if not mgr.inst_paused:
                return
            mgr.toggle_inst_pause()
            pos, dur, playing, paused = self._timeline_inst_state()
            self.state.playback_running = playing
            self._publish_status('playback_resumed', playing=playing, paused=paused, position=pos, duration=dur)
            self._publish_status('playback_tick', position=pos, duration=dur, playing=playing, paused=paused)
            return
        if self.state.mode == 'ai_sing' and self._player.is_active and not self._player.is_playing:
            if self._player.play(on_finish=self._on_playback_finished):
                self.state.playback_running = True
                self._restart_playback_tick()
                pos = self._player.position
                self._publish_status(
                    'playback_resumed',
                    playing=True,
                    paused=False,
                    position=pos,
                    duration=self._player.duration,
                )
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=self._player.duration,
                    playing=True,
                    paused=False,
                )
            return
        if self.state.mode == 'ai_follow' and not self.state.ai_follow_running:
            self._apply_mode('ai_follow', autoplay=True)

    def _playback_transport(self, payload=None):
        if self._is_timeline_playing():
            self._pause_timeline()
            return
        if self._has_paused_session():
            if not self._playback_matches_selection():
                self._release_playback_source(handoff=False)
                self._clear_playback_song()
                mode = self.state.selected_mode if self.state.selected_mode in MODE_IDS else 'ai_sing'
                self._apply_mode(mode, autoplay=True, song=self.state.selected_song)
                return
            self._resume_timeline()
            return
        mode = self.state.selected_mode if self.state.selected_mode in MODE_IDS else 'ai_sing'
        self._apply_mode(mode, autoplay=True)

    def _session_playback_mode(self) -> str:
        """当前播放会话模式（含暂停/智能混响覆盖），用于切歌。"""
        mgr = self._unified_mgr()
        if mgr is not None:
            if mgr.inst_duration > 0 and mgr.inst_playing:
                return mgr.config.playback_mode
            if mgr.config.playback_mode in ('reverb_talk', 'normal_talk') and self.state.passthrough_running:
                return mgr.config.playback_mode
        pf = self._pitch_follow
        if self.state.ai_follow_running or self.state.ai_follow_preparing or (pf is not None and pf.running):
            return 'ai_follow'
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.state.passthrough_running:
            return self.state.mode
        if self.state.mode == 'ai_sing' and self._player.is_active:
            return 'ai_sing'
        if self.state.playback_running and self.state.mode in PLAYBACK_MODES:
            return self.state.mode
        return ''

    def _active_playback_mode(self) -> str:
        if not self._is_timeline_playing():
            return ''
        return self._session_playback_mode()

    def _select_song(self, payload: dict):
        payload = payload or {}
        song = payload.get('song') or payload or {}
        if not song.get('play_path'):
            return
        prev = self.state.selected_song or {}
        prev_id = prev.get('id') or prev.get('play_path')
        new_id = song.get('id') or song.get('play_path')
        prev_lib = str(prev.get('library_type') or '')
        new_lib = str(song.get('library_type') or '')
        lib_changed = bool(prev_id and prev_lib != new_lib)
        switching = bool(prev_id and new_id and (prev_id != new_id or lib_changed))
        force_switch = bool(payload.get('force_switch')) or lib_changed
        if switching:
            self._reset_smart_switch()
        self.state.selected_song = dict(song)
        defer = lib_changed and (switching or force_switch)
        if defer:
            threading.Thread(
                target=self._select_song_apply,
                args=(dict(song), dict(payload), switching, lib_changed, force_switch),
                name='select-song',
                daemon=True,
            ).start()
        else:
            self._select_song_apply(song, payload, switching, lib_changed, force_switch)

    def _select_song_apply(self, song: dict, payload: dict, switching: bool, lib_changed: bool, force_switch: bool):
        resume_if_playing = payload.get('resume_if_playing', True)
        user_autoplay = bool(payload.get('autoplay'))
        self._schedule_smart_peaks(song)
        lrc = song.get('lrc_path') or find_lrc_in_dir(
            song.get('dir') or Path(song.get('play_path', '')).parent,
            song_lookup_stem(song),
        )
        if lrc and Path(lrc).is_file():
            prev_lrc = self.lyrics._loaded_path
            from app.lyrics.aligner import find_vocal_for_song, refresh_karaoke_timing

            vocal = find_vocal_for_song(song.get('dir') or Path(lrc).parent, song_lookup_stem(song), song)
            is_accomp = str(song.get('library_type') or '') == 'accompaniment'
            self.lyrics.load_lrc(lrc, vocal_path=None if is_accomp else vocal, force=True)
            if is_accomp and vocal and Path(vocal).is_file():
                doc = refresh_karaoke_timing(self.lyrics.document, vocal_path=vocal)
                self.lyrics.document = doc
                self.lyrics.matcher.set_document(doc)
                self.lyrics._timing_from_file = False
            self.state.loaded_lyrics = True
            self.state.selected_song['lrc_path'] = lrc
            if switching or self.lyrics._loaded_path != prev_lrc:
                doc = self.lyrics.document
                from app.lyrics.aligner import word_timing_label

                engine = str(self.config_store.get('lyrics.align_engine', 'energy') or 'energy').strip().lower()
                suffix = word_timing_label(
                    doc.align_mode,
                    has_words=doc.has_words,
                    from_file=bool(getattr(self.lyrics, '_timing_from_file', False)),
                    config_engine=engine,
                )
                self._publish_status(
                    'lyrics_loaded',
                    lines=[ln.text for ln in doc.lines],
                    has_words=doc.has_words,
                    align_mode=doc.align_mode,
                    log='已加载歌词：%s（%s 行%s）'
                    % (doc.title or song.get('title', ''), len(doc.lines), suffix),
                )
        else:
            self.lyrics.clear()
            self.state.loaded_lyrics = False
            hint = Path(lrc).name if lrc else '%s.lrc' % song.get('title', '')
            self._publish_status(
                'lyrics_loaded',
                lines=[],
                log='未找到歌词文件（期望同名 %s），仅播放音频' % hint,
            )
        if lib_changed:
            was_active = self._is_timeline_playing() or self._has_paused_session()
            if was_active or user_autoplay:
                if was_active and self._unified_stream_active() and not self._song_unified_ready(song, 'ai_sing'):
                    self._release_playback_source(handoff=False)
                    time.sleep(0.03)
                mode = self._session_playback_mode()
                if not mode:
                    mode = self.state.selected_mode if self.state.selected_mode in MODE_IDS else 'ai_sing'
                new_lib = str(song.get('library_type') or '')
                if new_lib == 'accompaniment' and mode == 'ai_follow':
                    mode = 'ai_sing'
                elif new_lib != 'accompaniment' and mode in ('reverb_talk', 'normal_talk'):
                    mode = 'ai_sing'
                title = song.get('title') or Path(song.get('play_path') or '').stem
                self._inst_end_sent = False
                autoplay = was_active or user_autoplay
                self._continue_mode_with_song(mode, dict(self.state.selected_song), 0.0, autoplay)
                self._publish_status('track_advance', title=title, log='切换歌曲：%s' % title)
                return
            try:
                self._preload_song_assets(dict(self.state.selected_song))
            finally:
                title = (self.state.selected_song or {}).get('title') or ''
                self._publish_status('song_switched', title=title)
            return
        if switching and (resume_if_playing or force_switch):
            mode = self._session_playback_mode()
            if not mode:
                mode = self.state.selected_mode if self.state.selected_mode in MODE_IDS else 'ai_sing'
            was_active = self._is_timeline_playing() or self._has_paused_session()
            if was_active or user_autoplay:
                song_now = dict(self.state.selected_song)
                if was_active and self._unified_stream_active() and not self._song_unified_ready(song_now, mode):
                    self._release_playback_source(handoff=False)
                    time.sleep(0.03)
                title = song.get('title') or Path(song.get('play_path') or '').stem
                self._inst_end_sent = False
                autoplay = was_active or user_autoplay
                self._continue_mode_with_song(mode, dict(self.state.selected_song), 0.0, autoplay)
                self._publish_status('track_advance', title=title, log='切换歌曲：%s' % title)
                return
            if force_switch:
                self._release_playback_source(handoff=False)
                self._clear_playback_song()
        elif force_switch and self._unified_stream_active():
            self._release_playback_source(handoff=False)
            self._clear_playback_song()

        def _preload_done():
            try:
                self._preload_song_assets(dict(self.state.selected_song))
            finally:
                t = (self.state.selected_song or {}).get('title') or ''
                self._publish_status('song_switched', title=t)

        threading.Thread(target=_preload_done, name='song-preload', daemon=True).start()

    def _preload_song_assets(self, song: dict):
        try:
            self._sync_playback_output_device()
            play_path = song.get('play_path') or song.get('cover_path')
            if play_path and Path(play_path).is_file():
                self._player.load(str(play_path))
            if song.get('instrumental_path') and song.get('vocal_path'):
                self.pitch_follow.preload(song)
        except Exception:
            logger.debug('song preload failed:\n%s', traceback.format_exc())

    def _sync_playback_output_device(self):
        audio = self.config_store.get('audio', {}) or {}
        from app.audio.devices import resolve_io_devices
        _, out = resolve_io_devices(audio.get('input_device'), audio.get('output_device'), hostapi=audio.get('hostapi'))
        self._player.set_output_device(out)
        self._player.set_target_sr(int(audio.get('sample_rate', 48000)))

    @staticmethod
    def _wav_duration(path: str) -> float:
        try:
            import soundfile as sf
            info = sf.info(str(path))
            return float(info.duration) if info.samplerate else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _align_timeline(time_sec: float, from_dur: float, to_dur: float) -> float:
        if from_dur <= 0 or to_dur <= 0:
            return max(0.0, float(time_sec or 0))
        ratio = max(0.0, min(1.0, float(time_sec) / from_dur))
        return max(0.0, min(to_dur, ratio * to_dur))

    def _current_song_position(self) -> float:
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            return mgr.inst_position
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            pf = self._pitch_follow
            if pf is not None and pf.duration > 0:
                return pf.position
        if self.state.playback_running and self._player.is_active:
            return self._player.position
        return 0.0

    def _ensure_playback_lyrics(self, time_sec: float = 0.0):
        if not self.state.loaded_lyrics:
            return
        if not self.state.lyrics_running:
            self.lyrics.start(source='manual', enable_tick=False)
            self.state.lyrics_running = True
        self.lyrics.sync_at(time_sec, force=True)

    def _reset_playback_lyrics(self, time_sec: float = 0.0):
        if not self.state.loaded_lyrics:
            return
        if not self.state.lyrics_running:
            self.lyrics.start(source='manual', enable_tick=False)
            self.state.lyrics_running = True
        self.lyrics.reset_sync(time_sec)

    def _start_ai_sing(self, payload: dict):
        self._dispatch_mode_switch(self._start_ai_sing_impl, self._with_autoplay(payload))

    def _start_ai_sing_impl(self, payload: dict):
        payload = payload or {}
        song = (payload or {}).get('song') or self.state.selected_song or {}
        if self.state.offline_running and not self._offline_allows_playback(song):
            self._publish_status('playback_blocked', log='离线做歌进行中，请稍后再播放')
            return
        autoplay = bool(payload.get('autoplay', True))
        carry_pos = float(payload.get('position', 0) or 0) if 'position' in payload else self._current_song_position()
        if self.state.realtime_running:
            self.stop_realtime()
        self._select_song({'song': song})
        if self._song_unified_ready(song, 'ai_sing'):
            if self._switch_unified_playback('ai_sing', song, carry_pos, autoplay):
                title = song.get('title') or Path(song.get('instrumental_path') or '').stem
                pos, dur, playing, paused = self._timeline_inst_state()
                self._inst_end_sent = False
                hint = '（从 %s 继续）' % self._fmt_pos(pos) if pos > 0.5 else ''
                if autoplay:
                    self._publish_status(
                        'playback_started',
                        title=title,
                        play_path=song.get('vocal_path'),
                        duration=dur,
                        position=pos,
                        playing=playing,
                        paused=paused,
                        log='AI 唱歌：正在播放 %s%s' % (title, hint),
                    )
                else:
                    self._publish_status(
                        'playback_started',
                        title=title,
                        play_path=song.get('vocal_path'),
                        duration=dur,
                        position=pos,
                        playing=False,
                        paused=True,
                        log='AI 唱歌：已就绪 %s（按播放键开始）' % title,
                    )
                return
        if self._unified_stream_active():
            self._release_playback_source(handoff=False)
            if 'position' not in payload:
                carry_pos = 0.0
            time.sleep(0.03)
        elif self._player.is_active:
            self._player.stop()
            time.sleep(0.02)
        play_path = song.get('play_path') or song.get('cover_path') or song.get('vocal_path')
        if not play_path:
            self._publish_error('请先在歌库选择已生成的 AI 歌曲（需 cover.wav 或 converted_vocal.wav）')
            return
        explicit_pos = 'position' in payload
        from_inst_dur = 0.0
        reverb_handoff = False
        if self.state.mode == 'reverb_talk':
            reverb_handoff = True
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                carry_pos = mgr.inst_position
                from_inst_dur = mgr.inst_duration
            self.stop_passthrough(handoff=True)
            self._player.stop()
            time.sleep(0.03)
        elif self.state.passthrough_running:
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                carry_pos = mgr.inst_position
                from_inst_dur = mgr.inst_duration
            self.stop_passthrough(handoff=True)
            self._player.stop()
            time.sleep(0.03)
        elif not explicit_pos and carry_pos <= 0:
            carry_pos = self._current_song_position()
        follow_active = self.state.ai_follow_running or self.state.ai_follow_preparing
        if follow_active:
            pf = self._pitch_follow
            if pf is not None:
                if pf.duration > 0:
                    from_inst_dur = pf.duration
                if carry_pos <= 0:
                    carry_pos = pf.position
            self.stop_ai_follow(handoff=True)
            time.sleep(0.03)
        self._sync_playback_output_device()
        try:
            duration = self._player.load(play_path)
        except Exception as exc:
            self._publish_error('无法加载音频: %s' % exc, exc)
            return
        if carry_pos > 0 and from_inst_dur > 0 and duration > 0 and abs(from_inst_dur - duration) > 0.05:
            carry_pos = self._align_timeline(carry_pos, from_inst_dur, duration)
        if carry_pos > 0 and duration > 0:
            self._player.seek_ratio(carry_pos / duration)
        elif duration > 0:
            self._player.seek_ratio(0)
        elif self.state.playback_running and not reverb_handoff and not follow_active:
            self._stop_playback(handoff=True)
        self.state.mode = 'ai_sing'
        self._inst_end_sent = False
        pos = self._player.position
        if pos <= 0.15:
            self._reset_playback_lyrics(pos)
        else:
            self._ensure_playback_lyrics(pos)
        if not autoplay:
            self.state.playback_running = False
            self._restart_playback_tick()
            title = song.get('title') or Path(play_path).stem
            self._publish_status(
                'playback_started',
                title=title,
                play_path=play_path,
                duration=duration,
                position=pos,
                playing=False,
                paused=True,
                log='AI 唱歌：已就绪 %s（按播放键开始）' % title,
            )
            self._publish_status(
                'playback_tick',
                position=pos,
                duration=duration,
                playing=False,
                paused=True,
            )
            return
        self.state.playback_running = True
        started = False
        last_err = None
        for attempt in range(4):
            try:
                if not self._player.play(on_finish=self._on_playback_finished):
                    raise RuntimeError('播放器未启动')
                started = True
                break
            except Exception as exc:
                last_err = exc
                logger.warning('player play retry %s: %s', attempt + 1, exc)
                time.sleep(0.08 * (attempt + 1))
        if not started:
            self.state.playback_running = False
            self.state.mode = 'idle'
            self._halt_playback_tick()
            self._publish_error('AI 唱歌播放失败: %s' % last_err, last_err)
            self._publish_status('playback_stopped', log='AI 唱歌启动失败，请稍后再试')
            return
        time.sleep(0.06)
        if not self._player.is_active:
            logger.warning('ai_sing inactive after play, retry once pos=%.2fs', self._player.position)
            self._player.stop()
            time.sleep(0.12)
            try:
                if not self._player.play(on_finish=self._on_playback_finished):
                    raise RuntimeError('播放器重试未启动')
            except Exception as exc:
                logger.error('ai_sing retry play failed: %s', exc, exc_info=True)
                self.state.playback_running = False
                self.state.mode = 'idle'
                self._halt_playback_tick()
                self._publish_error('AI 唱歌播放失败: %s' % exc, exc)
                self._publish_status('playback_stopped', log='AI 唱歌启动失败，请稍后再试')
                return
        self._restart_playback_tick()
        pos = self._player.position
        title = song.get('title') or Path(play_path).stem
        logger.info('ai_sing playing title=%s pos=%.2fs active=%s', title, pos, self._player.is_active)
        hint = '（从 %s 继续）' % self._fmt_pos(pos) if pos > 0.5 else ''
        self._publish_status(
            'playback_started',
            title=title,
            play_path=play_path,
            duration=duration,
            position=pos,
            playing=True,
            paused=False,
            log='AI 唱歌：正在播放 %s%s' % (title, hint),
        )
        self._publish_status(
            'playback_tick',
            position=pos,
            duration=duration,
            playing=True,
            paused=False,
        )
        self._mark_playback_song(song)
        song_assets = dict(self.state.selected_song) if self.state.selected_song else dict(song)
        if song_assets.get('instrumental_path') and song_assets.get('vocal_path'):
            threading.Thread(
                target=self._preload_song_assets,
                args=(song_assets,),
                name='song-preload',
                daemon=True,
            ).start()

    def _playback_tick_loop(self, gen: int):
        stuck = 0
        while not self._playback_stop.is_set() and self._tick_generation == gen:
            mgr = self._unified_mgr()
            if mgr is not None and mgr.inst_duration > 0:
                stuck = 0
                pos, dur, playing, paused = self._timeline_inst_state()
                if mgr.inst_finished and not mgr.inst_paused and not self._inst_end_sent:
                    self._inst_end_sent = True
                    if self._handle_track_end(from_follow=(self.state.mode == 'ai_follow')):
                        break
                self.lyrics.sync_at(pos)
                self._maybe_smart_switch(pos, playing, paused)
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=dur,
                    playing=playing,
                    paused=paused,
                    **self._playback_tick_extra(),
                )
            elif self._player.is_active:
                stuck = 0
                pos = self._player.position
                playing = self._player.is_playing
                paused = not self._player.is_playing and self._player.is_active
                self.lyrics.sync_at(pos)
                self._maybe_smart_switch(pos, playing, paused)
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=self._player.duration,
                    playing=self._player.is_playing,
                    paused=not self._player.is_playing and self._player.is_active,
                    **self._playback_tick_extra(),
                )
            elif self.state.mode == 'ai_sing' and self.state.playback_running:
                stuck += 1
                if stuck in (3, 10, 30):
                    logger.warning(
                        'ai_sing tick stalled gen=%s stuck=%s player_active=%s pos=%.2fs mode=%s',
                        gen,
                        stuck,
                        self._player.is_active,
                        self._player.position,
                        self.state.mode,
                    )
            if self._playback_stop.wait(0.03) or self._tick_generation != gen:
                break

    def _play_mode(self) -> str:
        mode = str(self.config_store.get('playback.play_mode', 'sequential') or 'sequential')
        return mode if mode in PLAY_MODES else 'sequential'

    def _set_play_mode(self, payload=None):
        if payload and (payload or {}).get('mode'):
            mode = str(payload.get('mode') or 'sequential')
        else:
            cur = self._play_mode()
            mode = PLAY_MODES[(PLAY_MODES.index(cur) + 1) % len(PLAY_MODES)]
        if mode not in PLAY_MODES:
            return
        self.config_store.set('playback.play_mode', mode)
        try:
            self.config_store.save()
        except OSError as exc:
            logger.warning('play_mode save failed: %s', exc)
        self._publish_status('play_mode_changed', mode=mode, log='播放模式：%s' % PLAY_MODE_LABELS[mode])

    def _pick_next_song(self, repeat_same: bool = False):
        cur = self.state.selected_song or {}
        library = self._library_inst if str(cur.get('library_type') or '') == 'accompaniment' else self._library_sing
        if not library:
            return None
        current = self.state.selected_song or {}
        if repeat_same and current.get('play_path'):
            return dict(current)
        cur_id = current.get('id') or current.get('play_path')
        mode = self._play_mode()
        if mode == 'repeat_one':
            return dict(current) if current.get('play_path') else None
        if mode == 'shuffle':
            import random
            pool = [s for s in library if (s.get('id') or s.get('play_path')) != cur_id] or library
            return dict(random.choice(pool))
        idx = 0
        for i, s in enumerate(library):
            if (s.get('id') or s.get('play_path')) == cur_id:
                idx = i
                break
        return dict(library[(idx + 1) % len(library)])

    def _continue_mode_with_song(self, mode: str, song: dict, carry_pos: float = 0.0, autoplay: bool = True):
        self._dispatch_mode_switch(self._continue_mode_with_song_impl, mode, dict(song), float(carry_pos), bool(autoplay))

    def _continue_mode_with_song_impl(self, mode: str, song: dict, carry_pos: float = 0.0, autoplay: bool = True):
        if float(carry_pos or 0) <= 0.15:
            self._reset_playback_lyrics(float(carry_pos or 0))
        payload = {'song': song, 'position': carry_pos, 'autoplay': autoplay}
        if mode == 'ai_sing':
            self._start_ai_sing_impl(payload)
        elif mode == 'ai_follow':
            self._start_ai_follow(payload)
        elif mode == 'reverb_talk':
            self._start_talk(payload, mode='reverb_talk')
        elif mode == 'normal_talk':
            self._start_talk(payload, mode='normal_talk')
        else:
            self._start_ai_sing_impl(payload)

    def _handle_track_end(self, from_follow: bool = False) -> bool:
        if self._track_end_busy:
            return True
        self._track_end_busy = True
        try:
            mode = self._play_mode()
            cur_mode = self.state.mode
            song = self.state.selected_song or {}
            title = song.get('title') or Path(song.get('play_path') or '').stem
            if mode == 'repeat_one' and cur_mode in PLAYBACK_MODES:
                mgr = self._unified_mgr()
                if mgr is not None and mgr.inst_duration > 0:
                    mgr.replay_instrumental()
                    self._inst_end_sent = False
                    self._smart_silent_acc = 0.0
                    self._smart_vocal_acc = 0.0
                    self._reset_playback_lyrics(0.0)
                    pos, dur, playing, paused = self._timeline_inst_state()
                    self._publish_status(
                        'playback_tick',
                        position=pos,
                        duration=dur,
                        playing=playing,
                        paused=paused,
                    )
                    self._publish_status('track_advance', title=title, log='单曲循环：%s' % title)
                    return False
            next_song = self._pick_next_song()
            if not next_song or not next_song.get('play_path'):
                return False
            next_title = next_song.get('title') or Path(next_song.get('play_path') or '').stem
            if mode == 'repeat_one':
                hint = '单曲循环：%s' % next_title
            elif mode == 'shuffle':
                hint = '随机播放：%s' % next_title
            else:
                hint = '下一首：%s' % next_title
            self._select_song({'song': next_song, 'resume_if_playing': False})
            self._publish_status('select_song_ui', title=next_title)
            self._publish_status('track_advance', title=next_title, log=hint)
            self._inst_end_sent = False
            active_mode = cur_mode if cur_mode in ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk') else 'ai_sing'
            self._continue_mode_with_song(active_mode, next_song, 0.0)
            return True
        finally:
            self._track_end_busy = False

    def _on_playback_finished(self):
        if self.state.ai_follow_running or self.state.ai_follow_preparing or self.state.mode == 'ai_follow':
            return
        if self._handle_track_end():
            return
        self.scheduler.publish(
            BusMessage(
                SignalType.STATUS,
                ModuleId.SCHEDULER,
                {'action': 'playback_finished', 'log': 'AI 唱歌播放完成'},
            )
        )
        self._stop_playback()

    def _toggle_playback_pause(self, payload=None):
        self._playback_transport(payload)

    def _seek_playback(self, payload: dict):
        ratio = float((payload or {}).get('ratio', 0))
        mgr = self._unified_mgr()
        if mgr is not None and mgr.inst_duration > 0:
            mgr.seek_instrumental(ratio * mgr.inst_duration)
            self.lyrics.sync_at(mgr.inst_position, force=True)
            pos, dur, playing, paused = self._timeline_inst_state()
            self._publish_status(
                'playback_tick',
                position=pos,
                duration=dur,
                playing=playing,
                paused=paused,
            )
            return
        if self.state.ai_follow_running and self._pitch_follow is not None and self._pitch_follow.duration > 0:
            self._pitch_follow.seek(ratio * self._pitch_follow.duration)
            self.lyrics.sync_at(self._pitch_follow.position, force=True)
            return
        if not self._player.is_active or self._player.duration <= 0:
            return
        self._player.seek_ratio(ratio)
        self.lyrics.sync_at(self._player.position, force=True)

    def _stop_playback(self, payload=None, handoff=False):
        if self._unified_stream_active():
            if handoff:
                return
            was_mode = self.state.mode
            self._halt_playback_tick(wait=0.4)
            self.audio.stop_stream()
            self.state.playback_running = False
            self.state.passthrough_running = False
            self.state.ai_follow_running = False
            if was_mode in PLAYBACK_MODES:
                self.lyrics.stop()
                self.state.lyrics_running = False
                self.state.mode = 'idle'
            self._clear_playback_song()
            self._publish_status('playback_stopped', log='播放已停止')
            return
        if handoff:
            self._player.stop()
        else:
            self._player.stop_reset()
        self._halt_playback_tick(wait=0.2 if handoff else 0.4)
        was_sing = self.state.mode == 'ai_sing'
        self.state.playback_running = False
        if handoff:
            return
        if was_sing:
            self.lyrics.stop()
            self.state.lyrics_running = False
            self.state.mode = 'idle'
        self._clear_playback_song()
        self._publish_status('playback_stopped', log='播放已停止')

    def _toggle_ai(self, payload=None):
        if self.state.realtime_running:
            self.stop_realtime()
        else:
            self._start_realtime_voice(payload or {})

    def _persist_config_safe(self):
        try:
            self.config_store.save()
        except OSError as exc:
            logger.warning('config save failed: %s', exc)
            self._publish_status('config_save_warn', log='参数已生效；配置文件写入失败（可能被占用），稍后再保存')

    def _schedule_config_save(self):
        if self._mix_save_timer is not None:
            self._mix_save_timer.cancel()
        self._mix_save_timer = threading.Timer(0.35, self._persist_config_safe)
        self._mix_save_timer.daemon = True
        self._mix_save_timer.start()

    def _update_ai_follow_mix(self, payload: dict):
        p = payload or {}
        cs = self.config_store
        for key in ('inst_ui', 'mic_ui', 'orig_ui', 'threshold', 'attenuation_ui'):
            if key in p:
                cs.set('pitchfix.%s' % key, int(p[key]))
        mapping = (
            ('inst_gain', 'inst_gain'),
            ('mic_gain', 'mic_gain'),
            ('ref_vocal_gain', 'ref_vocal_gain'),
            ('follow_threshold', 'follow_threshold'),
            ('follow_attenuation', 'follow_attenuation'),
        )
        for src, dst in mapping:
            if src in p:
                cs.set('pitchfix.%s' % dst, float(p[src]))
        if 'detune_mode' in p:
            cs.set('pitchfix.detune_mode', str(p['detune_mode']))
        pf = self._pitch_follow
        if pf is not None and (self.state.ai_follow_running or pf.running):
            pf.apply_settings(
                inst_gain=p.get('inst_gain'),
                mic_gain=p.get('mic_gain'),
                ref_vocal_gain=p.get('ref_vocal_gain'),
                follow_threshold=p.get('follow_threshold'),
                follow_attenuation=p.get('follow_attenuation'),
            )
        mgr = self.audio.manager
        if mgr is not None and mgr.running and mgr.config.playback_mode in PLAYBACK_MODES:
            mix = pitchfix_mix_from_config(self.config_store)
            mgr.config.inst_gain = inst_gain_from_config(self.config_store)
            mgr.config.mic_gain = mix['mic_gain']
            mgr.config.ref_vocal_gain = mix['ref_vocal_gain']
            mgr.config.follow_threshold = mix['follow_threshold']
            mgr.config.follow_attenuation = mix['follow_attenuation']
        self._schedule_config_save()

    def _release_playback_source(self, handoff: bool = True) -> float:
        pos = self._current_song_position()
        if handoff and self._unified_stream_active():
            return pos
        if self._unified_stream_active() and not handoff:
            pos = self._current_song_position()
            self._stop_playback(handoff=False)
            time.sleep(0.03)
            return pos
        if self.state.mode in ('reverb_talk', 'normal_talk') or (
            self.state.passthrough_running and self.audio.manager and self.audio.manager.inst_duration > 0
        ):
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                pos = mgr.inst_position
            self.stop_passthrough(handoff=handoff)
            time.sleep(0.03)
        elif self.state.ai_follow_running or self.state.ai_follow_preparing:
            pf = self._pitch_follow
            if pf is not None and pf.duration > 0:
                pos = pf.position
            self.stop_ai_follow(handoff=handoff)
            time.sleep(0.03)
        elif self.state.mode == 'ai_sing' or (self.state.playback_running and self._player.is_active):
            if self._player.duration > 0 or self._player.is_active:
                pos = self._player.position
            self._stop_playback(handoff=handoff)
            time.sleep(0.03)
        return pos

    def _toggle_ai_follow(self, payload=None):
        if (payload or {}).get('stop'):
            self._follow_prepare_cancel.set()
            self.stop_ai_follow()
            return
        self._dispatch_mode_switch(self._start_ai_follow, self._with_autoplay(payload or {}))

    def _finish_ai_follow_start(self, song: dict, carry_pos: float = 0.0):
        pf = self.pitch_follow
        self.state.ai_follow_preparing = False
        self.state.ai_follow_running = True
        self.state.mode = 'ai_follow'
        pos = pf.position if pf.duration > 0 else carry_pos
        self._ensure_playback_lyrics(pos)
        self._follow_stop.clear()
        self._follow_tick = threading.Thread(target=self._follow_tick_loop, name='ai-follow-tick', daemon=True)
        self.scheduler.register_thread('ai-follow-tick', self._follow_tick)
        self._follow_tick.start()
        title = song.get('title') or Path(song.get('instrumental_path') or '').stem
        hint = '（从 %s 继续）' % self._fmt_pos(pos) if pos > 0.5 else ''
        self._publish_status(
            'ai_follow_started',
            title=title,
            duration=pf.duration,
            position=pos,
            playing=True,
            log='AI 跟唱已启动：%s%s\n麦克风检测到声音时播放 AI 人声（按歌曲时间轴）；哼/说/吹气均可触发\n输出=伴奏+VAD 门控 AI 人声' % (title, hint),
        )

    def _start_ai_follow(self, payload: dict):
        payload = payload or {}
        autoplay = bool(payload.get('autoplay', True))
        carry_pos = float(payload.get('position', 0) or 0) if 'position' in payload else self._current_song_position()
        if self.state.realtime_running:
            self.stop_realtime()
        if self.state.offline_running:
            self._publish_status('realtime_blocked', log='离线任务进行中，请稍后再启动 AI 跟唱')
            return
        if self.state.ai_follow_preparing:
            return
        song = (payload or {}).get('song') or self.state.selected_song or {}
        if not song.get('instrumental_path') or not song.get('vocal_path'):
            if song.get('play_path') or song.get('title'):
                self._select_song({'song': song})
                song = self.state.selected_song
        if not song.get('instrumental_path'):
            self._publish_error('AI 跟唱需要伴奏 instrumental.wav，请先在歌库选择已做歌条目')
            return
        if not song.get('vocal_path'):
            self._publish_error('AI 跟唱需要参考人声 converted_vocal.wav，请先离线做歌')
            return
        self._select_song({'song': song})
        self.pitch_follow.preload(song)
        if self._switch_unified_playback('ai_follow', song, carry_pos, autoplay):
            title = song.get('title') or Path(song.get('instrumental_path') or '').stem
            pos, dur, playing, paused = self._timeline_inst_state()
            hint = '（从 %s 继续）' % self._fmt_pos(pos) if pos > 0.5 else ''
            self._publish_status(
                'ai_follow_started',
                title=title,
                duration=dur,
                position=pos,
                playing=playing if autoplay else False,
                paused=paused if not autoplay else False,
                log='AI 跟唱已启动：%s%s\n麦克风检测到声音时播放 AI 人声（按歌曲时间轴）' % (title, hint),
            )
            return
        explicit_pos = 'position' in payload
        handoff_dur = self._player.duration if self.state.playback_running and self._player.duration > 0 else 0.0
        need_release = (
            not self._unified_stream_active()
            and (
                self.state.passthrough_running
                or self.state.ai_follow_running
                or self.state.ai_follow_preparing
                or self.state.mode == 'ai_sing'
                or (self.state.playback_running and self._player.is_active)
            )
        )
        if need_release:
            released = self._release_playback_source(handoff=True)
            if not explicit_pos and carry_pos <= 0:
                carry_pos = released
        inst_dur = self._wav_duration(song['instrumental_path'])
        if carry_pos > 0 and handoff_dur > 0 and inst_dur > 0 and abs(handoff_dur - inst_dur) > 0.05:
            carry_pos = self._align_timeline(carry_pos, handoff_dur, inst_dur)
        tick_dur = inst_dur or handoff_dur
        self._ensure_playback_lyrics(carry_pos)
        if not autoplay:
            self.state.mode = 'ai_follow'
            self.state.ai_follow_running = False
            self.state.ai_follow_preparing = False
            self.state.playback_running = False
            title = song.get('title') or Path(song.get('instrumental_path') or '').stem
            self._publish_status(
                'ai_follow_started',
                title=title,
                duration=tick_dur,
                position=carry_pos,
                playing=False,
                paused=True,
                log='AI 跟唱：已就绪 %s（按播放键开始）' % title,
            )
            self._publish_status(
                'playback_tick',
                position=carry_pos,
                duration=tick_dur,
                playing=False,
                paused=True,
            )
            return
        if self.pitch_follow.assets_ready(song):
            self._publish_status(
                'ai_follow_preparing',
                title=song.get('title', ''),
                position=carry_pos,
                duration=tick_dur,
                playing=False,
                paused=True,
            )
            try:
                if self.state.playback_running:
                    self._stop_playback(handoff=True)
                self.pitch_follow.start(song, seek_sec=carry_pos)
                self._finish_ai_follow_start(song, carry_pos)
            except Exception as exc:
                logger.error('ai follow fast start failed:\n%s', traceback.format_exc())
                self._publish_error('AI 跟唱启动失败: %s' % exc, exc)
                self._publish_status('ai_follow_failed', message=str(exc))
            return
        if tick_dur > 0 or carry_pos > 0:
            self._publish_status(
                'playback_tick',
                position=carry_pos,
                duration=tick_dur,
                playing=self.state.playback_running,
                paused=not self.state.playback_running,
            )
        self.state.ai_follow_preparing = True
        self._follow_prepare_cancel.clear()
        self._publish_status(
            'ai_follow_preparing',
            title=song.get('title', ''),
            position=carry_pos,
            duration=tick_dur,
            playing=self.state.playback_running,
            paused=not self.state.playback_running,
            log='正在加载伴奏与 AI 人声…',
        )
        self._follow_prepare_thread = threading.Thread(
            target=self._ai_follow_prepare_worker,
            args=(dict(song), carry_pos),
            name='ai-follow-prepare',
            daemon=True,
        )
        self.scheduler.register_thread('ai-follow-prepare', self._follow_prepare_thread)
        self._follow_prepare_thread.start()

    def _ai_follow_prepare_worker(self, song: dict, carry_pos: float = 0.0):
        try:
            if self._follow_prepare_cancel.is_set():
                return
            self.pitch_follow.preload(song)
            if self._follow_prepare_cancel.is_set():
                return
            if self.state.playback_running:
                self._stop_playback(handoff=True)
            self.pitch_follow.start(song, seek_sec=carry_pos)
            if self._follow_prepare_cancel.is_set():
                self.pitch_follow.stop()
                return
            self._finish_ai_follow_start(song, carry_pos)
        except Exception as exc:
            self.state.ai_follow_preparing = False
            if not self._follow_prepare_cancel.is_set():
                logger.error('ai follow prepare failed:\n%s', traceback.format_exc())
                self._publish_error('AI 跟唱启动失败: %s' % exc, exc)
                self._publish_status('ai_follow_failed', message=str(exc))
        finally:
            self.scheduler.unregister_thread('ai-follow-prepare')
            self._follow_prepare_thread = None

    def _release_ai_follow(self, handoff=False):
        if handoff and self._unified_stream_active():
            self.state.ai_follow_running = False
            self.state.ai_follow_preparing = False
            return
        if self._pitch_follow is not None:
            self._pitch_follow.stop(keep_cache=handoff, fast=handoff)
        if self.state.lyrics_running and self.state.mode == 'ai_follow' and not handoff:
            self.lyrics.stop()
            self.state.lyrics_running = False
        was = self.state.ai_follow_running or self.state.ai_follow_preparing
        self.state.ai_follow_running = False
        self.state.ai_follow_preparing = False
        if self.state.mode == 'ai_follow' and not handoff:
            self.state.mode = 'idle'
        if was and not handoff:
            self._publish_status('ai_follow_stopped', log='AI 跟唱已停止')

    def _follow_tick_loop(self):
        natural_finish = False
        try:
            while not self._follow_stop.is_set():
                pf = self._pitch_follow
                if pf is None:
                    break
                if pf.running or pf.position > 0:
                    pos = pf.position
                    self.lyrics.sync_at(pos, force=False)
                    if not self._unified_stream_active():
                        self._maybe_smart_switch(pos, pf.running, False)
                    self._publish_status(
                        'playback_tick',
                        position=pos,
                        duration=pf.duration,
                        playing=pf.running,
                        paused=False,
                    )
                if not pf.running and pf.duration > 0 and pf.position >= max(0.0, pf.duration - 0.2):
                    natural_finish = True
                    break
                if self._follow_stop.wait(0.03):
                    break
        finally:
            continued = False
            if natural_finish:
                continued = self._handle_track_end(from_follow=True)
                if not continued:
                    self.scheduler.publish(
                        BusMessage(
                            SignalType.STATUS,
                            ModuleId.SCHEDULER,
                            {'action': 'ai_follow_finished', 'log': 'AI 跟唱伴奏已播完'},
                        )
                    )
            self._follow_stop.set()
            self._follow_tick = None
            try:
                self.scheduler.unregister_thread('ai-follow-tick')
            except Exception:
                pass
            if not continued:
                self._release_ai_follow(handoff=self._follow_handoff)

    def stop_ai_follow(self, payload=None, handoff=False):
        self._follow_handoff = handoff
        self._follow_prepare_cancel.set()
        self._follow_stop.set()
        prep = self._follow_prepare_thread
        if prep and prep.is_alive() and threading.current_thread() is not prep:
            prep.join(timeout=0.5)
        self._follow_prepare_thread = None
        try:
            self.scheduler.unregister_thread('ai-follow-prepare')
        except Exception:
            pass
        tick = self._follow_tick
        tick_released = False
        join_wait = 0.05 if handoff else 1.0
        if tick and tick.is_alive():
            if threading.current_thread() is tick:
                return
            tick.join(timeout=join_wait)
            tick_released = True
        self._follow_tick = None
        try:
            self.scheduler.unregister_thread('ai-follow-tick')
        except Exception:
            pass
        if not tick_released:
            self._release_ai_follow(handoff=handoff)

    def _start_realtime_voice(self, payload: dict):
        if self.state.passthrough_running:
            self.stop_passthrough()
        if self.state.playback_running:
            self._stop_playback()
        if self.state.ai_follow_running:
            self.stop_ai_follow()
        if self.state.offline_running:
            self._publish_status('realtime_blocked', log='离线任务进行中，请稍后再启动实时变声')
            return
        model_sid = (
            (payload or {}).get('model_sid')
            or self.state.current_model
            or self.config_store.get('realtime.model_sid')
            or discover_first_model(project_root=self.project_root)
        )
        if not model_sid:
            self._publish_error('未找到 RVC 模型，请将 .pth 放入 assets/weights')
            return
        self.realtime.start(model_sid=model_sid, use_audio=True)
        self.state.realtime_running = True
        self.state.current_model = model_sid
        self.state.mode = 'realtime'
        self._publish_status(
            'realtime_started',
            model_sid=model_sid,
            log='实时变声已启动（模型 %s）\n音频 IN: %s\n音频 OUT: %s'
            % (model_sid, self._device_name(self.audio.manager.config.input_device if self.audio.manager else None),
               self._device_name(self.audio.manager.config.output_device if self.audio.manager else None)),
        )

    def _device_name(self, index):
        if index is None:
            return '未设置'
        try:
            import sounddevice as sd
            return str(sd.query_devices(index).get('name', index))
        except Exception:
            return str(index)

    @staticmethod
    def _fmt_pos(sec: float) -> str:
        sec = max(0.0, float(sec or 0))
        m, s = divmod(int(sec), 60)
        return '%02d:%02d' % (m, s)

    def stop_realtime(self, payload=None):
        if self._realtime is not None:
            self._realtime.stop()
        if self.state.realtime_running:
            self.audio.stop_stream()
        self.state.realtime_running = False
        if self.state.mode == 'realtime':
            self.state.mode = 'idle'
        self._publish_status('realtime_stopped', log='实时变声已停止')

    def _load_lyrics(self, payload: dict):
        path = (payload or {}).get('path', '')
        if not path:
            self._publish_error('歌词路径为空')
            return
        self.lyrics.load_lrc(path, offset_ms=(payload or {}).get('offset_ms'), force=True)
        self.state.loaded_lyrics = True
        if self._lyrics_window:
            self._lyrics_window.show()
        doc = self.lyrics.document
        lines = [ln.text for ln in doc.lines]
        from app.lyrics.aligner import word_timing_label

        engine = str(self.config_store.get('lyrics.align_engine', 'energy') or 'energy').strip().lower()
        suffix = word_timing_label(
            doc.align_mode,
            has_words=doc.has_words,
            from_file=bool(getattr(self.lyrics, '_timing_from_file', False)),
            config_engine=engine,
        )
        self._publish_status(
            'lyrics_loaded',
            lines=lines,
            has_words=doc.has_words,
            align_mode=doc.align_mode,
            log='已加载歌词：%s（%s 行%s）' % (doc.title or Path(path).name, len(doc.lines), suffix),
        )

    def _enhance_lyrics(self, payload: dict = None):
        payload = payload or {}
        song = dict(self.state.selected_song or {})
        lrc = song.get('lrc_path') or ''
        if not lrc or not Path(lrc).is_file():
            self._publish_error('当前歌曲没有可增强的 LRC')
            return
        if getattr(self, '_enhance_busy', False):
            self._publish_status('lyrics_enhance_busy', log='逐字歌词生成中，请稍候…')
            return
        self._enhance_busy = True
        # payload 显式指定优先；否则读 lyrics.align_engine（energy|whisper）
        if 'use_whisper' in payload:
            use_whisper = bool(payload.get('use_whisper'))
        else:
            engine = str(self.config_store.get('lyrics.align_engine', 'energy') or 'energy').strip().lower()
            # 兼容误拼 whispera / whisper_asr
            use_whisper = engine.startswith('whisper') or engine in ('faster-whisper', 'asr')
        model_size = str(payload.get('model_size') or self.config_store.get('lyrics.whisper_model', 'small') or 'small')
        device_pref = str(payload.get('device') or self.config_store.get('lyrics.whisper_device', 'auto') or 'auto')

        def _work():
            try:
                from app.lyrics.aligner import (
                    enhance_lrc_file,
                    find_vocal_for_song,
                    local_whisper_ready,
                    whisper_available,
                )

                vocal = find_vocal_for_song(song.get('dir') or Path(lrc).parent, song.get('title') or '', song)
                if use_whisper and not whisper_available():
                    self._publish_status(
                        'lyrics_enhance_progress',
                        log='未安装 faster-whisper，回退人声能量对齐（可: pip install faster-whisper）',
                    )
                elif use_whisper:
                    if local_whisper_ready(model_size):
                        tip = 'Whisper 识别整首歌中（模型 %s 已在本地，非重新下载；同曲再次生成会更快）…' % model_size
                    else:
                        tip = 'Whisper 首次下载模型 %s 后识别整首歌…' % model_size
                    self._publish_status('lyrics_enhance_progress', log=tip)
                else:
                    self._publish_status('lyrics_enhance_progress', log='人声能量对齐中…')
                out, mode = enhance_lrc_file(
                    lrc,
                    vocal_path=vocal,
                    use_whisper=use_whisper,
                    model_size=model_size,
                    device_pref=device_pref,
                )
                self.state.selected_song['lrc_path'] = str(out.resolve())
                self.lyrics.load_lrc(out, force=True, vocal_path=None)
                self.state.loaded_lyrics = True
                doc = self.lyrics.document
                mode_label = {'whisper': 'Whisper', 'energy': '人声能量', 'even': '均分'}.get(mode, mode)
                if use_whisper and mode != 'whisper':
                    self._publish_status(
                        'lyrics_enhance_progress',
                        log='Whisper 未成功（模型/网络），已回退为 %s' % mode_label,
                    )
                self._publish_status(
                    'lyrics_loaded',
                    lines=[ln.text for ln in doc.lines],
                    has_words=doc.has_words,
                    log='已生成逐字歌词：%s（%s 行，%s）' % (out.name, len(doc.lines), mode_label),
                )
            except Exception as exc:
                logger.error('lyrics enhance failed:\n%s', traceback.format_exc())
                self._publish_error('生成逐字歌词失败: %s' % exc, exc)
            finally:
                self._enhance_busy = False

        threading.Thread(target=_work, name='lyrics-enhance', daemon=True).start()

    def _rewrite_lyrics(self, payload: dict = None):
        payload = payload or {}
        song = self.state.selected_song or {}
        lrc = song.get('lrc_path') or self.lyrics._loaded_path
        if not lrc or not Path(lrc).is_file():
            self._publish_error('没有可保存的歌词文件')
            return
        idx = int(payload.get('line_index', -1))
        text = str(payload.get('text', ''))
        if idx < 0:
            self._publish_error('请先选中要修改的歌词行')
            return
        from app.lyrics.rewrite import save_rewrite

        try:
            save_rewrite(self.lyrics.document, lrc, idx, text)
            self.lyrics.load_lrc(lrc, force=True)
        except Exception as exc:
            self._publish_error('保存改词失败: %s' % exc, exc)
            return
        doc = self.lyrics.document
        self._publish_status(
            'lyrics_loaded',
            lines=[ln.text for ln in doc.lines],
            has_words=doc.has_words,
            log='已保存改词：第 %s 行' % (idx + 1),
        )

    def _start_offline_cover(self, payload: dict):
        if self.state.offline_running:
            self._publish_status('offline_busy', log='已有离线任务进行中')
            return
        if self.state.realtime_running:
            self.stop_realtime()
        input_path = (payload or {}).get('input', '')
        model = (payload or {}).get('model', '')
        if not input_path or not model:
            self._publish_error('离线做歌缺少 input 或 model')
            return
        thread = threading.Thread(
            target=self._offline_worker,
            args=(dict(payload),),
            name='offline-cover',
            daemon=True,
        )
        self._offline_thread = thread
        self.state.offline_running = True
        self.state.mode = 'offline'
        self.scheduler.register_thread('offline-cover', thread)
        self._publish_status('offline_started', log='离线做歌已开始…')
        thread.start()

    def _cancel_offline_user(self, payload=None):
        if not self.state.offline_running:
            self._publish_status('offline_idle', log='当前没有进行中的制作任务')
            return
        self._publish_status('offline_cancelling', log='正在取消制作…')
        self._cancel_offline(wait=False)

    def _offline_worker(self, payload: dict):
        from app.rvc import OfflineSongPipeline

        preset = payload.get('preset', 'normal')
        output_dir = payload.get('output_dir', 'opt/task4_offline')
        params = RvcInferParams(
            f0_up_key=int(payload.get('f0_up_key', 0)),
            f0_method=str(payload.get('f0_method', 'rmvpe')),
            index_rate=float(payload.get('index_rate', 0.75)),
            protect=float(payload.get('protect', 0.33)),
            file_index=resolve_index_for_model(payload.get('model', ''), self.project_root) or '',
        )
        pipeline = OfflineSongPipeline(work_root=str(Path(output_dir) / 'msst_work'), msst_keep_work=False)
        self._offline_pipeline = pipeline
        terminal = None
        try:
            for event in pipeline.run(
                payload.get('model'),
                payload.get('input'),
                vc=None,
                preset_id=preset,
                output_dir=output_dir,
                rvc_params=params,
                mix_cover=True,
                output_format='wav',
                event_callback=lambda e: self._publish_progress(**e),
            ):
                if event.get('event') in {'result', 'failed', 'cancelled'}:
                    terminal = event
            if terminal and terminal.get('event') == 'result':
                result = terminal.get('result')
                cover = getattr(result, 'cover_path', None) or terminal.get('cover_path')
                used_model = payload.get('model', '')
                if used_model:
                    self.state.current_model = used_model
                    self.config_store.set('realtime.model_sid', used_model)
                    self.config_store.save()
                result_dict = result.as_dict() if hasattr(result, 'as_dict') else {}
                stem = Path(payload.get('input', '')).stem
                lrc_src = (payload.get('lrc_path') or '').strip()
                if lrc_src and Path(lrc_src).is_file() and stem:
                    out_lrc = Path(output_dir) / ('%s.lrc' % stem)
                    try:
                        shutil.copy2(lrc_src, out_lrc)
                        from app.lyrics.aligner import enhance_lrc_file, find_vocal_for_song

                        vocal = find_vocal_for_song(output_dir, stem)
                        enhance_lrc_file(out_lrc, vocal_path=vocal, use_whisper=False)
                        result_dict['lrc_path'] = str(out_lrc.resolve())
                    except Exception as exc:
                        logger.warning('copy/enhance lrc failed: %s', exc)
                self._publish_status(
                    'offline_finished',
                    log='离线做歌完成：%s' % (cover or output_dir),
                    title=stem,
                    cover_path=cover,
                    result=result_dict,
                )
                self._refresh_library()
            elif terminal and terminal.get('event') == 'cancelled':
                self._publish_status(
                    'offline_cancelled',
                    message=terminal.get('message') or '制作已取消',
                    log='制作已取消',
                )
            elif terminal:
                msg = terminal.get('message') or terminal.get('event') or 'offline failed'
                detail = (terminal.get('detail') or '').strip()
                if detail and detail not in msg:
                    msg = '%s\n%s' % (msg, detail[:2000])
                self._publish_status('offline_failed', message=msg)
                self._publish_error(msg)
        except ModuleNotFoundError as exc:
            msg = '未检测到 PyTorch，无法做歌。请使用 build_demo_package.bat 重新打包（含 CondaPack），或安装 conda 环境 rvc312 后重启。' if exc.name == 'torch' else str(exc)
            logger.error('offline worker failed:\n%s', traceback.format_exc())
            self._publish_status('offline_failed', message=msg)
            self._publish_error(msg, exc)
        except Exception as exc:
            logger.error('offline worker failed:\n%s', traceback.format_exc())
            self._publish_status('offline_failed', message=str(exc))
            self._publish_error('离线做歌失败: %s' % exc, exc)
        finally:
            with self._lock:
                self.state.offline_running = False
                if self.state.mode == 'offline':
                    self.state.mode = 'idle'
                self._offline_thread = None
                self.scheduler.unregister_thread('offline-cover')

    def _cancel_offline(self, wait=False):
        if not self.state.offline_running:
            return
        try:
            if self._offline_pipeline is not None:
                self._offline_pipeline.cancel()
        except Exception:
            pass
        if wait and self._offline_thread and self._offline_thread.is_alive():
            self._offline_thread.join(timeout=1.0)

    def _check_update(self, payload=None):
        payload = payload or {}
        threading.Thread(
            target=self._check_update_worker,
            args=(bool(payload.get('silent')),),
            name='check-update',
            daemon=True,
        ).start()

    def _check_update_worker(self, silent: bool = False):
        from app.ops.update_client import UpdateClient

        client = UpdateClient(self.config_store, self.project_root)
        result = client.check()
        if not result.get('ok'):
            self._publish_status('update_failed', silent=silent, message=result.get('error', '检查失败'))
            return
        if result.get('need_update'):
            self._publish_status(
                'update_available',
                silent=silent,
                current_version=result.get('current_version'),
                latest_version=result.get('latest_version'),
                force_update=result.get('force_update'),
                update_desc=result.get('update_desc'),
            )
            return
        msg = '当前已是最新版本（%s）' % result.get('current_version', '')
        self._publish_status('update_checked', silent=silent, message=msg, log=msg if not silent else '')

    def _apply_update(self, payload=None):
        if self._update_running:
            return
        threading.Thread(
            target=self._apply_update_worker,
            args=(payload or {},),
            name='apply-update',
            daemon=True,
        ).start()

    def _apply_update_worker(self, payload: dict):
        from app.ops.update_client import UpdateClient

        self._update_running = True
        try:
            client = UpdateClient(self.config_store, self.project_root)
            use_patch = bool(payload.get('use_patch', True))

            def on_progress(ratio, msg=''):
                self._publish_progress(percent=int(float(ratio or 0) * 100), message=msg or '更新中…', phase='update')

            result = client.apply(use_patch=use_patch, on_progress=on_progress)
            if not result.get('ok'):
                self._publish_status('update_failed', message=result.get('error', '更新失败'))
                return
            if result.get('updated'):
                self._publish_status(
                    'update_finished',
                    updated=True,
                    version=result.get('version'),
                    install_dir=result.get('install_dir'),
                    backup_dir=result.get('backup_dir'),
                    log='已更新至 %s，请重启客户端' % result.get('version'),
                )
            else:
                self._publish_status('update_finished', updated=False, message='无需更新')
        finally:
            self._update_running = False

    def _skip_update(self, payload=None):
        from app.ops.update_client import UpdateClient

        version = str((payload or {}).get('version') or '').strip()
        if not version:
            return
        UpdateClient(self.config_store, self.project_root).skip_version(version)
        self._publish_status('update_skipped', log='已跳过版本 %s' % version)

    def _save_settings(self, payload: dict):
        payload = payload or {}
        audio = payload.get('audio') or {}
        from app.audio.devices import device_ref_for_config, list_devices
        devices = list_devices(hostapi=audio.get('hostapi') or self.config_store.get('audio.hostapi'))
        for key in ('hostapi', 'wasapi_exclusive', 'sample_rate', 'passthrough_gain', 'passthrough_ui', 'reverb_mix', 'reverb_decay'):
            if key in audio:
                self.config_store.set('audio.%s' % key, audio[key])
        if 'input_device' in audio:
            self.config_store.set('audio.input_device', device_ref_for_config(audio['input_device'], devices))
        if 'output_device' in audio:
            self.config_store.set('audio.output_device', device_ref_for_config(audio['output_device'], devices))
        if 'passthrough_ui' in audio:
            from app.audio.service import passthrough_gain_from_audio
            merged = dict(self.config_store.get('audio', {}) or {})
            merged.update(audio)
            self.config_store.set('audio.passthrough_gain', passthrough_gain_from_audio(merged))
        realtime = payload.get('realtime') or {}
        for key, val in realtime.items():
            self.config_store.set('realtime.%s' % key, val)
        if realtime.get('model_sid'):
            self.state.current_model = str(realtime['model_sid'])
        if realtime.get('f0_method'):
            self.config_store.set('rvc.f0_method', str(realtime['f0_method']))
        if 'pitch' in realtime:
            self.config_store.set('rvc.f0_up_key', int(realtime['pitch']))
        if 'formant' in realtime:
            self.config_store.set('rvc.formant', float(realtime['formant']))
        if 'index_rate' in realtime:
            self.config_store.set('rvc.index_rate', float(realtime['index_rate']))
        if payload.get('osc_port') is not None:
            self.config_store.set('lyrics.osc_port', int(payload['osc_port']))
        lyrics = payload.get('lyrics') or {}
        for key in ('align_engine', 'whisper_model', 'whisper_device'):
            if key in lyrics and lyrics[key] is not None:
                self.config_store.set('lyrics.%s' % key, str(lyrics[key]).strip())
        if 'lead_ms' in lyrics:
            self.config_store.set('lyrics.lead_ms', int(lyrics['lead_ms']))
        if 'offset_ms' in lyrics:
            self.config_store.set('lyrics.offset_ms', int(lyrics['offset_ms']))
        if lyrics:
            off = int(self.config_store.get('lyrics.offset_ms', 0) or 0)
            lead = int(self.config_store.get('lyrics.lead_ms', 0) or 0)
            self.lyrics.matcher.set_offset_ms(off + lead)
        if payload.get('update_url') is not None:
            self.config_store.set('update.check_url', str(payload['update_url']).strip())
        if payload.get('update_auto_check') is not None:
            self.config_store.set('update.auto_check', bool(payload['update_auto_check']))
        if payload.get('crash_auto_upload') is not None:
            self.config_store.set('logs.auto_upload_crash', bool(payload['crash_auto_upload']))
        if payload.get('log_upload_url') is not None:
            self.config_store.set('logs.upload_url', str(payload['log_upload_url']).strip())
        if payload.get('log_dir'):
            self.config_store.set('paths.log_dir', str(payload['log_dir']).strip())
        if payload.get('sr_type'):
            self.config_store.set('realtime.sr_type', str(payload['sr_type']))
        shortcuts = payload.get('shortcuts') or {}
        for key, val in shortcuts.items():
            self.config_store.set('shortcuts.%s' % key, str(val or '').strip())
        playback = payload.get('playback') or {}
        play_mode = str(playback.get('play_mode') or '').strip()
        if play_mode in PLAY_MODES:
            self.config_store.set('playback.play_mode', play_mode)
        if 'smart_switch' in playback:
            self.config_store.set('playback.smart_switch', bool(playback.get('smart_switch')))
            if playback.get('smart_switch'):
                self._smart_reverb_active = False
                self._smart_silent_acc = 0.0
                self._smart_vocal_acc = 0.0
            else:
                self._reset_smart_switch()
        if playback.get('smart_switch_min_gap_sec') is not None:
            self.config_store.set('playback.smart_switch_min_gap_sec', float(playback['smart_switch_min_gap_sec']))
        pitchfix = payload.get('pitchfix') or {}
        for key in ('inst_ui', 'mic_ui', 'orig_ui', 'threshold', 'attenuation_ui'):
            if key in pitchfix:
                self.config_store.set('pitchfix.%s' % key, int(pitchfix[key]))
        for src, dst in (
            ('inst_gain', 'inst_gain'),
            ('mic_gain', 'mic_gain'),
            ('ref_vocal_gain', 'ref_vocal_gain'),
            ('follow_threshold', 'follow_threshold'),
            ('follow_attenuation', 'follow_attenuation'),
        ):
            if src in pitchfix:
                self.config_store.set('pitchfix.%s' % dst, float(pitchfix[src]))
        pf = self._pitch_follow
        if pitchfix and pf is not None and (self.state.ai_follow_running or pf.running):
            pf.apply_settings(
                inst_gain=pitchfix.get('inst_gain'),
                mic_gain=pitchfix.get('mic_gain'),
                ref_vocal_gain=pitchfix.get('ref_vocal_gain'),
                follow_threshold=pitchfix.get('follow_threshold'),
                follow_attenuation=pitchfix.get('follow_attenuation'),
            )
        self.config_store.save()
        self._sync_playback_output_device()
        mgr = self.audio.manager
        if mgr and mgr.running:
            audio_cfg = dict(self.config_store.get('audio', {}) or {})
            if mgr.config.passthrough:
                from app.audio.service import passthrough_gain_from_audio
                mgr.config.passthrough_gain = passthrough_gain_from_audio(audio_cfg)
            mgr.config.reverb_mix = float(audio_cfg.get('reverb_mix', 0.35))
            mgr.config.reverb_decay = float(audio_cfg.get('reverb_decay', 0.72))
            if mgr.config.playback_mode in PLAYBACK_MODES:
                mix = pitchfix_mix_from_config(self.config_store)
                mgr.config.inst_gain = inst_gain_from_config(self.config_store)
                mgr.config.mic_gain = mix['mic_gain']
                mgr.config.ref_vocal_gain = mix['ref_vocal_gain']
                mgr.config.follow_threshold = mix['follow_threshold']
                mgr.config.follow_attenuation = mix['follow_attenuation']
        hint = ''
        if self.state.passthrough_running or self.state.realtime_running:
            hint = '（请重新开启普通说话/混响说话/AI 跟唱使新设备生效）'
        self._publish_status('settings_saved', log='音频与系统设置已写入 config/client.json%s' % hint)
        if play_mode in PLAY_MODES:
            self._publish_status('play_mode_changed', mode=play_mode)

    def _test_mic(self, payload=None):
        payload = payload or {}
        if payload.get('stop'):
            if self._is_talk_mode():
                self.stop_passthrough()
            return
        if self._is_talk_mode():
            return
        self._start_talk(payload, mode='normal_talk')
