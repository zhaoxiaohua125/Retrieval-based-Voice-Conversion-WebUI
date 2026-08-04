"""任务 7：全模块集成控制器（仅路由与生命周期，不含业务实现）。"""

import logging
import threading
import traceback
from pathlib import Path

from app.audio import AudioService
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.integration.state import ClientState
from app.lyrics import LyricsService
from app.ops.exceptions import classify_exception
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
            'playback_ai_follow': self._start_ai_follow,
            'realtime_start': self._start_ai_follow,
            'realtime_stop': self.stop_realtime,
            'playback_ai_sing': lambda p: self._publish_status('playback_ai_sing', log='AI 唱歌：请使用离线做歌生成人声后播放'),
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
        if self.state.realtime_running:
            self.stop_realtime()
        self.audio.start_stream(passthrough=True)
        self.state.mode = 'passthrough'
        self._publish_status('passthrough_started', log='%s：音频直通已启动（未经 RVC）' % label)

    def _toggle_ai(self, payload=None):
        if self.state.realtime_running:
            self.stop_realtime()
        else:
            self._start_ai_follow(payload or {})

    def _start_ai_follow(self, payload: dict):
        if self.state.offline_running:
            self._publish_status('realtime_blocked', log='离线任务进行中，请稍后再启动 AI 跟唱')
            return
        model_sid = (payload or {}).get('model_sid') or self.config_store.get('realtime.model_sid') or discover_first_model(self.project_root)
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
        self._publish_status('realtime_started', model_sid=model_sid, log='AI 跟唱已启动（模型 %s）' % model_sid)

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
        self._publish_status('lyrics_loaded', log='已加载歌词：%s（%s 行）' % (doc.title or Path(path).name, len(doc.lines)))

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
                self._publish_status('offline_finished', log='离线做歌完成：%s' % (cover or output_dir))
            elif terminal:
                self._publish_error(terminal.get('message') or terminal.get('event') or 'offline failed')
        except Exception as exc:
            logger.error('offline worker failed:\n%s', traceback.format_exc())
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
