"""实时 RVC 参数（映射 realtime_gui.py）。"""

from dataclasses import dataclass


@dataclass
class RealtimeRvcConfig:
    model_sid: str = ''
    index_path: str = ''
    pitch: int = 0
    formant: float = 0.0
    index_rate: float = 0.0
    f0_method: str = 'rmvpe'
    block_time: float = 0.25
    crossfade_time: float = 0.05
    extra_time: float = 2.5
    sample_rate: int = 48000
    sr_type: str = 'sr_model'
    channels: int = 1

    def to_dict(self):
        return {
            'model_sid': self.model_sid,
            'index_path': self.index_path,
            'pitch': self.pitch,
            'formant': self.formant,
            'index_rate': self.index_rate,
            'f0_method': self.f0_method,
            'block_time': self.block_time,
            'crossfade_time': self.crossfade_time,
            'extra_time': self.extra_time,
            'sample_rate': self.sample_rate,
            'sr_type': self.sr_type,
            'channels': self.channels,
        }
