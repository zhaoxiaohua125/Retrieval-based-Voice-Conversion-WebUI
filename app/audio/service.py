"""音频服务：对接 AppScheduler，统一管理设备与流生命周期。"""

import logging
from dataclasses import asdict
from pathlib import Path

from app.audio.devices import device_summary, list_devices
from app.audio.stream_manager import PLAYBACK_MODES, AudioStreamConfig, AudioStreamManager
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


def pitchfix_mix_from_config(config_store: ConfigStore) -> dict:
    pf = config_store.get('pitchfix', {}) or {}
    mic_gain = float(pf['mic_gain']) if pf.get('mic_gain') is not None else (
        int(pf['mic_ui']) / 100.0 if pf.get('mic_ui') is not None else 0.77
    )
    ref_vocal_gain = float(pf['ref_vocal_gain']) if pf.get('ref_vocal_gain') is not None else (
        int(pf['orig_ui']) / 100.0 if pf.get('orig_ui') is not None else 0.0
    )
    att = float(pf.get('follow_attenuation', 0.1))
    return {
        'mic_gain': mic_gain,
        'ref_vocal_gain': ref_vocal_gain,
        'follow_threshold': float(pf.get('follow_threshold', 75)),
        'follow_attenuation': min(0.2, max(0.1, att)),
    }


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

    def _build_playback_config(self, mode: str, reverb: bool | None = None) -> AudioStreamConfig:
        audio = self.config_store.get('audio', {}) or {}
        mix = pitchfix_mix_from_config(self.config_store)
        cfg = self.load_stream_config()
        cfg.playback_mode = mode
        cfg.passthrough = mode in ('normal_talk', 'reverb_talk')
        cfg.passthrough_reverb = mode == 'reverb_talk' if reverb is None else bool(reverb)
        cfg.inst_gain = inst_gain_from_config(self.config_store)
        cfg.mic_gain = mix['mic_gain']
        cfg.ref_vocal_gain = mix['ref_vocal_gain']
        cfg.follow_threshold = mix['follow_threshold']
        cfg.follow_attenuation = mix['follow_attenuation']
        if mode in ('normal_talk', 'reverb_talk'):
            cfg.block_ms = int(audio.get('passthrough_block_ms', 50))
            cfg.reverb_mix = float(audio.get('reverb_mix', 0.35))
            cfg.reverb_decay = float(audio.get('reverb_decay', 0.72))
        elif mode in ('ai_sing', 'ai_follow'):
            pf = self.config_store.get('pitchfix', {}) or {}
            cfg.block_ms = int(pf.get('block_ms', audio.get('passthrough_block_ms', 50)))
        return cfg

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

    def save_device_selection(self, input_device, output_device, hostapi: str | None = None):
        from app.audio.devices import device_ref_for_config, list_devices

        devices = list_devices(hostapi=hostapi or self.config_store.get('audio.hostapi'))
        in_ref = device_ref_for_config(input_device, devices)
        out_ref = device_ref_for_config(output_device, devices)
        self.config_store.set('audio.input_device', in_ref)
        self.config_store.set('audio.output_device', out_ref)
        if hostapi:
            self.config_store.set('audio.hostapi', hostapi)
        self.config_store.save()
        self._publish(SignalType.CONFIG_CHANGED, {'section': 'audio', 'input_device': in_ref, 'output_device': out_ref})

    def list_devices(self, hostapi: str | None = None):
        host = hostapi or self.config_store.get('audio.hostapi')
        devices = list_devices(hostapi=host)
        summary = device_summary(devices)
        self._publish(SignalType.STATUS, {'action': 'devices_listed', 'summary': summary, 'devices': [d.to_dict() for d in devices]})
        return devices

    def switch_playback_mode(
        self,
        mode: str,
        inst_path: str | None = None,
        vocal_path: str | None = None,
        inst_seek: float = 0.0,
        reverb: bool | None = None,
    ):
        if mode not in PLAYBACK_MODES:
            raise ValueError('unsupported playback mode: %s' % mode)
        self._ensure_shutdown_hook()
        cfg = self._build_playback_config(mode, reverb=reverb)
        if self.manager and self.manager.running:
            self.manager.set_playback_mode(cfg, inst_path, vocal_path if mode in ('ai_sing', 'ai_follow') else None, inst_seek)
            return self.manager
        self.manager = AudioStreamManager(cfg)
        if inst_path:
            self.manager.load_instrumental(inst_path, inst_seek)
        if vocal_path and mode in ('ai_sing', 'ai_follow'):
            self.manager.load_ref_vocal(vocal_path)
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

    def start_stream(
        self,
        passthrough: bool | None = None,
        reverb: bool = False,
        inst_path: str | None = None,
        inst_seek: float = 0.0,
    ):
        mode = 'reverb_talk' if reverb else 'normal_talk'
        return self.switch_playback_mode(mode, inst_path=inst_path, vocal_path=None, inst_seek=inst_seek, reverb=reverb)

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
