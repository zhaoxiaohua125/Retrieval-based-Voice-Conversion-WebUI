"""任务 7：全模块集成控制器（仅路由与生命周期，不含业务实现）。"""

import logging
import queue
import shutil
import threading
import time
import traceback
from pathlib import Path

from app.audio import AudioService
from app.audio.service import passthrough_gain_from_audio
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.integration.state import ClientState
from app.lyrics import LyricsService
from app.ops.exceptions import classify_exception
from app.playback import WavPlayer, scan_song_library
from app.playback.library import find_lrc_in_dir
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
        self._library = []
        self._started = False
        self._lock = threading.RLock()
        self._tick_generation = 0
        self._track_end_busy = False
        self._inst_end_sent = False
        self._switch_queue = queue.Queue()
        self._switch_worker = threading.Thread(target=self._switch_worker_loop, name='mode-switch', daemon=True)
        self._switch_worker.start()

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
        self.lyrics.set_tick_handler(lambda payload: window.set_line(payload.get('text', ''), highlight=True))

    @property
    def library(self):
        return list(self._library)

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
            'check_update': self._check_update,
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
            except Exception:
                logger.error('mode switch failed (%s):\n%s', name, traceback.format_exc())
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

    def _reverb_inst_state(self):
        mgr = self.audio.manager
        if mgr is None or mgr.inst_duration <= 0:
            return 0.0, 0.0, False, False
        pos = mgr.inst_position
        dur = mgr.inst_duration
        playing = mgr.inst_playing and not mgr.inst_paused
        paused = mgr.inst_paused and mgr.inst_playing
        return pos, dur, playing, paused

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
        if self._is_talk_mode() and self.state.mode != mode:
            self.stop_passthrough(handoff=True)
        if self.state.mode == 'ai_sing' or (self.state.playback_running and self._player.is_active):
            carry_pos = self._player.position
            self._stop_playback(handoff=True)
            time.sleep(0.15)
            logger.info('talk handoff from ai_sing pos=%.2fs mode=%s', carry_pos, mode)
        elif self.state.ai_follow_running or self.state.ai_follow_preparing:
            carry_pos = self._current_song_position()
            self.stop_ai_follow(handoff=True)
            time.sleep(0.15)
            logger.info('talk handoff from ai_follow pos=%.2fs mode=%s', carry_pos, mode)
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
        if audio_cfg.get('input_device') is None or audio_cfg.get('output_device') is None:
            self._publish_error('请先在 config/client.json 配置 audio.input_device 与 output_device')
            self._publish_status('passthrough_blocked', log='%s：未配置音频设备' % label)
            return
        last_err = None
        for attempt in range(4):
            try:
                self.audio.start_stream(
                    passthrough=True,
                    reverb=(mode == 'reverb_talk'),
                    inst_path=inst_path or None,
                    inst_seek=carry_pos,
                )
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                logger.warning('%s stream retry %s: %s', label, attempt + 1, exc)
                time.sleep(0.12 * (attempt + 1))
        if last_err is not None:
            self._publish_error('音频流启动失败: %s' % last_err, last_err)
            self._publish_status('passthrough_blocked', log='%s启动失败' % label)
            return
        self.state.mode = mode
        self.state.passthrough_running = True
        in_dev = self.audio.manager.config.input_device if self.audio.manager else None
        out_dev = self.audio.manager.config.output_device if self.audio.manager else None
        gain = passthrough_gain_from_audio(self.config_store.get('audio', {}) or {})
        inst_hint = ''
        pos, dur, playing, paused = 0.0, 0.0, False, False
        has_inst = bool(inst_path)
        if has_inst and mode in ('reverb_talk', 'normal_talk'):
            self._inst_end_sent = False
            self._ensure_playback_lyrics(carry_pos)
            self._restart_playback_tick()
            if not autoplay:
                mgr = self.audio.manager
                if mgr is not None and mgr.inst_duration > 0 and not mgr.inst_paused:
                    mgr.toggle_inst_pause()
                self.state.playback_running = False
            else:
                self.state.playback_running = True
            pos, dur, playing, paused = self._reverb_inst_state()
            inst_hint = '\n伴奏：%s（与 AI 唱歌可互切，播放头同步）' % Path(inst_path).name
            self._publish_status(
                'playback_tick',
                position=pos,
                duration=dur,
                playing=playing,
                paused=paused,
            )
        elif mode in ('reverb_talk', 'normal_talk'):
            inst_hint = '\n未找到伴奏轨，仅麦克风' if mode == 'reverb_talk' else '\n未找到伴奏轨，仅干声'
        extra = '\n已叠加房间混响（可调 audio.reverb_mix / reverb_decay）' if mode == 'reverb_talk' else ''
        talk_mode_desc = {
            'reverb_talk': '伴奏+混响麦' if has_inst else '干声+混响直通',
            'normal_talk': '伴奏+干声麦' if has_inst else '干声直通已启动（不经 RVC）',
        }
        self._publish_status(
            'passthrough_started',
            mode=mode,
            input_device=in_dev,
            output_device=out_dev,
            position=pos if has_inst else 0.0,
            duration=dur if has_inst else 0.0,
            playing=playing if has_inst else False,
            paused=paused if has_inst else False,
            log='%s：%s\nIN: %s\nOUT: %s\n监听增益: %.1fx（设置里 %s%%）%s%s\n保存设置后需重开本模式；Voicemeeter：H1→B1，VAIO→A1'
            % (
                label,
                talk_mode_desc.get(mode, ''),
                self._device_name(in_dev),
                self._device_name(out_dev),
                gain,
                int(gain * 50),
                extra,
                inst_hint,
            ),
        )

    def stop_passthrough(self, payload=None, handoff: bool = False):
        if not self.state.passthrough_running and not (self.audio.manager and self.audio.manager.running):
            return
        was_reverb = self.state.mode == 'reverb_talk'
        was_talk = self.state.mode in ('reverb_talk', 'normal_talk')
        label = '混响说话' if was_reverb else '普通说话'
        had_timeline = self.state.playback_running and was_talk
        if had_timeline or (handoff and self.state.playback_running):
            self._halt_playback_tick(wait=0.25 if handoff else 0.4)
        self.audio.stop_stream()
        if handoff:
            time.sleep(0.25)
        else:
            time.sleep(0.03)
        self.state.passthrough_running = False
        if had_timeline and not handoff:
            self.state.playback_running = False
            if self.state.lyrics_running:
                self.lyrics.stop()
                self.state.lyrics_running = False
        if self._is_talk_mode() and not handoff:
            self.state.mode = 'idle'
        if not handoff:
            self._publish_status('passthrough_stopped', log='%s已停止' % label)

    def _stop_playback_all(self, payload=None):
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            self.stop_ai_follow()
        if self._is_talk_mode():
            self.stop_passthrough()
        self._stop_playback(payload)

    def _scan_library_blocking(self):
        opt_dir = self.config_store.get('paths.opt_dir', 'opt')
        dirs = [opt_dir, str(Path(opt_dir) / 'task4_offline')]
        self._library = scan_song_library(self.project_root, dirs=dirs)

    def _refresh_library(self):
        def _work():
            try:
                self._scan_library_blocking()
                self._publish_status('library_updated', songs=self._library, log='歌库已刷新（%s 首）' % len(self._library))
            except Exception:
                logger.error('library refresh failed:\n%s', traceback.format_exc())
        threading.Thread(target=_work, name='library-scan', daemon=True).start()

    def _is_timeline_playing(self) -> bool:
        if self.state.ai_follow_running:
            pf = self._pitch_follow
            return pf is not None and pf.running
        if self.state.mode in ('reverb_talk', 'normal_talk'):
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                return mgr.inst_playing and not mgr.inst_paused
            return False
        if self.state.mode == 'ai_sing':
            return self._player.is_playing
        return False

    def _with_autoplay(self, payload=None) -> dict:
        p = dict(payload or {})
        if 'autoplay' not in p:
            p['autoplay'] = self._is_timeline_playing()
        return p

    def _has_paused_session(self) -> bool:
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.state.passthrough_running:
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                return mgr.inst_paused and mgr.inst_playing
            return False
        if self.state.mode == 'ai_sing' and self._player.is_active:
            return not self._player.is_playing
        return False

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
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            self.stop_ai_follow()
            self._publish_status('playback_paused', playing=False, paused=True)
            return
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.audio.manager and self.audio.manager.inst_duration > 0:
            if self.audio.manager.inst_paused:
                return
            self.audio.manager.toggle_inst_pause()
            pos, dur, playing, paused = self._reverb_inst_state()
            self.state.playback_running = playing
            self._publish_status('playback_paused', playing=playing, paused=paused, position=pos, duration=dur)
            self._publish_status('playback_tick', position=pos, duration=dur, playing=playing, paused=paused)
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
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.audio.manager and self.audio.manager.inst_duration > 0:
            if not self.audio.manager.inst_paused:
                return
            self.audio.manager.toggle_inst_pause()
            pos, dur, playing, paused = self._reverb_inst_state()
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
            self._resume_timeline()
            return
        mode = self.state.selected_mode if self.state.selected_mode in MODE_IDS else 'ai_sing'
        self._apply_mode(mode, autoplay=True)

    def _active_playback_mode(self) -> str:
        if not self._is_timeline_playing():
            return ''
        if self.state.ai_follow_running or self.state.ai_follow_preparing or self.state.mode == 'ai_follow':
            return 'ai_follow'
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.state.passthrough_running:
            return self.state.mode
        if self.state.mode == 'ai_sing' or (self.state.playback_running and self._player.is_active):
            return 'ai_sing'
        return ''

    def _select_song(self, payload: dict):
        payload = payload or {}
        song = payload.get('song') or payload or {}
        if not song.get('play_path'):
            return
        prev = self.state.selected_song or {}
        prev_id = prev.get('id') or prev.get('play_path')
        new_id = song.get('id') or song.get('play_path')
        switching = bool(prev_id and new_id and prev_id != new_id)
        resume_if_playing = payload.get('resume_if_playing', True)
        self.state.selected_song = dict(song)
        lrc = song.get('lrc_path') or find_lrc_in_dir(song.get('dir') or Path(song.get('play_path', '')).parent, song.get('title', ''))
        if lrc and Path(lrc).is_file():
            prev_lrc = self.lyrics._loaded_path
            self.lyrics.load_lrc(lrc)
            self.state.loaded_lyrics = True
            self.state.selected_song['lrc_path'] = lrc
            if switching or self.lyrics._loaded_path != prev_lrc:
                doc = self.lyrics.document
                self._publish_status(
                    'lyrics_loaded',
                    lines=[ln.text for ln in doc.lines],
                    log='已加载歌词：%s（%s 行）' % (doc.title or song.get('title', ''), len(doc.lines)),
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
        if resume_if_playing and switching:
            mode = self._active_playback_mode()
            if mode:
                title = song.get('title') or Path(song.get('play_path') or '').stem
                self._inst_end_sent = False
                self._continue_mode_with_song(mode, dict(self.state.selected_song), 0.0)
                self._publish_status('track_advance', title=title, log='切换歌曲：%s' % title)
                return
        threading.Thread(
            target=self._preload_song_assets,
            args=(dict(self.state.selected_song),),
            name='song-preload',
            daemon=True,
        ).start()

    def _preload_song_assets(self, song: dict):
        try:
            self._sync_playback_output_device()
            play_path = song.get('play_path') or song.get('cover_path')
            if play_path and Path(play_path).is_file():
                if str(play_path) != self._player.path or not self._player.is_active:
                    self._player.load(str(play_path))
            if song.get('instrumental_path') and song.get('vocal_path'):
                self.pitch_follow.preload(song)
        except Exception:
            logger.debug('song preload failed:\n%s', traceback.format_exc())

    def _sync_playback_output_device(self):
        audio = self.config_store.get('audio', {}) or {}
        dev = audio.get('output_device')
        self._player.set_output_device(dev)
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
        if self.state.ai_follow_running or self.state.ai_follow_preparing:
            pf = self._pitch_follow
            if pf is not None and pf.duration > 0:
                return pf.position
        if self._is_talk_mode() and self.audio.manager and self.audio.manager.inst_duration > 0:
            return self.audio.manager.inst_position
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

    def _start_ai_sing(self, payload: dict):
        self._dispatch_mode_switch(self._start_ai_sing_impl, self._with_autoplay(payload))

    def _start_ai_sing_impl(self, payload: dict):
        if self.state.offline_running:
            self._publish_status('playback_blocked', log='离线做歌进行中，请稍后再播放')
            return
        payload = payload or {}
        autoplay = bool(payload.get('autoplay', True))
        explicit_pos = 'position' in payload
        carry_pos = float(payload.get('position', 0) or 0)
        from_inst_dur = 0.0
        reverb_handoff = False
        if self.state.mode == 'reverb_talk':
            reverb_handoff = True
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                carry_pos = mgr.inst_position
                from_inst_dur = mgr.inst_duration
            logger.info('ai_sing handoff from reverb pos=%.2fs inst_dur=%.2fs', carry_pos, from_inst_dur)
            self.stop_passthrough(handoff=True)
            self._player.stop()
            time.sleep(0.15)
            logger.info('ai_sing reverb stream released')
        elif self.state.passthrough_running:
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                carry_pos = mgr.inst_position
                from_inst_dur = mgr.inst_duration
            logger.info('ai_sing handoff from talk pos=%.2fs mode=%s', carry_pos, self.state.mode)
            self.stop_passthrough(handoff=True)
            self._player.stop()
            time.sleep(0.15)
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
            time.sleep(0.15)
            logger.info('ai_sing handoff from follow pos=%.2fs', carry_pos)
        song = (payload or {}).get('song') or self.state.selected_song or {}
        play_path = song.get('play_path') or song.get('cover_path') or song.get('vocal_path')
        if not play_path:
            self._publish_error('请先在歌库选择已生成的 AI 歌曲（需 cover.wav 或 converted_vocal.wav）')
            return
        if self.state.realtime_running:
            self.stop_realtime()
        self._select_song({'song': song})
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
            if self.state.mode in ('reverb_talk', 'normal_talk') and self.audio.manager and self.audio.manager.inst_duration > 0:
                stuck = 0
                pos, dur, playing, paused = self._reverb_inst_state()
                mgr = self.audio.manager
                if mgr.inst_finished and not mgr.inst_paused and not self._inst_end_sent:
                    self._inst_end_sent = True
                    if self._handle_track_end():
                        break
                self.lyrics.sync_at(pos)
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=dur,
                    playing=playing,
                    paused=paused,
                )
            elif self._player.is_active:
                stuck = 0
                pos = self._player.position
                self.lyrics.sync_at(pos)
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=self._player.duration,
                    playing=self._player.is_playing,
                    paused=not self._player.is_playing and self._player.is_active,
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
            if self._playback_stop.wait(0.1) or self._tick_generation != gen:
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
        library = self._library or []
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
        payload = {'song': song, 'position': carry_pos, 'autoplay': autoplay}
        if mode == 'ai_sing':
            self._start_ai_sing_impl(payload)
        elif mode == 'ai_follow':
            self.stop_ai_follow(handoff=True)
            time.sleep(0.1)
            self._start_ai_follow(payload)
        elif mode == 'reverb_talk':
            if self.state.passthrough_running:
                self.stop_passthrough(handoff=True)
            time.sleep(0.1)
            self._start_talk(payload, mode='reverb_talk')
        elif mode == 'normal_talk':
            if self.state.passthrough_running:
                self.stop_passthrough(handoff=True)
            time.sleep(0.1)
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
            if mode == 'repeat_one' and cur_mode in ('reverb_talk', 'normal_talk'):
                mgr = self.audio.manager
                if mgr is not None and mgr.inst_duration > 0:
                    mgr.replay_instrumental()
                    self._inst_end_sent = False
                    self._ensure_playback_lyrics(0)
                    pos, dur, playing, paused = self._reverb_inst_state()
                    self._publish_status(
                        'playback_tick',
                        position=pos,
                        duration=dur,
                        playing=playing,
                        paused=paused,
                    )
                    self._publish_status('track_advance', title=title, log='单曲循环：%s' % title)
                    return True
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
        if self.state.ai_follow_running and self._pitch_follow is not None and self._pitch_follow.duration > 0:
            self._pitch_follow.seek(ratio * self._pitch_follow.duration)
            self.lyrics.sync_at(self._pitch_follow.position, force=True)
            return
        if self.state.mode in ('reverb_talk', 'normal_talk') and self.audio.manager and self.audio.manager.inst_duration > 0:
            self.audio.manager.seek_instrumental(ratio * self.audio.manager.inst_duration)
            self.lyrics.sync_at(self.audio.manager.inst_position, force=True)
            pos, dur, playing, paused = self._reverb_inst_state()
            self._publish_status(
                'playback_tick',
                position=pos,
                duration=dur,
                playing=playing,
                paused=paused,
            )
            return
        if not self._player.is_active or self._player.duration <= 0:
            return
        self._player.seek_ratio(ratio)
        self.lyrics.sync_at(self._player.position, force=True)

    def _stop_playback(self, payload=None, handoff=False):
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
                detune_mode=p.get('detune_mode'),
            )
        self._schedule_config_save()

    def _release_playback_source(self, handoff: bool = True) -> float:
        pos = self._current_song_position()
        if self.state.mode in ('reverb_talk', 'normal_talk') or (
            self.state.passthrough_running and self.audio.manager and self.audio.manager.inst_duration > 0
        ):
            mgr = self.audio.manager
            if mgr is not None and mgr.inst_duration > 0:
                pos = mgr.inst_position
            self.stop_passthrough(handoff=handoff)
            time.sleep(0.15)
        elif self.state.ai_follow_running or self.state.ai_follow_preparing:
            pf = self._pitch_follow
            if pf is not None and pf.duration > 0:
                pos = pf.position
            self.stop_ai_follow(handoff=handoff)
            time.sleep(0.15)
        elif self.state.mode == 'ai_sing' or (self.state.playback_running and self._player.is_active):
            if self._player.duration > 0 or self._player.is_active:
                pos = self._player.position
            self._stop_playback(handoff=handoff)
            time.sleep(0.15)
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
            log='AI 跟唱已启动：%s%s\n对着麦克风唱，系统将按 AI 人声旋律修音\n输出=伴奏+修音人声（请在设置中核对音频设备）' % (title, hint),
        )

    def _start_ai_follow(self, payload: dict):
        payload = payload or {}
        autoplay = bool(payload.get('autoplay', True))
        explicit_pos = 'position' in payload
        carry_pos = float(payload.get('position', 0) or 0)
        need_release = (
            self.state.passthrough_running
            or self.state.ai_follow_running
            or self.state.ai_follow_preparing
            or self.state.mode == 'ai_sing'
            or (self.state.playback_running and self._player.is_active)
        )
        if need_release:
            released = self._release_playback_source(handoff=True)
            if not explicit_pos and carry_pos <= 0:
                carry_pos = released
        elif not explicit_pos and carry_pos <= 0:
            carry_pos = self._current_song_position()
        handoff_dur = self._player.duration if self.state.playback_running and self._player.duration > 0 else 0.0
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
        ref_path = song.get('vocal_path') or ''
        cache_hit = bool(ref_path and Path(ref_path).with_suffix('.f0.npz').is_file())
        self.state.ai_follow_preparing = True
        self._follow_prepare_cancel.clear()
        self._publish_status(
            'ai_follow_preparing',
            title=song.get('title', ''),
            position=carry_pos,
            duration=tick_dur,
            playing=self.state.playback_running,
            paused=not self.state.playback_running,
            log='正在加载伴奏…' if cache_hit else '正在加载伴奏并分析旋律（首次较慢）…',
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
                    self.lyrics.tick_at(pos)
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
                if self._follow_stop.wait(0.25):
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
        self.lyrics.load_lrc(path, offset_ms=(payload or {}).get('offset_ms'))
        self.state.loaded_lyrics = True
        if self._lyrics_window:
            self._lyrics_window.show()
        doc = self.lyrics.document
        lines = [ln.text for ln in doc.lines]
        self._publish_status(
            'lyrics_loaded',
            lines=lines,
            log='已加载歌词：%s（%s 行）' % (doc.title or Path(path).name, len(doc.lines)),
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
                        result_dict['lrc_path'] = str(out_lrc.resolve())
                    except Exception as exc:
                        logger.warning('copy lrc failed: %s', exc)
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
        from app.ops.updater import check_update

        url = self.config_store.get('update.check_url', '')
        if not url:
            self._publish_status('update_skip', log='未配置 update.check_url')
            return
        info = check_update(url)
        self._publish_status('update_checked', log='更新检查：%s' % (info.get('message') or info.get('latest_version')))

    def _save_settings(self, payload: dict):
        payload = payload or {}
        audio = payload.get('audio') or {}
        for key in ('hostapi', 'wasapi_exclusive', 'input_device', 'output_device', 'sample_rate', 'passthrough_gain', 'passthrough_ui'):
            if key in audio:
                self.config_store.set('audio.%s' % key, audio[key])
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
        if payload.get('update_url') is not None:
            self.config_store.set('update.check_url', str(payload['update_url']).strip())
        if payload.get('log_dir'):
            self.config_store.set('paths.log_dir', str(payload['log_dir']).strip())
        if payload.get('sr_type'):
            self.config_store.set('realtime.sr_type', str(payload['sr_type']))
        shortcuts = payload.get('shortcuts') or {}
        for key, val in shortcuts.items():
            self.config_store.set('shortcuts.%s' % key, str(val or '').strip())
        self.config_store.save()
        self._sync_playback_output_device()
        mgr = self.audio.manager
        if mgr and mgr.running and mgr.config.passthrough:
            from app.audio.service import passthrough_gain_from_audio
            merged = dict(self.config_store.get('audio', {}) or {})
            mgr.config.passthrough_gain = passthrough_gain_from_audio(merged)
        hint = ''
        if self.state.passthrough_running or self.state.realtime_running:
            hint = '（请重新开启普通说话/混响说话/AI 跟唱使新设备生效）'
        self._publish_status('settings_saved', log='音频与系统设置已写入 config/client.json%s' % hint)

    def _test_mic(self, payload=None):
        payload = payload or {}
        if payload.get('stop'):
            if self._is_talk_mode():
                self.stop_passthrough()
            return
        if self._is_talk_mode():
            return
        self._start_talk(payload, mode='normal_talk')
