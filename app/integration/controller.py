"""任务 7：全模块集成控制器（仅路由与生命周期，不含业务实现）。"""

import logging
import shutil
import threading
import traceback
from pathlib import Path

from app.audio import AudioService
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

logger = logging.getLogger('rvc_client.integration')
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        self._bridge = None
        self._lyrics_window = None
        self._offline_thread = None
        self._offline_pipeline = None
        self._player = WavPlayer()
        self._playback_tick = None
        self._playback_stop = threading.Event()
        self._library = []
        self._started = False
        self._lock = threading.RLock()

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
        self._refresh_library()
        self._publish_status('controller_ready', log='集成控制器已就绪')
        return self

    def shutdown(self):
        with self._lock:
            self._stop_playback()
            self.stop_realtime()
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
            'playback_refresh_library': lambda p: self._refresh_library(),
            'playback_select_song': self._select_song,
            'playback_ai_sing': self._start_ai_sing,
            'playback_toggle_pause': self._toggle_playback_pause,
            'playback_stop': lambda p: self._stop_playback(),
            'playback_seek': self._seek_playback,
            'playback_ai_follow': self._start_ai_follow,
            'realtime_start': self._start_ai_follow,
            'realtime_stop': self.stop_realtime,
            'playback_reverb_talk': lambda p: self._start_passthrough('混响说话'),
            'playback_normal_talk': lambda p: self._start_passthrough('普通说话'),
            'ai_toggle': self._toggle_ai,
            'lyrics_load': self._load_lyrics,
            'lyrics_start': lambda p: self.lyrics.start(source=(p or {}).get('clock_source')),
            'lyrics_stop': lambda p: self.lyrics.stop(),
            'lyrics_set_offset': lambda p: self.lyrics.set_offset_ms(int((p or {}).get('offset_ms', 0))),
            'check_update': self._check_update,
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

    def _start_passthrough(self, label: str, payload=None):
        self._stop_playback()
        if self.state.realtime_running:
            self.stop_realtime()
        self.audio.start_stream(passthrough=True)
        self.state.mode = 'passthrough'
        self._publish_status('passthrough_started', log='%s：音频直通已启动（未经 RVC）' % label)

    def _refresh_library(self):
        opt_dir = self.config_store.get('paths.opt_dir', 'opt')
        dirs = [opt_dir, str(Path(opt_dir) / 'task4_offline')]
        self._library = scan_song_library(self.project_root, dirs=dirs)
        self._publish_status('library_updated', songs=self._library, log='歌库已刷新（%s 首）' % len(self._library))

    def _select_song(self, payload: dict):
        song = (payload or {}).get('song') or payload or {}
        if not song.get('play_path'):
            return
        self.state.selected_song = dict(song)
        lrc = song.get('lrc_path') or find_lrc_in_dir(song.get('dir') or Path(song.get('play_path', '')).parent, song.get('title', ''))
        if lrc and Path(lrc).is_file():
            self.lyrics.load_lrc(lrc)
            self.state.loaded_lyrics = True
            self.state.selected_song['lrc_path'] = lrc
            doc = self.lyrics.document
            self._publish_status(
                'lyrics_loaded',
                lines=[ln.text for ln in doc.lines],
                log='已加载歌词：%s（%s 行）' % (doc.title or song.get('title', ''), len(doc.lines)),
            )
        else:
            self.state.loaded_lyrics = False
            hint = Path(lrc).name if lrc else '%s.lrc' % song.get('title', '')
            self._publish_status('lyrics_missing', log='未找到歌词文件（期望同名 %s），仅播放音频' % hint)

    def _start_ai_sing(self, payload: dict):
        if self.state.offline_running:
            self._publish_status('playback_blocked', log='离线做歌进行中，请稍后再播放')
            return
        song = (payload or {}).get('song') or self.state.selected_song or {}
        play_path = song.get('play_path') or song.get('cover_path') or song.get('vocal_path')
        if not play_path:
            self._publish_error('请先在歌库选择已生成的 AI 歌曲（需 cover.wav 或 converted_vocal.wav）')
            return
        if self.state.realtime_running:
            self.stop_realtime()
        self._select_song({'song': song})
        self._stop_playback()
        try:
            duration = self._player.load(play_path)
        except Exception as exc:
            self._publish_error('无法加载音频: %s' % exc, exc)
            return
        self.state.playback_running = True
        self.state.mode = 'ai_sing'
        self.lyrics.start(source='manual')
        self.state.lyrics_running = True
        self._playback_stop.clear()
        self._playback_tick = threading.Thread(target=self._playback_tick_loop, name='playback-tick', daemon=True)
        self.scheduler.register_thread('playback-tick', self._playback_tick)
        self._playback_tick.start()
        self._player.play(on_finish=self._on_playback_finished)
        title = song.get('title') or Path(play_path).stem
        self._publish_status(
            'playback_started',
            title=title,
            play_path=play_path,
            duration=duration,
            position=0.0,
            playing=True,
            paused=False,
            log='AI 唱歌：正在播放 %s' % title,
        )
        self._publish_status(
            'playback_tick',
            position=0.0,
            duration=duration,
            playing=True,
            paused=False,
        )

    def _playback_tick_loop(self):
        while not self._playback_stop.is_set():
            if self._player.is_active:
                pos = self._player.position
                self.lyrics.set_manual_time(pos)
                self._publish_status(
                    'playback_tick',
                    position=pos,
                    duration=self._player.duration,
                    playing=self._player.is_playing,
                    paused=not self._player.is_playing and self._player.is_active,
                )
            if self._playback_stop.wait(0.1):
                break

    def _on_playback_finished(self):
        self.scheduler.publish(
            BusMessage(
                SignalType.STATUS,
                ModuleId.SCHEDULER,
                {'action': 'playback_finished', 'log': 'AI 唱歌播放完成'},
            )
        )
        self._stop_playback()

    def _toggle_playback_pause(self, payload=None):
        if not self.state.playback_running:
            if self.state.selected_song:
                self._start_ai_sing({'song': self.state.selected_song})
            else:
                self._publish_status('playback_idle', log='请先选择歌曲')
            return
        resumed = self._player.toggle_pause()
        self._publish_status(
            'playback_paused' if not resumed else 'playback_resumed',
            playing=resumed,
            paused=not resumed,
            position=self._player.position,
            duration=self._player.duration,
        )
        self._publish_status(
            'playback_tick',
            position=self._player.position,
            duration=self._player.duration,
            playing=resumed,
            paused=not resumed,
        )

    def _seek_playback(self, payload: dict):
        ratio = float((payload or {}).get('ratio', 0))
        if not self._player.is_active or self._player.duration <= 0:
            return
        self._player.seek_ratio(ratio)
        self.lyrics.set_manual_time(self._player.position)

    def _stop_playback(self, payload=None):
        self._playback_stop.set()
        self._player.stop()
        if self._playback_tick and self._playback_tick.is_alive():
            self._playback_tick.join(timeout=1.0)
        self._playback_tick = None
        self.scheduler.unregister_thread('playback-tick')
        if self.state.mode == 'ai_sing':
            self.lyrics.stop()
            self.state.lyrics_running = False
            self.state.mode = 'idle'
        self.state.playback_running = False
        self._publish_status('playback_stopped', log='播放已停止')

    def _toggle_ai(self, payload=None):
        if self.state.realtime_running:
            self.stop_realtime()
        else:
            self._start_ai_follow(payload or {})

    def _start_ai_follow(self, payload: dict):
        if self.state.playback_running:
            self._stop_playback()
        if self.state.offline_running:
            self._publish_status('realtime_blocked', log='离线任务进行中，请稍后再启动 AI 跟唱')
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
        if self.state.loaded_lyrics and not self.lyrics.running:
            clock = self.config_store.get('lyrics.clock_source', 'osc')
            self.lyrics.start(source=clock)
            self.state.lyrics_running = True
        self._publish_status(
            'realtime_started',
            model_sid=model_sid,
            log='AI 跟唱已启动（模型 %s）\n音频 IN: %s\n音频 OUT: %s'
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

    def stop_realtime(self, payload=None):
        if self._realtime is not None:
            self._realtime.stop()
        self.audio.stop_stream()
        self.state.realtime_running = False
        if self.state.mode in ('realtime', 'passthrough'):
            self.state.mode = 'idle'
        self._publish_status('realtime_stopped', log='AI 跟唱/直通已停止')

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
        thread.start()
        self._publish_status('offline_started', log='离线做歌已开始…')

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
            elif terminal:
                msg = terminal.get('message') or terminal.get('event') or 'offline failed'
                detail = (terminal.get('detail') or '').strip()
                if detail and detail not in msg:
                    msg = '%s\n%s' % (msg, detail[:2000])
                self._publish_status('offline_failed', message=msg)
                self._publish_error(msg)
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
