"""MSST 离线做歌预设：映射到 tools.pymss_webui 中已有的模型 label。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    """单个分离阶段定义。"""

    stage_id: str
    model_label: str
    description: str


@dataclass(frozen=True)
class PresetSpec:
    """普通/强力做歌预设，包含按顺序执行的阶段列表。"""

    preset_id: str
    label: str
    stages: tuple[StageSpec, ...]


PRESET_NORMAL = PresetSpec(
    preset_id='normal',
    label='普通做歌',
    stages=(
        StageSpec('split', '去伴奏', '人声与伴奏分离'),
        StageSpec('dereverb', '去混响', '人声去混响，输出 RVC 输入干声'),
    ),
)

PRESET_POWERFUL = PresetSpec(
    preset_id='powerful',
    label='强力做歌',
    stages=(
        StageSpec('split', '去伴奏（激进）', '高质量人声与伴奏分离'),
        StageSpec('dereverb', '去混响（激进）', '激进去混响'),
        StageSpec('harmony', '提主旋律', '从人声中提取主旋律与和声'),
    ),
)

PRESETS = {
    PRESET_NORMAL.preset_id: PRESET_NORMAL,
    PRESET_POWERFUL.preset_id: PRESET_POWERFUL,
}


def get_preset(preset_id: str) -> PresetSpec:
    """按 preset_id 返回预设；不支持时抛出 KeyError。"""
    key = str(preset_id or 'normal').strip().lower()
    if key not in PRESETS:
        raise KeyError('unknown msst preset: %s' % preset_id)
    return PRESETS[key]
