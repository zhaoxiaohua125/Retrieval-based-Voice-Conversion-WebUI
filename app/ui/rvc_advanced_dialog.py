"""RVC 高级设置（对标 realtime_gui：模型 + 常规 + 性能）。"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)

from app.config_store import ConfigStore
from app.rvc.vc_context import resolve_index_for_model


def _slider_row(parent_layout, label: str, minimum: int, maximum: int, value: int, fmt=None):
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    val_lbl = QLabel(fmt(value) if fmt else str(value))
    slider.valueChanged.connect(lambda v: val_lbl.setText(fmt(v) if fmt else str(v)))
    row.addWidget(slider, stretch=1)
    row.addWidget(val_lbl)
    parent_layout.addLayout(row)
    return slider, val_lbl


class RvcAdvancedDialog(QDialog):
    """RVC 实时推理高级参数（独立弹窗）。"""

    def __init__(self, config: ConfigStore, project_root=None, song_make_page=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.song_make_page = song_make_page
        self.setWindowTitle('RVC 高级设置')
        self.setMinimumSize(720, 520)
        self._build_ui()
        self._load_values()

    def _weights_dir(self):
        rel = self.config.get('paths.model_dir', 'assets/weights')
        return (self.project_root / rel).resolve()

    def _indices_dir(self):
        rel = self.config.get('paths.index_dir', 'assets/indices')
        return (self.project_root / rel).resolve()

    def _build_ui(self):
        root = QVBoxLayout(self)
        model_box = QGroupBox('加载模型')
        model_form = QFormLayout(model_box)
        model_row = QHBoxLayout()
        self.cmb_model = QComboBox()
        self.cmb_model.setMinimumWidth(360)
        self.cmb_model.currentTextChanged.connect(self._on_model_changed)
        btn_reload = QPushButton('刷新')
        btn_reload.clicked.connect(self._reload_models)
        btn_import = QPushButton('导入…')
        btn_import.clicked.connect(self._import_models)
        model_row.addWidget(self.cmb_model, stretch=1)
        model_row.addWidget(btn_reload)
        model_row.addWidget(btn_import)
        model_form.addRow('RVC 模型 (.pth)', model_row)
        idx_row = QHBoxLayout()
        self.edit_index = QLineEdit()
        self.edit_index.setPlaceholderText('留空则自动匹配 assets/indices')
        btn_idx = QPushButton('选择 .index')
        btn_idx.clicked.connect(self._pick_index)
        idx_row.addWidget(self.edit_index, stretch=1)
        idx_row.addWidget(btn_idx)
        model_form.addRow('Index 文件', idx_row)
        root.addWidget(model_box)

        body = QHBoxLayout()
        general = QGroupBox('常规设置')
        general_layout = QVBoxLayout(general)
        self.slider_threhold, _ = _slider_row(general_layout, '响应阈值', -60, 0, -60)
        self.slider_pitch, _ = _slider_row(general_layout, '音调设置', -16, 16, 0)
        self.spin_formant = QDoubleSpinBox()
        self.spin_formant.setRange(-2.0, 2.0)
        self.spin_formant.setSingleStep(0.05)
        formant_row = QHBoxLayout()
        formant_row.addWidget(QLabel('声线粗细'))
        formant_row.addWidget(self.spin_formant)
        general_layout.addLayout(formant_row)
        self.slider_index_rate, _ = _slider_row(
            general_layout, '检索特征占比', 0, 100, 0, fmt=lambda v: '%.2f' % (v / 100.0)
        )
        self.slider_rms, _ = _slider_row(
            general_layout, '响度因子', 0, 100, 0, fmt=lambda v: '%.2f' % (v / 100.0)
        )
        f0_row = QHBoxLayout()
        f0_row.addWidget(QLabel('音高算法'))
        self.radio_pm = QRadioButton('pm')
        self.radio_rmvpe = QRadioButton('rmvpe')
        self.radio_fcpe = QRadioButton('fcpe')
        self.f0_group = QButtonGroup(self)
        for rb in (self.radio_pm, self.radio_rmvpe, self.radio_fcpe):
            self.f0_group.addButton(rb)
            f0_row.addWidget(rb)
        f0_row.addStretch()
        general_layout.addLayout(f0_row)
        body.addWidget(general, stretch=1)

        perf = QGroupBox('性能设置')
        perf_layout = QVBoxLayout(perf)
        self.slider_block, _ = _slider_row(
            perf_layout, '采样长度', 2, 150, 25, fmt=lambda v: '%.2f' % (v / 100.0)
        )
        self.slider_crossfade, _ = _slider_row(
            perf_layout, '淡入淡出长度', 1, 15, 5, fmt=lambda v: '%.2f' % (v / 100.0)
        )
        self.slider_extra, _ = _slider_row(
            perf_layout, '额外推理时长', 5, 500, 250, fmt=lambda v: '%.2f' % (v / 100.0)
        )
        self.chk_in_denoise = QCheckBox('输入降噪')
        self.chk_out_denoise = QCheckBox('输出降噪')
        perf_layout.addWidget(self.chk_in_denoise)
        perf_layout.addWidget(self.chk_out_denoise)
        perf_layout.addStretch()
        body.addWidget(perf, stretch=1)
        root.addLayout(body)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton('保存')
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _reload_models(self):
        self.cmb_model.blockSignals(True)
        self.cmb_model.clear()
        weights = self._weights_dir()
        if weights.is_dir():
            for path in sorted(weights.glob('*.pth')):
                self.cmb_model.addItem(path.name)
        self.cmb_model.blockSignals(False)

    def _import_models(self):
        if self.song_make_page is not None:
            self.song_make_page.import_models()
        self._reload_models()
        sid = self.config.get('realtime.model_sid', '')
        if sid:
            idx = self.cmb_model.findText(sid)
            if idx >= 0:
                self.cmb_model.setCurrentIndex(idx)

    def _pick_index(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, '选择 Index', str(self._indices_dir()), 'Index (*.index);;全部 (*.*)'
        )
        if path:
            self.edit_index.setText(str(Path(path).resolve()))

    def _on_model_changed(self, name: str):
        if not name:
            return
        if self.edit_index.text().strip():
            return
        idx = resolve_index_for_model(name, project_root=self.project_root) or ''
        self.edit_index.setText(idx)

    def _load_values(self):
        rt = self.config.get('realtime', {}) or {}
        rvc = self.config.get('rvc', {}) or {}
        self._reload_models()
        sid = str(rt.get('model_sid') or '')
        if sid:
            row = self.cmb_model.findText(sid)
            if row >= 0:
                self.cmb_model.setCurrentIndex(row)
        self.edit_index.setText(str(rt.get('index_path') or ''))
        if not self.edit_index.text() and sid:
            self._on_model_changed(sid)
        self.slider_threhold.setValue(int(rt.get('threhold', -60)))
        self.slider_pitch.setValue(int(rt.get('pitch', rvc.get('f0_up_key', 0))))
        self.spin_formant.setValue(float(rt.get('formant', rvc.get('formant', 0.0))))
        self.slider_index_rate.setValue(int(float(rt.get('index_rate', rvc.get('index_rate', 0.0))) * 100))
        self.slider_rms.setValue(int(float(rt.get('rms_mix_rate', 0.0)) * 100))
        f0 = str(rt.get('f0_method', rvc.get('f0_method', 'rmvpe')))
        if f0 == 'pm':
            self.radio_pm.setChecked(True)
        elif f0 == 'fcpe':
            self.radio_fcpe.setChecked(True)
        else:
            self.radio_rmvpe.setChecked(True)
        self.slider_block.setValue(int(float(rt.get('block_time', 0.25)) * 100))
        self.slider_crossfade.setValue(int(float(rt.get('crossfade_time', 0.05)) * 100))
        self.slider_extra.setValue(int(float(rt.get('extra_time', 2.5)) * 100))
        self.chk_in_denoise.setChecked(bool(rt.get('I_noise_reduce', False)))
        self.chk_out_denoise.setChecked(bool(rt.get('O_noise_reduce', False)))

    def collect_realtime_payload(self) -> dict:
        f0 = 'rmvpe'
        if self.radio_pm.isChecked():
            f0 = 'pm'
        elif self.radio_fcpe.isChecked():
            f0 = 'fcpe'
        return {
            'model_sid': self.cmb_model.currentText(),
            'index_path': self.edit_index.text().strip(),
            'threhold': self.slider_threhold.value(),
            'pitch': self.slider_pitch.value(),
            'formant': float(self.spin_formant.value()),
            'index_rate': self.slider_index_rate.value() / 100.0,
            'rms_mix_rate': self.slider_rms.value() / 100.0,
            'f0_method': f0,
            'block_time': self.slider_block.value() / 100.0,
            'crossfade_time': self.slider_crossfade.value() / 100.0,
            'extra_time': self.slider_extra.value() / 100.0,
            'I_noise_reduce': self.chk_in_denoise.isChecked(),
            'O_noise_reduce': self.chk_out_denoise.isChecked(),
        }
