"""实时 RVC 服务：音频环形缓冲 ↔ 推理线程 ↔ AppScheduler。"""

import logging
import threading
import time
import traceback

from app.audio import AudioService, AudioStreamConfig, AudioStreamManager
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.rvc.realtime_config import RealtimeRvcConfig
from app.rvc.realtime_engine import RealtimeModelPool, RealtimeRvcEngine
from app.rvc.vc_context import discover_first_model
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client.rvc.realtime')


class RealtimeRvcService:
    """任务 4B：管理实时推理线程与模型池。"""

    def __init__(
        self,
        scheduler: AppScheduler | None = None,
        audio: AudioService | None = None,
        config: ConfigStore | None = None,
        project_root=None,
    ):
        self.scheduler = scheduler or AppScheduler.instance()
        self.audio = audio or AudioService(self.scheduler, config)
        self.config_store = config or ConfigStore().load()
        self.project_root = project_root
        self.pool = RealtimeModelPool(project_root=project_root)
        self._worker: threading.Thread | None = None
        self._running = False
        self._hook_registered = False

    def _publish(self, signal: SignalType, payload: dict):
        self.scheduler.publish(BusMessage(signal, ModuleId.RVC, payload))

    def _ensure_hooks(self):
        if self._hook_registered:
            return
        self.scheduler.add_shutdown_hook(self.stop)
        self._hook_registered = True

    def _load_cfg(self) -> RealtimeRvcConfig:
        rvc = self.config_store.get('rvc', {}) or {}
        audio = self.config_store.get('audio', {}) or {}
        rt = self.config_store.get('realtime', {}) or {}
        return RealtimeRvcConfig(
            model_sid=str(rt.get('model_sid') or rvc.get('model_sid') or ''),
            index_path=str(rt.get('index_path') or ''),
            pitch=int(rt.get('pitch', rvc.get('f0_up_key', 0))),
            formant=float(rt.get('formant', rvc.get('formant', 0.0))),
            index_rate=float(rt.get('index_rate', rvc.get('index_rate', 0.0))),
            f0_method=str(rt.get('f0_method', rvc.get('f0_method', 'rmvpe'))),
            block_time=float(rt.get('block_time', 0.25)),
            crossfade_time=float(rt.get('crossfade_time', 0.05)),
            extra_time=float(rt.get('extra_time', 2.5)),
            sample_rate=int(audio.get('sample_rate', 48000)),
            sr_type=str(rt.get('sr_type', 'sr_model')),
            channels=int(audio.get('channels', 1)),
        )

    def start(self, model_sid: str | None = None, use_audio: bool = True):
        self._ensure_hooks()
        if self._running:
            return self.active_engine
        cfg = self._load_cfg()
        self.pool.cfg = cfg
        sid = model_sid or cfg.model_sid or discover_first_model(project_root=self.project_root)
        if not sid:
            raise RuntimeError('未找到 RVC 模型，请放入 assets/weights/*.pth')
        engine = self.pool.preload(sid)
        engine.start(sample_rate=cfg.sample_rate)
        if use_audio:
            audio_cfg = self.audio.load_stream_config()
            audio_cfg.passthrough = False
            self.audio.manager = AudioStreamManager(audio_cfg)
            self.audio.manager.start()
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, name='realtime-rvc', daemon=True)
        self.scheduler.register_thread('realtime-rvc', self._worker)
        self._worker.start()
        self._publish(
            SignalType.STATUS,
            {'action': 'realtime_started', 'model_sid': sid, 'block_frame': engine.block_frame},
        )
        return engine

    def stop(self):
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3.0)
        self._worker = None
        self.scheduler.unregister_thread('realtime-rvc')
        if self.pool.active_engine:
            self.pool.active_engine.stop()
        if self.audio.manager:
            self.audio.stop_stream()
        self._publish(SignalType.STATUS, {'action': 'realtime_stopped', 'stats': self.stats()})

    @property
    def active_engine(self) -> RealtimeRvcEngine | None:
        return self.pool.active_engine

    def switch_model(self, model_sid: str):
        engine = self.pool.switch(model_sid)
        if not engine.ready:
            engine.start(sample_rate=self.pool.cfg.sample_rate)
        self._publish(SignalType.STATUS, {'action': 'realtime_model_switched', 'model_sid': model_sid})

    def stats(self):
        engine = self.active_engine
        data = {'running': self._running, 'loaded_models': self.pool.list_loaded()}
        if engine:
            data['engine'] = engine.stats
        if self.audio.manager:
            data['audio'] = self.audio.manager.stats
        return data

    def _worker_loop(self):
        engine = self.active_engine
        mgr = self.audio.manager
        pending = None
        while self._running:
            try:
                engine = self.active_engine
                if engine is None or not engine.ready:
                    time.sleep(0.01)
                    continue
                need = engine.block_frame
                if mgr is None:
                    time.sleep(0.05)
                    continue
                while mgr.input_ring.available_frames() < need and self._running:
                    time.sleep(0.002)
                block = mgr.input_ring.read(need)
                if block.ndim == 2 and block.shape[1] > 1:
                    block = block.mean(axis=1, keepdims=True)
                out = engine.process_block(block[:, 0] if block.ndim == 2 else block)
                mgr.push_output(out.reshape(-1, 1))
            except Exception:
                logger.error('realtime worker error:\n%s', traceback.format_exc())
                self._publish(SignalType.ERROR, {'action': 'realtime_worker_error', 'detail': traceback.format_exc()})
                time.sleep(0.05)

    def attach_scheduler(self):
        def on_status(msg: BusMessage):
            if msg.source == ModuleId.RVC:
                return
            action = (msg.payload or {}).get('action')
            if action == 'realtime_start':
                self.start(model_sid=(msg.payload or {}).get('model_sid'))
            elif action == 'realtime_stop':
                self.stop()
            elif action == 'realtime_switch_model':
                self.switch_model((msg.payload or {}).get('model_sid'))

        self.scheduler.subscribe(SignalType.STATUS, on_status)
        self._ensure_hooks()
        return self

    def process_offline_blocks(self, blocks: list, model_sid: str | None = None) -> list:
        """无音频设备时的块级推理（测试/验收用）。"""
        cfg = self._load_cfg()
        self.pool.cfg = cfg
        sid = model_sid or cfg.model_sid or discover_first_model(project_root=self.project_root)
        if not sid:
            raise RuntimeError('未找到 RVC 模型')
        engine = self.pool.preload(sid)
        engine.start(sample_rate=cfg.sample_rate)
        outputs = []
        try:
            for block in blocks:
                outputs.append(engine.process_block(block))
        finally:
            engine.stop()
        return outputs
