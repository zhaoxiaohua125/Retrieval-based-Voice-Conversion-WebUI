"""主窗口骨架（对标 SoundTrail 布局，无音频/推理逻辑）。"""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.layout_store import load_ui_layout, save_ui_layout


class MainWindow(QMainWindow):
    """主界面：左资源栏 + 中 Tab + 右参数 + 底日志。"""

    def __init__(self, bridge, project_root=None):
        super().__init__()
        self.bridge = bridge
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.setWindowTitle('RVC AI 跟唱客户端')
        self.resize(1280, 800)
        self._build_ui()
        self._restore_layout()
        self._gpu_timer = QTimer(self)
        self._gpu_timer.timeout.connect(self._refresh_gpu_status)
        self._gpu_timer.start(8000)
        self._refresh_gpu_status()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        self.resource_list = QListWidget()
        self.resource_list.addItems(['伴奏', '人声', 'LRC 歌词', '模型文件'])
        self.resource_list.setMaximumWidth(180)
        splitter.addWidget(self.resource_list)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.tabs = QTabWidget()
        center_layout.addWidget(self.tabs)
        self.tabs.addTab(self._build_realtime_tab(), '实时跟唱')
        self.tabs.addTab(self._build_offline_tab(), '离线制作')
        self.tabs.addTab(self._build_model_tab(), '模型管理')
        self.tabs.addTab(self._build_settings_tab(), '系统设置')
        splitter.addWidget(center)

        self.params_panel = self._build_params_panel()
        self.params_panel.setMaximumWidth(320)
        splitter.addWidget(self.params_panel)
        splitter.setStretchFactor(1, 1)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText('运行日志…')
        self.log_view.setMaximumHeight(160)
        outer.addWidget(self.log_view)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.gpu_label = QLabel('GPU: --')
        self.status.addPermanentWidget(self.gpu_label)

        self.bridge.log_message.connect(self.append_log)

    def _build_realtime_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel('实时跟唱（阶段 3/4B 接入音频 IO + 流式 RVC）'))
        btn = QPushButton('启动 AI 跟唱（占位）')
        btn.clicked.connect(
            lambda: self.bridge.emit_action('realtime_start', log='实时跟唱：音频模块未接入，敬请期待')
        )
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _build_offline_tab(self):
        w = QWidget()
        layout = QFormLayout(w)
        self.offline_input = QLineEdit()
        btn_in = QPushButton('选择原唱…')
        btn_in.clicked.connect(self._pick_offline_input)
        row_in = QHBoxLayout()
        row_in.addWidget(self.offline_input)
        row_in.addWidget(btn_in)
        layout.addRow('原唱文件', row_in)
        self.offline_preset = QComboBox()
        self.offline_preset.addItems(['normal', 'powerful'])
        layout.addRow('MSST 预设', self.offline_preset)
        self.offline_model = QComboBox()
        self._reload_model_combo(self.offline_model)
        layout.addRow('RVC 模型', self.offline_model)
        self.offline_output = QLineEdit('opt/task4_offline')
        layout.addRow('输出目录', self.offline_output)
        btn_run = QPushButton('开始离线制作')
        btn_run.clicked.connect(self._request_offline_cover)
        layout.addRow(btn_run)
        return w

    def _build_model_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.model_list = QListWidget()
        self._reload_model_list()
        layout.addWidget(self.model_list)
        row = QHBoxLayout()
        btn_import = QPushButton('导入 .pth/.index')
        btn_import.clicked.connect(self._import_models)
        btn_refresh = QPushButton('刷新')
        btn_refresh.clicked.connect(self._reload_model_list)
        row.addWidget(btn_import)
        row.addWidget(btn_refresh)
        layout.addLayout(row)
        return w

    def _build_settings_tab(self):
        w = QWidget()
        layout = QFormLayout(w)
        self.set_audio_device = QLineEdit('（阶段 3 接入 sounddevice 枚举）')
        self.set_osc_port = QSpinBox()
        self.set_osc_port.setRange(1, 65535)
        self.set_osc_port.setValue(9000)
        self.set_update_url = QLineEdit('')
        self.set_log_dir = QLineEdit('logs/client')
        layout.addRow('音频设备', self.set_audio_device)
        layout.addRow('OSC 端口', self.set_osc_port)
        layout.addRow('更新地址', self.set_update_url)
        layout.addRow('日志目录', self.set_log_dir)
        btn_save = QPushButton('保存设置')
        btn_save.clicked.connect(self._save_settings)
        layout.addRow(btn_save)
        return w

    def _build_params_panel(self):
        box = QGroupBox('参数面板')
        form = QFormLayout(box)
        self.p_f0_key = QSpinBox()
        self.p_f0_key.setRange(-24, 24)
        self.p_f0_method = QComboBox()
        self.p_f0_method.addItems(['rmvpe', 'fcpe', 'pm'])
        self.p_index_rate = QDoubleSpinBox()
        self.p_index_rate.setRange(0, 1)
        self.p_index_rate.setSingleStep(0.05)
        self.p_index_rate.setValue(0.75)
        self.p_protect = QDoubleSpinBox()
        self.p_protect.setRange(0, 0.5)
        self.p_protect.setSingleStep(0.01)
        self.p_protect.setValue(0.33)
        self.p_msst_preset = QComboBox()
        self.p_msst_preset.addItems(['普通做歌', '强力做歌'])
        form.addRow('变调(半音)', self.p_f0_key)
        form.addRow('F0 算法', self.p_f0_method)
        form.addRow('Index 占比', self.p_index_rate)
        form.addRow('Protect', self.p_protect)
        form.addRow('MSST 预设', self.p_msst_preset)
        return box

    def _weights_dir(self):
        return self.project_root / 'assets' / 'weights'

    def _reload_model_list(self):
        self.model_list.clear()
        root = self._weights_dir()
        if not root.is_dir():
            self.model_list.addItem('（未找到 assets/weights 目录）')
            return
        files = sorted(list(root.glob('*.pth')) + list(root.glob('*.index')))
        if not files:
            self.model_list.addItem('（暂无模型，请导入）')
            return
        for path in files:
            self.model_list.addItem(path.name)

    def _reload_model_combo(self, combo):
        combo.clear()
        root = self._weights_dir()
        if root.is_dir():
            for path in sorted(root.glob('*.pth')):
                combo.addItem(path.name)

    def _pick_offline_input(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择原唱', str(self.project_root), 'Audio (*.wav *.flac *.mp3 *.m4a)')
        if path:
            self.offline_input.setText(path)

    def _request_offline_cover(self):
        payload = {
            'input': self.offline_input.text().strip(),
            'preset': self.offline_preset.currentText(),
            'model': self.offline_model.currentText(),
            'output_dir': self.offline_output.text().strip(),
            'f0_up_key': self.p_f0_key.value(),
            'f0_method': self.p_f0_method.currentText(),
            'index_rate': self.p_index_rate.value(),
            'protect': self.p_protect.value(),
        }
        if not payload['input']:
            QMessageBox.information(self, '提示', '请先选择原唱文件')
            return
        if not payload['model']:
            QMessageBox.information(self, '提示', '请先选择或导入 RVC 模型')
            return
        self.bridge.emit_action('offline_cover', **payload, log='已提交离线制作任务（集成阶段执行）')

    def _import_models(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '导入模型', str(self.project_root), 'RVC Model (*.pth *.index)'
        )
        if not paths:
            return
        dest = self._weights_dir()
        dest.mkdir(parents=True, exist_ok=True)
        import shutil
        copied = []
        for src in paths:
            target = dest / Path(src).name
            shutil.copy2(src, target)
            copied.append(target.name)
        self._reload_model_list()
        self._reload_model_combo(self.offline_model)
        self.bridge.emit_action('model_import', files=copied, log='已导入模型: %s' % ', '.join(copied))

    def _save_settings(self):
        layout = load_ui_layout()
        layout['settings'] = {
            'osc_port': self.set_osc_port.value(),
            'update_url': self.set_update_url.text().strip(),
            'log_dir': self.set_log_dir.text().strip(),
        }
        save_ui_layout(layout)
        self.bridge.emit_action('settings_save', **layout['settings'], log='设置已保存')

    def append_log(self, text):
        self.log_view.append(text)

    def _refresh_gpu_status(self):
        try:
            from app.ops.hardware import collect_environment_info
            cuda = collect_environment_info().get('cuda', {})
            if cuda.get('available'):
                name = cuda.get('device_name', 'CUDA')
                mem = cuda.get('total_memory_gb', '')
                self.gpu_label.setText('GPU: %s %sGB' % (name, mem))
            else:
                self.gpu_label.setText('GPU: CPU 模式')
        except Exception:
            self.gpu_label.setText('GPU: 未检测')

    def _restore_layout(self):
        layout = load_ui_layout()
        geo = layout.get('geometry')
        if isinstance(geo, list) and len(geo) == 4:
            self.setGeometry(*geo)
        tab = layout.get('active_tab')
        if isinstance(tab, int) and 0 <= tab < self.tabs.count():
            self.tabs.setCurrentIndex(tab)

    def closeEvent(self, event):
        layout = load_ui_layout()
        g = self.geometry()
        layout['geometry'] = [g.x(), g.y(), g.width(), g.height()]
        layout['active_tab'] = self.tabs.currentIndex()
        save_ui_layout(layout)
        event.accept()
