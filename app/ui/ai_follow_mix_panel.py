"""AI 跟唱混音调节浮层（对标声迹喇叭面板）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from app.config_store import ConfigStore

_DEFAULTS = {
    'inst_ui': 77,
    'mic_ui': 77,
    'orig_ui': 0,
    'threshold': 75,
    'attenuation_ui': 1,
}


def _att_from_slider(v: int) -> float:
    return min(0.2, max(0.1, 0.1 + (int(v) - 1) * 0.01))


def _slider_from_att(att: float) -> int:
    att = min(0.2, max(0.1, float(att)))
    return max(1, min(11, int(round((att - 0.1) / 0.01)) + 1))


class AiFollowMixPanel(QFrame):
    def __init__(self, bridge, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.bridge = bridge
        self.setMinimumWidth(360)
        self.setStyleSheet(
            'QFrame{background:#fff;border:1px solid #e2e8f0;border-radius:10px;}'
            'QLabel{color:#334155;font-size:13px;}'
            'QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}'
            'QSlider::handle:horizontal{width:14px;margin:-5px 0;background:#2563eb;border-radius:7px;}'
            'QPushButton{padding:4px 12px;border-radius:6px;border:1px solid #cbd5e1;background:#fff;}'
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        self._rows = {}
        for key, label, lo, hi, tip in (
            ('inst_ui', '伴奏音量', 0, 100, ''),
            ('mic_ui', 'AI人声音量', 0, 150, 'VAD 门控打开时，按歌曲时间轴播放 converted_vocal 的音量'),
            ('orig_ui', '原唱监听', 0, 100, '不参与 VAD，始终叠加 converted_vocal（通常为 0）'),
            ('threshold', '跟唱阈值', 0, 100, '越高越不易误触（喘气可调到 65~80）；越低越容易跟唱'),
            ('attenuation_ui', '跟唱衰减', 1, 11, '字间/停麦后 AI 人声保持（秒）；0.10≈0.25s，0.20≈0.5s；句中断可略加大'),
        ):
            layout.addLayout(self._make_row(key, label, lo, hi, tip))
        foot = QHBoxLayout()
        foot.addStretch()
        btn_reset = QPushButton('重置')
        btn_reset.clicked.connect(self._on_reset)
        foot.addWidget(btn_reset)
        layout.addLayout(foot)
        self._load_from_config()

    def _make_row(self, key, label, lo, hi, tip=''):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        if tip:
            slider.setToolTip(tip)
        val_lbl = QLabel('')
        val_lbl.setMinimumWidth(36)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _sync(v):
            if key == 'attenuation_ui':
                val_lbl.setText('%.2f' % _att_from_slider(v))
            else:
                val_lbl.setText(str(v))
            self._emit_change()

        slider.valueChanged.connect(_sync)
        row.addWidget(slider, stretch=1)
        row.addWidget(val_lbl)
        self._rows[key] = (slider, val_lbl)
        return row

    def _load_from_config(self):
        pf = ConfigStore().load().get('pitchfix', {}) or {}
        values = dict(_DEFAULTS)
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
        return out

    def _emit_change(self):
        self.bridge.emit_action('playback_ai_follow_mix', **self._values())

    def _on_reset(self):
        for key, val in _DEFAULTS.items():
            slider, _ = self._rows[key]
            slider.setValue(val)
