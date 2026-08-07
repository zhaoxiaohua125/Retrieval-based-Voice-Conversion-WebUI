"""AI 跟唱跑调/人性化：对目标 F0 叠加 LFO 微偏移（对标声迹 AI 跑调模式）。"""

import math

DETUNE_MODES = {
    'off': {'label': '关闭', 'cents': 0, 'hz': 0},
    'humanized': {'label': '★ 综合人性化（推荐）', 'cents': 10, 'hz': 5.0},
    'vibrato': {'label': '自然颤音', 'cents': 8, 'hz': 5.5},
    'breath': {'label': '呼吸波动', 'cents': 10, 'hz': 3.0},
    'emotional': {'label': '情感颤抖', 'cents': 12, 'hz': 4.0},
    'jitter': {'label': '微小抖动', 'cents': 6, 'hz': 3.0},
    'drift': {'label': '音准漂移', 'cents': 8, 'hz': 2.0},
    'sway': {'label': '律动摆动', 'cents': 9, 'hz': 3.5},
}


def detune_mode_labels():
    return [(k, v['label']) for k, v in DETUNE_MODES.items()]


def detune_cents(mode: str, t_sec: float) -> float:
    spec = DETUNE_MODES.get(str(mode or 'off')) or DETUNE_MODES['off']
    cents = float(spec['cents'])
    hz = float(spec['hz'])
    if cents <= 0 or hz <= 0:
        return 0.0
    return cents * math.sin(2.0 * math.pi * hz * max(0.0, float(t_sec)))


def apply_detune_f0(target_hz: float, mode: str, t_sec: float) -> float:
    if target_hz <= 0:
        return target_hz
    cents = detune_cents(mode, t_sec)
    if abs(cents) < 0.01:
        return float(target_hz)
    return float(target_hz) * (2.0 ** (cents / 1200.0))
