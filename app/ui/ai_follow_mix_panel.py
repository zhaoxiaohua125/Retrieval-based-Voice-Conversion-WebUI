"""播放页喇叭浮层：全局音量 + AI 跟唱专用参数。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from app.config_store import ConfigStore
from app.ui.qt_util import clicked

_DEFAULTS = {
    'inst_ui': 77,
    'ai_vocal_ui': 100,
    'mic_ui': 77,
    'orig_ui': 0,
    'threshold': 75,
    'attenuation_ui': 1,
}

_GLOBAL_ROWS = (
    ('inst_ui', '伴奏', 0, 100, '普通说话、混响、AI 唱歌/跟唱通用'),
    ('ai_vocal_ui', 'AI 人声', 0, 400, 'AI 唱歌/跟唱直播人声，与普通说话同刻度 0～400%'),
)

_FOLLOW_ROWS = (
    ('mic_ui', '跟唱门控', 0, 150, 'VAD 打开时按时间轴播放 converted_vocal 的音量'),
    ('orig_ui', '原唱监听', 0, 100, '不参与 VAD，始终叠加 converted_vocal（通常为 0）'),
    ('threshold', '跟唱阈值', 0, 100, '越高越不易误触；越低越容易跟唱'),
    ('attenuation_ui', '跟唱衰减', 1, 11, '停麦后 AI 人声保持时长；0.10≈0.25s'),
)


def _att_from_slider(v: int) -> float:
    return min(0.2, max(0.1, 0.1 + (int(v) - 1) * 0.01))


def _slider_from_att(att: float) -> int:
    att = min(0.2, max(0.1, float(att)))
    return max(1, min(11, int(round((att - 0.1) / 0.01)) + 1))


class AiFollowMixPanel(QFrame):
    def __init__(self, bridge, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.bridge = bridge
        self.setMinimumWidth(380)
        self.setStyleSheet(
            'QFrame{background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;}'
            'QGroupBox{font-weight:600;color:#1e293b;border:1px solid #cbd5e1;border-radius:8px;'
            'margin-top:12px;padding:12px 10px 10px 10px;background:#fff;}'
            'QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}'
            'QLabel{color:#334155;font-size:13px;}'
            'QLabel#mixHint{color:#64748b;font-size:11px;}'
            'QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}'
            'QSlider::handle:horizontal{width:14px;margin:-5px 0;background:#2563eb;border-radius:7px;}'
            'QPushButton{padding:5px 14px;border-radius:6px;border:1px solid #cbd5e1;background:#fff;color:#334155;}'
            'QPushButton:hover{background:#f1f5f9;}'
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)
        hint = QLabel('实时调节播放混音；跟唱区仅在 AI 跟唱模式生效')
        hint.setObjectName('mixHint')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._rows = {}
        layout.addWidget(self._make_group('全局音量', _GLOBAL_ROWS))
        layout.addWidget(self._make_group('AI 跟唱专用', _FOLLOW_ROWS))
        foot = QHBoxLayout()
        foot.addStretch()
        btn_reset = QPushButton('重置默认')
        btn_reset.clicked.connect(clicked(self._on_reset))
        foot.addWidget(btn_reset)
        layout.addLayout(foot)
        self._load_from_config()

    def _make_group(self, title: str, rows):
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(8)
        for key, label, lo, hi, tip in rows:
            box_layout.addLayout(self._make_row(key, label, lo, hi, tip))
        return box

    def _make_row(self, key, label, lo, hi, tip=''):
        row = QHBoxLayout()
        row.setSpacing(8)
        name = QLabel(label)
        name.setFixedWidth(64)
        name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        if tip:
            slider.setToolTip(tip)
        val_lbl = QLabel('')
        val_lbl.setMinimumWidth(40)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setStyleSheet('color:#2563eb;font-weight:600;')

        def _sync(v):
            if key == 'attenuation_ui':
                val_lbl.setText('%.2f' % _att_from_slider(v))
            elif key in ('inst_ui', 'ai_vocal_ui'):
                val_lbl.setText('%s%%' % v)
            else:
                val_lbl.setText(str(v))
            self._emit_change()

        slider.valueChanged.connect(_sync)
        row.addWidget(name)
        row.addWidget(slider, stretch=1)
        row.addWidget(val_lbl)
        self._rows[key] = (slider, val_lbl)
        return row

    def _load_from_config(self):
        cfg = ConfigStore().load()
        pf = cfg.get('pitchfix', {}) or {}
        audio = cfg.get('audio', {}) or {}
        values = dict(_DEFAULTS)
        values['ai_vocal_ui'] = int(audio.get('ai_vocal_ui', 100))
        if 'inst_ui' in pf:
            values['inst_ui'] = int(pf['inst_ui'])
        elif pf.get('inst_gain') is not None:
            values['inst_ui'] = int(round(float(pf['inst_gain']) * 100))
        if 'mic_ui' in pf:
            values['mic_ui'] = int(pf['mic_ui'])
        elif pf.get('mic_gain') is not None:
            values['mic_ui'] = int(round(float(pf['mic_gain']) * 100))
        for key in ('orig_ui', 'threshold', 'attenuation_ui'):
            if key in pf:
                values[key] = int(pf[key])
            elif key == 'orig_ui' and pf.get('ref_vocal_gain') is not None:
                values['orig_ui'] = int(round(float(pf['ref_vocal_gain']) * 100))
            elif key == 'threshold' and pf.get('follow_threshold') is not None:
                values['threshold'] = int(round(float(pf['follow_threshold'])))
            elif key == 'attenuation_ui' and pf.get('follow_attenuation') is not None:
                values['attenuation_ui'] = _slider_from_att(float(pf['follow_attenuation']))
        for key, (slider, val_lbl) in self._rows.items():
            slider.blockSignals(True)
            slider.setValue(values[key])
            slider.blockSignals(False)
            if key == 'attenuation_ui':
                val_lbl.setText('%.2f' % _att_from_slider(values[key]))
            elif key in ('inst_ui', 'ai_vocal_ui'):
                val_lbl.setText('%s%%' % values[key])
            else:
                val_lbl.setText(str(values[key]))

    def _values(self):
        out = {}
        for key, (slider, _) in self._rows.items():
            out[key] = slider.value()
        out['inst_gain'] = out['inst_ui'] / 100.0
        out['mic_gain'] = out['mic_ui'] / 100.0
        out['ref_vocal_gain'] = out['orig_ui'] / 100.0
        out['follow_threshold'] = float(out['threshold'])
        out['follow_attenuation'] = _att_from_slider(out['attenuation_ui'])
        out['ai_vocal_gain'] = round(out['ai_vocal_ui'] / 100.0, 3)
        return out

    def _emit_change(self):
        v = self._values()
        self.bridge.emit_action(
            'playback_ai_follow_mix',
            inst_ui=v['inst_ui'],
            inst_gain=v['inst_gain'],
            mic_ui=v['mic_ui'],
            mic_gain=v['mic_gain'],
            orig_ui=v['orig_ui'],
            ref_vocal_gain=v['ref_vocal_gain'],
            threshold=v['threshold'],
            follow_threshold=v['follow_threshold'],
            attenuation_ui=v['attenuation_ui'],
            follow_attenuation=v['follow_attenuation'],
        )
        self.bridge.emit_action('playback_ai_vocal_mix', ai_vocal_ui=v['ai_vocal_ui'], ai_vocal_gain=v['ai_vocal_gain'])

    def _on_reset(self):
        for key, val in _DEFAULTS.items():
            slider, val_lbl = self._rows[key]
            slider.setValue(val)
