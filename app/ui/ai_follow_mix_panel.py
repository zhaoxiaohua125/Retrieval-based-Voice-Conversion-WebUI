"""AI 跟唱混音调节浮层（对标声迹喇叭面板）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from app.config_store import ConfigStore
from app.pitchfix.detune import detune_mode_labels

_DEFAULTS = {
    'inst_ui': 77,
    'mic_ui': 77,
    'orig_ui': 0,
    'threshold': 75,
    'attenuation_ui': 1,
    'detune_mode': 'off',
}


def _att_from_slider(v: int) -> float:
    return max(0.1, float(v) / 10.0)


def _slider_from_att(att: float) -> int:
    return max(1, min(100, int(round(float(att) * 10))))


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
        for key, label, lo, hi in (
            ('inst_ui', '伴奏音量', 0, 100),
            ('mic_ui', '人声音量', 0, 150),
            ('orig_ui', '原唱音量', 0, 100),
            ('threshold', 'AI跟唱阈值', 0, 100),
            ('attenuation_ui', 'AI跟唱衰减', 1, 100),
        ):
            layout.addLayout(self._make_row(key, label, lo, hi))
        detune_row = QHBoxLayout()
        detune_row.addWidget(QLabel('AI跑调模式'))
        self.cmb_detune = QComboBox()
        self._detune_ids = []
        for mode_id, label in detune_mode_labels():
            self.cmb_detune.addItem(label, mode_id)
            self._detune_ids.append(mode_id)
        self.cmb_detune.setToolTip('对参考旋律叠加微音高抖动，避免修音过准显得假')
        self.cmb_detune.currentIndexChanged.connect(self._on_detune_changed)
        detune_row.addWidget(self.cmb_detune, stretch=1)
        layout.addLayout(detune_row)
        foot = QHBoxLayout()
        foot.addStretch()
        btn_reset = QPushButton('重置')
        btn_reset.clicked.connect(self._on_reset)
        foot.addWidget(btn_reset)
        layout.addLayout(foot)
        self._load_from_config()

    def _make_row(self, key, label, lo, hi):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        val_lbl = QLabel('')
        val_lbl.setMinimumWidth(36)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _sync(v):
            if key == 'attenuation_ui':
                val_lbl.setText('%.1f' % _att_from_slider(v))
            else:
                val_lbl.setText(str(v))
            self._emit_change()

        if key == 'attenuation_ui':
            slider.setToolTip('值越大灵敏度越低：停麦后还跟唱更久；0.1 最灵敏，话筒一停即停')

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
                val_lbl.setText('%.1f' % _att_from_slider(values[key]))
            else:
                val_lbl.setText(str(values[key]))
        mode = str(pf.get('detune_mode', _DEFAULTS['detune_mode']))
        idx = self.cmb_detune.findData(mode)
        self.cmb_detune.blockSignals(True)
        self.cmb_detune.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_detune.blockSignals(False)

    def _on_detune_changed(self, _idx):
        self._emit_change()

    def _values(self):
        out = {}
        for key, (slider, _) in self._rows.items():
            out[key] = slider.value()
        out['inst_gain'] = out['inst_ui'] / 100.0
        out['mic_gain'] = out['mic_ui'] / 100.0
        out['ref_vocal_gain'] = out['orig_ui'] / 100.0
        out['follow_threshold'] = float(out['threshold'])
        out['follow_attenuation'] = _att_from_slider(out['attenuation_ui'])
        out['detune_mode'] = str(self.cmb_detune.currentData() or 'off')
        return out

    def _emit_change(self):
        self.bridge.emit_action('playback_ai_follow_mix', **self._values())

    def _on_reset(self):
        for key, val in _DEFAULTS.items():
            if key == 'detune_mode':
                idx = self.cmb_detune.findData(val)
                if idx >= 0:
                    self.cmb_detune.setCurrentIndex(idx)
                continue
            slider, _ = self._rows[key]
            slider.setValue(val)
