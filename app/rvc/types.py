"""离线翻唱流水线输出结构。"""

from dataclasses import dataclass, field


@dataclass
class RvcInferParams:
    """RVC 离线推理参数（映射 WebUI 推理页）。"""

    f0_up_key: int = 0
    f0_method: str = 'rmvpe'
    file_index: str = ''
    index_rate: float = 0.75
    resample_sr: int = 0
    rms_mix_rate: float = 0.25
    protect: float = 0.33
    speaker_id: int = 0


@dataclass
class OfflineCoverResult:
    """MSST 多轨 + RVC 转换 + 可选混音成品。"""

    preset_id: str
    source_path: str
    output_dir: str
    vocals_path: str
    instrumental_path: str
    vocals_noreverb_path: str
    converted_vocal_path: str
    cover_path: str | None = None
    harmony_path: str | None = None
    rvc_info: str = ''
    log_lines: list[str] = field(default_factory=list)

    def as_dict(self):
        return {
            'preset_id': self.preset_id,
            'source_path': self.source_path,
            'output_dir': self.output_dir,
            'vocals_path': self.vocals_path,
            'instrumental_path': self.instrumental_path,
            'vocals_noreverb_path': self.vocals_noreverb_path,
            'converted_vocal_path': self.converted_vocal_path,
            'cover_path': self.cover_path,
            'harmony_path': self.harmony_path,
            'rvc_info': self.rvc_info,
        }
