"""制作歌曲 Tab 骨架：左资源栏 + 中文件输入 + 右参数（对标 SoundTrail）。"""

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SongMakePage(QWidget):
    """「制作歌曲」页：离线做歌入口，后续接 OfflineSongPipeline。"""

    RESOURCE_ITEMS = (
        ('伴奏', 'resource_accompaniment'),
        ('人声', 'resource_vocal'),
        ('原声', 'resource_original'),
        ('歌词', 'resource_lyrics'),
    )

    def __init__(self, bridge, project_root=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self._build_ui()
        self._set_input_mode(0)
        self._set_preset('normal')

    def _build_ui(self):
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(1, 1)

    def _build_left_panel(self):
        panel = QWidget()
        panel.setMaximumWidth(220)
        layout = QVBoxLayout(panel)
        grid = QGridLayout()
        for i, (label, action) in enumerate(self.RESOURCE_ITEMS):
            btn = QPushButton(label)
            btn.setMinimumHeight(56)
            btn.clicked.connect(
                lambda _, a=action, t=label: self.bridge.emit_action(a, log='资源栏「%s」：后续接入' % t)
            )
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addWidget(QLabel('已加载文件:'))
        self.loaded_files = QListWidget()
        layout.addWidget(self.loaded_files, stretch=1)
        btn_save = QPushButton('保存集合')
        btn_save.clicked.connect(
            lambda: self.bridge.emit_action('save_collection', log='保存集合：后续接入')
        )
        btn_clear = QPushButton('清理文件')
        btn_clear.clicked.connect(self._clear_loaded_files)
        layout.addWidget(btn_save)
        layout.addWidget(btn_clear)
        return panel

    def _build_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        mode_row = QHBoxLayout()
        self.btn_mode_file = QPushButton('输入文件做歌')
        self.btn_mode_link = QPushButton('输入曲库链接做歌')
        for btn in (self.btn_mode_file, self.btn_mode_link):
            btn.setCheckable(True)
            mode_row.addWidget(btn)
        self.btn_mode_file.setChecked(True)
        self.btn_mode_file.clicked.connect(lambda: self._set_input_mode(0))
        self.btn_mode_link.clicked.connect(lambda: self._set_input_mode(1))
        layout.addLayout(mode_row)

        action_row = QHBoxLayout()
        action_row.addStretch()
        btn_pick = QPushButton('选择文件')
        btn_pick.clicked.connect(self._pick_files)
        btn_clear_all = QPushButton('清除全部')
        btn_clear_all.clicked.connect(self._clear_input_list)
        btn_clear_sel = QPushButton('清除选中')
        btn_clear_sel.clicked.connect(self._clear_selected_input)
        for btn in (btn_pick, btn_clear_all, btn_clear_sel):
            action_row.addWidget(btn)
        layout.addLayout(action_row)

        self.input_stack = QStackedWidget()
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self._sync_loaded_files)
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText('曲库链接（后续接入）')
        self.input_stack.addWidget(self.file_list)
        self.input_stack.addWidget(self.link_input)
        layout.addWidget(self.input_stack, stretch=1)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        basic = QGroupBox('基础参数设置')
        basic_form = QFormLayout(basic)
        self.chk_separate = QCheckBox('是否分离伴奏')
        self.chk_separate.setChecked(True)
        self.chk_server = QCheckBox('服务器制作')
        basic_form.addRow(self.chk_separate)
        basic_form.addRow(self.chk_server)
        layout.addWidget(basic)

        mode_box = QGroupBox('做歌方式')
        mode_layout = QHBoxLayout(mode_box)
        self.btn_preset_normal = QPushButton('普通做歌')
        self.btn_preset_powerful = QPushButton('强力做歌')
        for btn in (self.btn_preset_normal, self.btn_preset_powerful):
            btn.setCheckable(True)
            mode_layout.addWidget(btn)
        self.btn_preset_normal.setChecked(True)
        self.btn_preset_normal.clicked.connect(lambda: self._set_preset('normal'))
        self.btn_preset_powerful.clicked.connect(lambda: self._set_preset('powerful'))
        layout.addWidget(mode_box)

        self.p_f0_key = QSlider(Qt.Orientation.Horizontal)
        self.p_f0_key.setRange(-24, 24)
        self.p_f0_key.setValue(0)
        self.lbl_f0_key = QLabel('0')
        self.p_f0_key.valueChanged.connect(lambda v: self.lbl_f0_key.setText(str(v)))
        f0_row = QHBoxLayout()
        f0_row.addWidget(self.p_f0_key)
        f0_row.addWidget(self.lbl_f0_key)
        layout.addWidget(QLabel('音高调整(半音)'))
        layout.addLayout(f0_row)

        self.p_formant = QSlider(Qt.Orientation.Horizontal)
        self.p_formant.setRange(-100, 100)
        self.p_formant.setValue(0)
        self.lbl_formant = QLabel('0.0')
        self.p_formant.valueChanged.connect(lambda v: self.lbl_formant.setText('%.1f' % (v / 10.0)))
        formant_row = QHBoxLayout()
        formant_row.addWidget(self.p_formant)
        formant_row.addWidget(self.lbl_formant)
        layout.addWidget(QLabel('声音粗细'))
        layout.addLayout(formant_row)

        adv = QGroupBox('高级参数（骨架）')
        adv_form = QFormLayout(adv)
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
        self.offline_model = QComboBox()
        self._reload_model_combo()
        self.offline_output = QLineEdit('opt/task4_offline')
        adv_form.addRow('F0 算法', self.p_f0_method)
        adv_form.addRow('Index 占比', self.p_index_rate)
        adv_form.addRow('Protect', self.p_protect)
        adv_form.addRow('RVC 模型', self.offline_model)
        adv_form.addRow('输出目录', self.offline_output)
        layout.addWidget(adv)

        btn_adv = QPushButton('高级参数设置')
        btn_adv.clicked.connect(lambda: adv.setVisible(not adv.isVisible()))
        btn_open = QPushButton('打开输出文件夹')
        btn_open.clicked.connect(self._open_output_dir)
        btn_run = QPushButton('开始处理')
        btn_run.setStyleSheet('padding: 10px; font-weight: bold;')
        btn_run.clicked.connect(self._request_offline_cover)
        layout.addWidget(btn_adv)
        layout.addWidget(btn_open)
        layout.addWidget(btn_run)
        layout.addStretch()
        self._adv_group = adv
        adv.setVisible(False)
        return panel

    def _weights_dir(self):
        return self.project_root / 'assets' / 'weights'

    def _reload_model_combo(self):
        self.offline_model.clear()
        root = self._weights_dir()
        if root.is_dir():
            for path in sorted(root.glob('*.pth')):
                self.offline_model.addItem(path.name)

    def _set_input_mode(self, index: int):
        self.input_stack.setCurrentIndex(index)
        self.btn_mode_file.setChecked(index == 0)
        self.btn_mode_link.setChecked(index == 1)
        for btn, active in ((self.btn_mode_file, index == 0), (self.btn_mode_link, index == 1)):
            btn.setStyleSheet(
                'padding: 6px 12px; border-radius: 8px;'
                + ('background:#2563eb;color:white;' if active else 'background:#eef2ff;')
            )
        self._style_preset_buttons()

    def _set_preset(self, preset: str):
        normal = preset == 'normal'
        self.btn_preset_normal.setChecked(normal)
        self.btn_preset_powerful.setChecked(not normal)
        self._style_preset_buttons()

    def _style_preset_buttons(self):
        for btn, active in ((self.btn_preset_normal, self.btn_preset_normal.isChecked()), (self.btn_preset_powerful, self.btn_preset_powerful.isChecked())):
            btn.setStyleSheet(
                'padding: 6px 12px; border-radius: 8px;'
                + ('background:#2563eb;color:white;' if active else 'background:#eef2ff;')
            )

    def _pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择音频', str(self.project_root), 'Audio (*.wav *.flac *.mp3 *.m4a)'
        )
        for path in paths:
            if not self.file_list.findItems(path, Qt.MatchFlag.MatchExactly):
                self.file_list.addItem(path)
        self._sync_loaded_files()

    def _clear_input_list(self):
        self.file_list.clear()
        self.loaded_files.clear()

    def _clear_selected_input(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._sync_loaded_files()

    def _clear_loaded_files(self):
        self.loaded_files.clear()
        self.file_list.clear()

    def _sync_loaded_files(self):
        self.loaded_files.clear()
        for i in range(self.file_list.count()):
            self.loaded_files.addItem(Path(self.file_list.item(i).text()).name)

    def _open_output_dir(self):
        out = self.project_root / self.offline_output.text().strip()
        out.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(out))
        self.bridge.emit_action('open_output_dir', path=str(out), log='已打开输出目录')

    def _request_offline_cover(self):
        if self.file_list.count() == 0:
            QMessageBox.information(self, '提示', '请先选择原唱文件')
            return
        model = self.offline_model.currentText()
        if not model:
            QMessageBox.information(self, '提示', '请先导入 RVC 模型到 assets/weights')
            return
        preset = 'powerful' if self.btn_preset_powerful.isChecked() else 'normal'
        payload = {
            'input': self.file_list.item(0).text(),
            'preset': preset,
            'model': model,
            'output_dir': self.offline_output.text().strip(),
            'f0_up_key': self.p_f0_key.value(),
            'f0_method': self.p_f0_method.currentText(),
            'index_rate': self.p_index_rate.value(),
            'protect': self.p_protect.value(),
            'separate_accompaniment': self.chk_separate.isChecked(),
            'server_mode': self.chk_server.isChecked(),
        }
        self.bridge.emit_action('offline_cover', **payload, log='已提交离线制作任务（集成阶段执行）')

    def import_models(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '导入模型', str(self.project_root), 'RVC Model (*.pth *.index)'
        )
        if not paths:
            return
        dest = self._weights_dir()
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in paths:
            target = dest / Path(src).name
            shutil.copy2(src, target)
            copied.append(target.name)
        self._reload_model_combo()
        self.bridge.emit_action('model_import', files=copied, log='已导入模型: %s' % ', '.join(copied))
