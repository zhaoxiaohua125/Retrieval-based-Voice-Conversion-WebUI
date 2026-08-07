"""音频服务：对接 AppScheduler，统一管理设备与流生命周期。"""

import logging
from dataclasses import asdict

from app.audio.devices import device_summary, list_devices
from app.audio.stream_manager import AudioStreamConfig, AudioStreamManager
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client.audio')


def passthrough_gain_from_audio(audio: dict) -> float:
    ui = audio.get('passthrough_ui')
    if ui is not None:
        return max(0.5, min(4.0, int(ui) / 50.0))
    return max(0.5, min(4.0, float(audio.get('passthrough_gain', 2.0))))


def inst_gain_from_config(config_store: ConfigStore) -> float:
    pf = config_store.get('pitchfix', {}) or {}
    if pf.get('inst_gain') is not None:
        return float(pf['inst_gain'])
    if pf.get('inst_ui') is not None:
        return int(pf['inst_ui']) / 100.0
    return 0.77


class AudioService:
    """任务 3 音频 IO 门面：枚举设备、启停采集流。"""

    def __init__(self, scheduler: AppScheduler | None = None, config: ConfigStore | None = None):
        self.scheduler = scheduler or AppScheduler.instance()
        self.config_store = config or ConfigStore().load()
        self.manager: AudioStreamManager | None = None
        self._hook_registered = False

    def _publish(self, signal: SignalType, payload: dict):
        self.scheduler.publish(BusMessage(signal, ModuleId.AUDIO, payload))

    def _ensure_shutdown_hook(self):
        if self._hook_registered:
            return
        self.scheduler.add_shutdown_hook(self.stop_stream)
        self._hook_registered = True

    def load_stream_config(self) -> AudioStreamConfig:
        audio = self.config_store.get('audio', {}) or {}
        return AudioStreamConfig(
            sample_rate=int(audio.get('sample_rate', 48000)),
            block_ms=int(audio.get('block_ms', 200)),
            channels=int(audio.get('channels', 1)),
            dtype=str(audio.get('dtype', 'float32')),
            input_device=audio.get('input_device'),
            output_device=audio.get('output_device'),
            hostapi=audio.get('hostapi'),
            wasapi_exclusive=bool(audio.get('wasapi_exclusive', False)),
            ring_ms=int(audio.get('ring_ms', 500)),
            passthrough=bool(audio.get('passthrough', False)),
            passthrough_gain=passthrough_gain_from_audio(audio),
            passthrough_reverb=False,
            reverb_mix=float(audio.get('reverb_mix', 0.35)),
            reverb_decay=float(audio.get('reverb_decay', 0.72)),
        )

    def save_device_selection(self, input_device: int, output_device: int, hostapi: str | None = None):
        self.config_store.set('audio.input_device', input_device)
        self.config_store.set('audio.output_device', output_device)
        if hostapi:
            self.config_store.set('audio.hostapi', hostapi)
        self.config_store.save()
        self._publish(SignalType.CONFIG_CHANGED, {'section': 'audio', 'input_device': input_device, 'output_device': output_device})

    def list_devices(self, hostapi: str | None = None):
        host = hostapi or self.config_store.get('audio.hostapi')
        devices = list_devices(hostapi=host)
        summary = device_summary(devices)
        self._publish(SignalType.STATUS, {'action': 'devices_listed', 'summary': summary, 'devices': [d.to_dict() for d in devices]})
        return devices

    def start_stream(
        self,
        passthrough: bool | None = None,
        reverb: bool = False,
        inst_path: str | None = None,
        inst_seek: float = 0.0,
    ):
        self._ensure_shutdown_hook()
        cfg = self.load_stream_config()
        if passthrough is not None:
            cfg.passthrough = passthrough
        cfg.passthrough_reverb = bool(reverb)
        if cfg.passthrough:
            audio = self.config_store.get('audio', {}) or {}
            cfg.block_ms = int(audio.get('passthrough_block_ms', 50))
            cfg.reverb_mix = float(audio.get('reverb_mix', 0.35))
            cfg.reverb_decay = float(audio.get('reverb_decay', 0.72))
            cfg.inst_gain = inst_gain_from_config(self.config_store)
        if self.manager and self.manager.running:
            same = (
                self.manager.config.passthrough == cfg.passthrough
                and self.manager.config.passthrough_reverb == cfg.passthrough_reverb
            )
            if same and not inst_path:
                self.manager.config.passthrough_gain = cfg.passthrough_gain
                self.manager.config.reverb_mix = cfg.reverb_mix
                self.manager.config.reverb_decay = cfg.reverb_decay
                self.manager.config.inst_gain = cfg.inst_gain
                if cfg.passthrough:
                    self.manager.config.block_ms = cfg.block_ms
                return self.manager
            self.stop_stream()
        self.manager = AudioStreamManager(cfg)
        if inst_path:
            self.manager.load_instrumental(inst_path, inst_seek)
        self.manager.start()
        self._publish(
            SignalType.STATUS,
            {
                'action': 'stream_started',
                'input_device': self.manager.config.input_device,
                'output_device': self.manager.config.output_device,
                'config': asdict(cfg),
            },
        )
        return self.manager

    def stop_stream(self):
        if self.manager is None:
            return
        try:
            stats = self.manager.stats
            self.manager.stop()
            self._publish(SignalType.STATUS, {'action': 'stream_stopped', 'stats': stats})
        finally:
            self.manager = None

    def attach_scheduler(self):
        """订阅 UI/调度控制消息。"""

        def on_status(msg: BusMessage):
            if msg.source == ModuleId.AUDIO:
                return
            payload = msg.payload or {}
            action = payload.get('action')
            if action == 'audio_list_devices':
                self.list_devices(payload.get('hostapi'))
            elif action == 'audio_start_stream':
                self.start_stream(passthrough=payload.get('passthrough'))
            elif action == 'audio_stop_stream':
                self.stop_stream()

        self.scheduler.subscribe(SignalType.STATUS, on_status)
        self._ensure_shutdown_hook()
        return self
