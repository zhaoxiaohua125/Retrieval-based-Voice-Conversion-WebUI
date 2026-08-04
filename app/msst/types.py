"""MSST 多阶段分离结果数据结构。"""

from dataclasses import dataclass, field


@dataclass
class StageOutput:
    """某一阶段的输出文件路径。"""

    stage_id: str
    model_label: str
    desired_path: str
    secondary_path: str | None = None


@dataclass
class SeparationResult:
    """完整做歌分离结果，路径均为最终导出目录下的标准文件名。"""

    preset_id: str
    source_path: str
    output_dir: str
    vocals_path: str
    instrumental_path: str
    vocals_noreverb_path: str
    harmony_path: str | None = None
    stages: list[StageOutput] = field(default_factory=list)
    log: str = ''

    def as_dict(self):
        """转为 dict，便于调度层通过 BusMessage payload 转发。"""
        return {
            'preset_id': self.preset_id,
            'source_path': self.source_path,
            'output_dir': self.output_dir,
            'vocals_path': self.vocals_path,
            'instrumental_path': self.instrumental_path,
            'vocals_noreverb_path': self.vocals_noreverb_path,
            'harmony_path': self.harmony_path,
            'stages': [
                {
                    'stage_id': item.stage_id,
                    'model_label': item.model_label,
                    'desired_path': item.desired_path,
                    'secondary_path': item.secondary_path,
                }
                for item in self.stages
            ],
        }
