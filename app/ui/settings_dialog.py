"""系统设置：常规项 + 音频设备（对标 realtime_gui / YY 试麦）。"""

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from app.audio.devices import list_devices, list_hostapis, pick_voicemeeter_defaults
from app.config_store import ConfigStore
from app.ui.layout_store import load_ui_layout
from app.ui.rvc_advanced_dialog import RvcAdvancedDialog


class SettingsDialog(QDialog):
    """系统设置弹窗：写入 config/client.json，无需手改 JSON。"""

    def __init__(self, bridge, config: ConfigStore, project_root=None, song_make_page=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.config = config
        self.project_root = project_root
        self.song_make_page = song_make_page
        self._mic_testing = False
        self._realtime_payload = None
        self.setWindowTitle('系统设置')
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_values()
        self._reload_devices()

    def _build_ui(self):
        root = QVBoxLayout(self)
        general = QGroupBox('常规')
        general_form = QFormLayout(general)
        self.spin_osc = QSpinBox()
        self.spin_osc.setRange(1, 65535)
        self.edit_update_url = QLineEdit()
        self.edit_log_dir = QLineEdit()
        general_form.addRow('OSC 端口', self.spin_osc)
        general_form.addRow('更新地址', self.edit_update_url)
        general_form.addRow('日志目录', self.edit_log_dir)
        root.addWidget(general)

        audio_box = QGroupBox('音频设备')
        audio_layout = QVBoxLayout(audio_box)
        host_row = QHBoxLayout()
        host_row.addWidget(QLabel('设备类型'))
        self.cmb_hostapi = QComboBox()
        self.cmb_hostapi.setMinimumWidth(220)
        self.cmb_hostapi.currentIndexChanged.connect(self._reload_devices)
        self.chk_wasapi = QCheckBox('独占 WASAPI 设备')
        host_row.addWidget(self.cmb_hostapi, stretch=1)
        host_row.addWidget(self.chk_wasapi)
        audio_layout.addLayout(host_row)

        form = QFormLayout()
        self.cmb_input = QComboBox()
        self.cmb_input.setMinimumWidth(420)
        self.cmb_output = QComboBox()
        self.cmb_output.setMinimumWidth(420)
        form.addRow('输入设备', self.cmb_input)
        form.addRow('输出设备', self.cmb_output)
        audio_layout.addLayout(form)

        sr_row = QHBoxLayout()
        self.btn_reload = QPushButton('重载设备列表')
        self.btn_reload.clicked.connect(self._reload_devices)
        self.radio_sr_model = QRadioButton('使用模型采样率')
        self.radio_sr_device = QRadioButton('使用设备采样率')
        self.sr_group = QButtonGroup(self)
        self.sr_group.addButton(self.radio_sr_model)
        self.sr_group.addButton(self.radio_sr_device)
        self.lbl_sample_rate = QLabel('采样率：48000')
        sr_row.addWidget(self.btn_reload)
        sr_row.addWidget(self.radio_sr_model)
        sr_row.addWidget(self.radio_sr_device)
        sr_row.addStretch()
        sr_row.addWidget(self.lbl_sample_rate)
        audio_layout.addLayout(sr_row)

        self.spin_sample_rate = QSpinBox()
        self.spin_sample_rate.setRange(8000, 192000)
        self.spin_sample_rate.setSingleStep(1000)
        self.spin_sample_rate.setValue(48000)
        self.spin_sample_rate.valueChanged.connect(lambda v: self.lbl_sample_rate.setText('采样率：%s' % v))
        self.radio_sr_device.toggled.connect(self._sync_sr_controls)
        self.radio_sr_model.toggled.connect(self._sync_sr_controls)
        self.cmb_input.currentIndexChanged.connect(self._sync_device_sample_rate_hint)
        self.cmb_output.currentIndexChanged.connect(self._sync_device_sample_rate_hint)

        mic_row = QHBoxLayout()
        self.btn_test_mic = QPushButton('试麦')
        self.btn_test_mic.setToolTip('启动干声直通测试，对着麦克风说话；再次点击停止')
        self.btn_test_mic.clicked.connect(self._toggle_test_mic)
        self.lbl_mic_hint = QLabel('试麦：直通输入→输出，不经 RVC')
        self.lbl_mic_hint.setStyleSheet('color:#64748b;font-size:12px;')
        mic_row.addWidget(self.btn_test_mic)
        mic_row.addWidget(self.lbl_mic_hint, stretch=1)
        audio_layout.addLayout(mic_row)
        root.addWidget(audio_box)

        rvc_row = QHBoxLayout()
        self.lbl_model = QLabel('')
        self.lbl_model.setStyleSheet('color:#334155;font-size:13px;')
        self.btn_advanced = QPushButton('RVC 高级设置…')
        self.btn_advanced.setToolTip('模型选择、音调/Index/性能参数（对标 realtime_gui）')
        self.btn_advanced.clicked.connect(self._open_advanced)
        rvc_row.addWidget(self.lbl_model, stretch=1)
        rvc_row.addWidget(self.btn_advanced)
        root.addLayout(rvc_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton('保存设置')
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _load_values(self):
        layout = load_ui_layout().get('settings') or {}
        self.spin_osc.setValue(int(self.config.get('lyrics.osc_port', layout.get('osc_port', 9000))))
        self.edit_update_url.setText(str(self.config.get('update.check_url', layout.get('update_url', ''))))
        self.edit_log_dir.setText(str(self.config.get('paths.log_dir', layout.get('log_dir', 'logs/client'))))
        self.spin_sample_rate.setValue(int(self.config.get('audio.sample_rate', 48000)))
        self.chk_wasapi.setChecked(bool(self.config.get('audio.wasapi_exclusive', False)))
        sr_type = str(self.config.get('realtime.sr_type', 'sr_model'))
        if sr_type == 'sr_device':
            self.radio_sr_device.setChecked(True)
        else:
            self.radio_sr_model.setChecked(True)
        self._sync_sr_controls()
        self.cmb_hostapi.blockSignals(True)
        self.cmb_hostapi.clear()
        self.cmb_hostapi.addItem('全部 HostAPI', None)
        saved_host = self.config.get('audio.hostapi')
        pick_idx = 0
        for i, name in enumerate(list_hostapis()):
            self.cmb_hostapi.addItem(name, name)
            if saved_host and name == saved_host:
                pick_idx = i + 1
        self.cmb_hostapi.setCurrentIndex(pick_idx)
        self.cmb_hostapi.blockSignals(False)
        self._refresh_model_label()

    def _refresh_model_label(self):
        sid = self.config.get('realtime.model_sid', '')
        self.lbl_model.setText('当前模型：%s' % (sid or '未选择'))

    def _open_advanced(self):
        dlg = RvcAdvancedDialog(
            self.config, project_root=self.project_root, song_make_page=self.song_make_page, parent=self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._realtime_payload = dlg.collect_realtime_payload()
        for key, val in self._realtime_payload.items():
            self.config.set('realtime.%s' % key, val)
        self._refresh_model_label()

    def _hostapi_filter(self):
        data = self.cmb_hostapi.currentData()
        return data if data else None

    def _reload_devices(self):
        hostapi = self._hostapi_filter()
        devices = list_devices(hostapi=hostapi)
        in_idx = self.config.get('audio.input_device')
        out_idx = self.config.get('audio.output_device')
        if in_idx is None or out_idx is None:
            def_in, def_out = pick_voicemeeter_defaults(devices)
            in_idx = in_idx if in_idx is not None else def_in
            out_idx = out_idx if out_idx is not None else def_out

        def fill_combo(combo, items, selected):
            combo.blockSignals(True)
            combo.clear()
            sel_row = -1
            for dev in items:
                combo.addItem('[%s] %s' % (dev.index, dev.name), dev.index)
                if selected is not None and dev.index == selected:
                    sel_row = combo.count() - 1
            if sel_row >= 0:
                combo.setCurrentIndex(sel_row)
            elif combo.count():
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        inputs = [d for d in devices if d.max_input_channels > 0]
        outputs = [d for d in devices if d.max_output_channels > 0]
        fill_combo(self.cmb_input, inputs, in_idx)
        fill_combo(self.cmb_output, outputs, out_idx)
        self._sync_device_sample_rate_hint()

    def _sync_sr_controls(self):
        use_device = self.radio_sr_device.isChecked()
        self.spin_sample_rate.setEnabled(not use_device)
        self.lbl_sample_rate.setText(
            '采样率：设备默认' if use_device else '采样率：%s' % self.spin_sample_rate.value()
        )

    def _sync_device_sample_rate_hint(self):
        if not self.radio_sr_device.isChecked():
            return
        dev = self.cmb_input.currentData()
        if dev is None:
            return
        for d in list_devices(hostapi=self._hostapi_filter()):
            if d.index == dev and d.default_samplerate:
                self.lbl_sample_rate.setText('采样率：%s（输入设备）' % int(d.default_samplerate))
                break

    def _toggle_test_mic(self):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True, log='试麦已停止')
            self._mic_testing = False
            self.btn_test_mic.setText('试麦')
            return
        self.bridge.emit_action('audio_test_mic', start=True, log='试麦：请对着麦克风说话…')
        self._mic_testing = True
        self.btn_test_mic.setText('停止试麦')

    def closeEvent(self, event):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True)
            self._mic_testing = False
        super().closeEvent(event)

    def reject(self):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True)
            self._mic_testing = False
        super().reject()

    def collect_payload(self) -> dict:
        sr_type = 'sr_device' if self.radio_sr_device.isChecked() else 'sr_model'
        sample_rate = int(self.spin_sample_rate.value())
        if sr_type == 'sr_device':
            dev = self.cmb_input.currentData()
            if dev is not None:
                for d in list_devices(hostapi=self._hostapi_filter()):
                    if d.index == dev and d.default_samplerate:
                        sample_rate = int(d.default_samplerate)
                        break
        payload = {
            'osc_port': self.spin_osc.value(),
            'update_url': self.edit_update_url.text().strip(),
            'log_dir': self.edit_log_dir.text().strip(),
            'sr_type': sr_type,
            'audio': {
                'hostapi': self._hostapi_filter(),
                'wasapi_exclusive': self.chk_wasapi.isChecked(),
                'input_device': self.cmb_input.currentData(),
                'output_device': self.cmb_output.currentData(),
                'sample_rate': sample_rate,
            },
        }
        if self._realtime_payload:
            payload['realtime'] = dict(self._realtime_payload)
        else:
            rt = self.config.get('realtime', {}) or {}
            if rt.get('model_sid'):
                payload['realtime'] = {
                    'model_sid': rt.get('model_sid'),
                    'index_path': rt.get('index_path', ''),
                    'pitch': rt.get('pitch', 0),
                    'formant': rt.get('formant', 0.0),
                    'index_rate': rt.get('index_rate', 0.0),
                    'f0_method': rt.get('f0_method', 'rmvpe'),
                    'block_time': rt.get('block_time', 0.25),
                    'crossfade_time': rt.get('crossfade_time', 0.05),
                    'extra_time': rt.get('extra_time', 2.5),
                    'threhold': rt.get('threhold', -60),
                    'rms_mix_rate': rt.get('rms_mix_rate', 0.0),
                    'I_noise_reduce': rt.get('I_noise_reduce', False),
                    'O_noise_reduce': rt.get('O_noise_reduce', False),
                }
        return payload
