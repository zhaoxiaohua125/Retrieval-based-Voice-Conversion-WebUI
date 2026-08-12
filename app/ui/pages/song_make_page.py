"""制作歌曲 Tab 骨架：左资源栏 + 中文件输入 + 右参数（对标 SoundTrail）。"""

import os
import shutil
from pathlib import Path

from app.ui.qt_util import clicked
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
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
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


AUDIO_SUFFIXES = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.aac', '.wma'}


class AudioDropListWidget(QListWidget):
    """支持拖拽导入音频的文件列表。"""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setToolTip('拖拽音频文件到此处（wav / flac / mp3 / m4a 等）')

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and self._urls_have_audio(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() and self._urls_have_audio(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = self._collect_audio_paths(event.mimeData().urls())
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _collect_audio_paths(urls):
        paths = []
        for url in urls or []:
            path = url.toLocalFile()
            if path and Path(path).suffix.lower() in AUDIO_SUFFIXES and Path(path).is_file():
                paths.append(str(Path(path).resolve()))
        return paths

    @staticmethod
    def _urls_have_audio(urls):
        for url in urls or []:
            path = url.toLocalFile()
            if path and Path(path).suffix.lower() in AUDIO_SUFFIXES:
                return True
        return False


class SongMakePage(QWidget):
    """「制作歌曲」页：离线做歌入口，后续接 OfflineSongPipeline。"""

    RESOURCE_STUB_TIP = '当前为一键做歌，自动分离，无需手动导入'
    RESOURCE_STUB_STYLE = (
        'QPushButton{padding:8px;color:#94a3b8;background-color:#f1f5f9;'
        'border:1px solid #e2e8f0;border-radius:6px;}'
    )
    RESOURCE_LYRICS_STYLE = (
        'QPushButton{padding:8px;color:#334155;background-color:#fff;border:1px solid #cbd5e1;border-radius:6px;}'
        'QPushButton:hover{background-color:#f8fafc;}'
    )

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
        self._lrc_path = ''
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
            if action == 'resource_lyrics':
                btn.setStyleSheet(self.RESOURCE_LYRICS_STYLE)
                btn.setToolTip('选择 LRC 歌词，制作完成后复制到输出目录')
                btn.clicked.connect(clicked(self._pick_lrc))
            else:
                btn.setEnabled(False)
                btn.setStyleSheet(self.RESOURCE_STUB_STYLE)
                btn.setToolTip(self.RESOURCE_STUB_TIP)
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addWidget(QLabel('已加载文件:'))
        self.loaded_files = QListWidget()
        layout.addWidget(self.loaded_files, stretch=1)
        btn_save = QPushButton('保存集合')
        btn_save.clicked.connect(
            clicked(lambda: self.bridge.emit_action('save_collection', log='保存集合：后续接入'))
        )
        btn_clear = QPushButton('清理文件')
        btn_clear.clicked.connect(clicked(self._clear_loaded_files))
        layout.addWidget(btn_save)
        layout.addWidget(btn_clear)
        return panel

    def _build_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        mode_row = QHBoxLayout()
        self.btn_mode_file = QPushButton('输入文件做歌')
        self.btn_mode_link = QPushButton('输入曲库链接做歌')
        self.btn_mode_file.setCheckable(True)
        mode_row.addWidget(self.btn_mode_file)
        mode_row.addWidget(self.btn_mode_link)
        self.btn_mode_file.setChecked(True)
        self.btn_mode_file.clicked.connect(clicked(lambda: self._set_input_mode(0)))
        self.btn_mode_link.setStyleSheet(self.RESOURCE_STUB_STYLE)
        self.btn_mode_link.setToolTip('暂未开放')
        self.btn_mode_link.clicked.connect(clicked(self._on_link_mode_stub))
        layout.addLayout(mode_row)

        action_row = QHBoxLayout()
        action_row.addStretch()
        btn_pick = QPushButton('选择文件')
        btn_pick.clicked.connect(clicked(self._pick_files))
        btn_clear_all = QPushButton('清除全部')
        btn_clear_all.clicked.connect(clicked(self._clear_input_list))
        btn_clear_sel = QPushButton('清除选中')
        btn_clear_sel.clicked.connect(clicked(self._clear_selected_input))
        for btn in (btn_pick, btn_clear_all, btn_clear_sel):
            action_row.addWidget(btn)
        layout.addLayout(action_row)

        self.file_drop_zone = QWidget()
        drop_layout = QGridLayout(self.file_drop_zone)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        self.file_list = AudioDropListWidget()
        self.file_list.setStyleSheet(
            'QListWidget{border:1px dashed #cbd5e1;border-radius:8px;background:#fafafa;padding:8px;}'
        )
        self.file_list.files_dropped.connect(self._add_audio_paths)
        self.file_list.itemSelectionChanged.connect(self._sync_loaded_files)
        self.file_list.model().rowsInserted.connect(lambda *_: self._update_file_drop_hint())
        self.file_list.model().rowsRemoved.connect(lambda *_: self._update_file_drop_hint())
        self.file_drop_hint = QLabel('点击上方「选择文件」按钮，或直接拖拽音频文件到此处\n支持 wav / flac / mp3 / m4a 等格式')
        self.file_drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_drop_hint.setWordWrap(True)
        self.file_drop_hint.setStyleSheet('color:#94a3b8;font-size:14px;padding:24px;background:transparent;')
        self.file_drop_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        drop_layout.addWidget(self.file_list, 0, 0)
        drop_layout.addWidget(self.file_drop_hint, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)

        self.input_stack = QStackedWidget()
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText('曲库链接（后续接入）')
        self.input_stack.addWidget(self.file_drop_zone)
        self.input_stack.addWidget(self.link_input)
        layout.addWidget(self.input_stack, stretch=1)
        self._update_file_drop_hint()

        prog_box = QGroupBox('制作进度')
        prog_layout = QVBoxLayout(prog_box)
        phase_row = QHBoxLayout()
        self.lbl_phase_msst = QLabel('① 分离')
        self.lbl_phase_rvc = QLabel('② 变声')
        self.lbl_phase_mix = QLabel('③ 混音')
        for lb in (self.lbl_phase_msst, self.lbl_phase_rvc, self.lbl_phase_mix):
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet('padding:4px 8px;border-radius:6px;color:#64748b;background:#f1f5f9;')
            phase_row.addWidget(lb)
        prog_layout.addLayout(phase_row)
        self.offline_progress = QProgressBar()
        self.offline_progress.setRange(0, 100)
        self.offline_progress.setValue(0)
        self.offline_progress.setTextVisible(True)
        self.offline_progress.setMinimumHeight(20)
        self.offline_progress.setStyleSheet(
            'QProgressBar{border:1px solid #cbd5e1;border-radius:4px;background:#f1f5f9;text-align:center;}'
            'QProgressBar::chunk{background:#2563eb;border-radius:3px;}'
        )
        self.offline_status = QLabel('等待开始…')
        self.offline_status.setStyleSheet('color:#64748b;')
        prog_layout.addWidget(self.offline_progress)
        prog_layout.addWidget(self.offline_status)
        layout.addWidget(prog_box)

        result_box = QGroupBox('输出结果')
        result_layout = QVBoxLayout(result_box)
        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(120)
        self.result_list.setToolTip('双击打开文件')
        self.result_list.itemDoubleClicked.connect(self._open_result_item)
        result_layout.addWidget(self.result_list)
        layout.addWidget(result_box)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        basic = QGroupBox('基础参数设置')
        basic_form = QFormLayout(basic)
        self.offline_model = QComboBox()
        self.offline_model.setToolTip('选择 assets/weights 下的 .pth 模型')
        self._reload_model_combo()
        self.btn_refresh_model = QPushButton('刷新')
        self.btn_refresh_model.setToolTip('重新扫描 assets/weights 下的 .pth 模型')
        self.btn_refresh_model.clicked.connect(clicked(self._refresh_model_list))
        model_row = QHBoxLayout()
        model_row.addWidget(self.offline_model, stretch=1)
        model_row.addWidget(self.btn_refresh_model)
        model_wrap = QWidget()
        model_wrap.setLayout(model_row)
        self.lbl_index_status = QLabel('')
        self.lbl_index_status.setWordWrap(True)
        self.offline_model.currentTextChanged.connect(lambda _: self._update_index_hint())
        basic_form.addRow('RVC 模型', model_wrap)
        basic_form.addRow('', self.lbl_index_status)
        layout.addWidget(basic)

        mode_box = QGroupBox('做歌方式')
        mode_layout = QHBoxLayout(mode_box)
        self.btn_preset_normal = QPushButton('普通做歌')
        self.btn_preset_powerful = QPushButton('强力做歌')
        for btn in (self.btn_preset_normal, self.btn_preset_powerful):
            btn.setCheckable(True)
            mode_layout.addWidget(btn)
        self.btn_preset_normal.setChecked(True)
        self.btn_preset_normal.clicked.connect(clicked(lambda: self._set_preset('normal')))
        self.btn_preset_powerful.clicked.connect(clicked(lambda: self._set_preset('powerful')))
        layout.addWidget(mode_box)

        self.p_f0_key = QSlider(Qt.Orientation.Horizontal)
        self.p_f0_key.setRange(-12, 12)
        self.p_f0_key.setValue(0)
        self.lbl_f0_key = QLabel('0')
        self.lbl_f0_key.setMinimumWidth(28)
        self.lbl_f0_key.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.p_f0_key.valueChanged.connect(lambda v: self.lbl_f0_key.setText(str(v)))
        layout.addWidget(QLabel('音高调整(半音):(男转女 +12, 女转男 -12)'))
        f0_row = QHBoxLayout()
        lbl_f0_min = QLabel('-12')
        lbl_f0_min.setStyleSheet('color:#64748b;')
        lbl_f0_max = QLabel('+12')
        lbl_f0_max.setStyleSheet('color:#64748b;')
        f0_row.addWidget(lbl_f0_min)
        f0_row.addWidget(self.p_f0_key, stretch=1)
        f0_row.addWidget(lbl_f0_max)
        f0_row.addWidget(self.lbl_f0_key)
        layout.addLayout(f0_row)

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
        self.offline_output = QLineEdit('opt/task4_offline')
        adv_form.addRow('F0 算法', self.p_f0_method)
        adv_form.addRow('Index 占比', self.p_index_rate)
        adv_form.addRow('Protect', self.p_protect)
        adv_form.addRow('输出目录', self.offline_output)
        layout.addWidget(adv)

        btn_adv = QPushButton('高级参数设置')
        btn_adv.clicked.connect(clicked(lambda: adv.setVisible(not adv.isVisible())))
        btn_open = QPushButton('打开输出文件夹')
        btn_open.clicked.connect(clicked(self._open_output_dir))
        btn_run = QPushButton('开始处理')
        btn_run.setStyleSheet('QPushButton{padding:10px;font-weight:bold;}')
        btn_run.clicked.connect(clicked(self._request_offline_cover))
        self.btn_run = btn_run
        self.btn_cancel = QPushButton('取消制作')
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(clicked(self._cancel_offline))
        run_row = QHBoxLayout()
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_cancel)
        layout.addWidget(btn_adv)
        layout.addWidget(btn_open)
        layout.addLayout(run_row)
        layout.addStretch()
        self._adv_group = adv
        adv.setVisible(False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_index_hint)
        return panel

    def _weights_dir(self):
        return self.project_root / 'assets' / 'weights'

    def _indices_dir(self):
        return self.project_root / 'assets' / 'indices'

    def _reload_model_combo(self):
        self.offline_model.clear()
        root = self._weights_dir()
        if root.is_dir():
            for path in sorted(root.glob('*.pth')):
                self.offline_model.addItem(path.name)

    def _refresh_model_list(self):
        prev = self.offline_model.currentText()
        self._reload_model_combo()
        if prev:
            idx = self.offline_model.findText(prev)
            if idx >= 0:
                self.offline_model.setCurrentIndex(idx)
        self._update_index_hint()

    def _update_index_hint(self):
        model = self.offline_model.currentText()
        if not model:
            self.lbl_index_status.setText('暂无模型，请在「高级参数设置」中导入 .pth，或放入 assets/weights 后点刷新')
            self.lbl_index_status.setStyleSheet('color:#64748b;font-size:12px;')
            return
        try:
            from app.rvc.vc_context import resolve_index_for_model
            index_path = resolve_index_for_model(model, project_root=self.project_root)
            if index_path:
                self.lbl_index_status.setText('已匹配 Index：%s' % Path(index_path).name)
                self.lbl_index_status.setStyleSheet('color:#16a34a;font-size:12px;')
            else:
                self.lbl_index_status.setText('')
        except Exception:
            self.lbl_index_status.setText('Index 状态检测失败')
            self.lbl_index_status.setStyleSheet('color:#94a3b8;font-size:12px;')

    def _update_file_drop_hint(self):
        if hasattr(self, 'file_drop_hint'):
            self.file_drop_hint.setVisible(self.file_list.count() == 0)

    def _set_input_mode(self, index: int):
        self.input_stack.setCurrentIndex(0)
        self.btn_mode_file.setChecked(True)
        self.btn_mode_file.setStyleSheet(
            'padding: 6px 12px; border-radius: 8px;background:#2563eb;color:white;'
        )
        self.btn_mode_link.setStyleSheet(self.RESOURCE_STUB_STYLE)
        self._style_preset_buttons()

    def _on_link_mode_stub(self):
        QMessageBox.information(self, '提示', '输入曲库链接做歌暂未开放')
        self._set_input_mode(0)

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
            self, '选择音频', str(self.project_root), 'Audio (*.wav *.flac *.mp3 *.m4a *.ogg *.aac)'
        )
        self._add_audio_paths(paths)

    def _add_audio_paths(self, paths):
        added = 0
        for path in paths or []:
            p = str(Path(path).resolve()) if Path(path).is_file() else str(path)
            if Path(p).suffix.lower() not in AUDIO_SUFFIXES:
                continue
            if self.file_list.findItems(p, Qt.MatchFlag.MatchExactly):
                continue
            self.file_list.addItem(p)
            added += 1
        if added:
            self._set_input_mode(0)
            self._sync_loaded_files()
            self.bridge.emit_action('audio_files_added', count=added, log='已添加 %s 个音频文件' % added)
        elif paths:
            QMessageBox.information(self, '提示', '未识别到支持的音频格式（wav / flac / mp3 / m4a 等）')
        return added

    def _pick_lrc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择歌词', str(self.project_root), 'Lyrics (*.lrc *.LRC)'
        )
        if not path:
            return
        self._lrc_path = path
        self._sync_loaded_files()
        self.bridge.emit_action('resource_lyrics', path=path, log='已选歌词：%s（制作完成后复制到输出目录）' % Path(path).name)

    def _clear_input_list(self):
        self.file_list.clear()
        self.loaded_files.clear()
        self._lrc_path = ''

    def _clear_selected_input(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._sync_loaded_files()

    def _clear_loaded_files(self):
        self.loaded_files.clear()
        self.file_list.clear()
        self._lrc_path = ''

    def _sync_loaded_files(self):
        self.loaded_files.clear()
        for i in range(self.file_list.count()):
            self.loaded_files.addItem(Path(self.file_list.item(i).text()).name)
        if self._lrc_path:
            self.loaded_files.addItem('[歌词] %s' % Path(self._lrc_path).name)

    def _open_output_dir(self):
        out = self.project_root / self.offline_output.text().strip()
        out.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out))
        self.bridge.emit_action('open_output_dir', path=str(out), log='已打开输出目录')

    def _open_result_item(self, item):
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole) or ''
        if not path:
            text = item.text()
            if '：' in text:
                path = text.split('：', 1)[1].strip()
            elif ':' in text:
                path = text.split(':', 1)[1].strip()
        p = Path(path)
        if not p.is_file():
            QMessageBox.information(self, '提示', '文件不存在：\n%s' % path)
            return
        os.startfile(str(p.resolve()))
        self.bridge.emit_action('open_result_file', path=str(p.resolve()), log='已打开：%s' % p.name)

    def _request_offline_cover(self):
        if self.file_list.count() == 0:
            QMessageBox.information(self, '提示', '请先选择原唱文件')
            return
        model = self.offline_model.currentText()
        if not model:
            QMessageBox.information(self, '提示', '请先在「高级参数设置」中导入 RVC 模型，或放入 assets/weights 后点刷新')
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
        }
        if self._lrc_path:
            payload['lrc_path'] = self._lrc_path
        self.bridge.emit_action('offline_cover', **payload, log='已提交离线制作任务')

    def _cancel_offline(self):
        self.bridge.emit_action('offline_cancel', log='已请求取消制作')

    def set_offline_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.btn_run.setText('处理中…' if running else '开始处理')
        if running:
            if not getattr(self, '_offline_ui_active', False):
                self.offline_progress.setValue(0)
                self.offline_status.setText('任务已启动…')
                self._set_phase('')
                self.result_list.clear()
            self._offline_ui_active = True
        else:
            self._offline_ui_active = False

    def apply_offline_progress(self, payload: dict):
        payload = payload or {}
        event = payload.get('event') or payload.get('action')
        nested = payload.get('payload') or {}
        if event == 'phase':
            pct = int(payload.get('percent', 0))
            self.offline_progress.setValue(max(0, min(100, pct)))
            msg = payload.get('message') or ''
            if msg:
                self.offline_status.setText(msg)
            self._set_phase(payload.get('phase') or '')
        elif event in ('progress', 'msst', 'stage_start'):
            msg = payload.get('message') or nested.get('message') or nested.get('model_label') or ''
            if msg:
                self.offline_status.setText(str(msg))
            pct = payload.get('percent')
            if pct is None and event == 'stage_start':
                idx = int(nested.get('stage_index') or 1)
                total = int(nested.get('stage_total') or 1)
                pct = 5.0 + (idx - 1) / max(total, 1) * 65.0
            if pct is not None:
                self.offline_progress.setValue(max(0, min(100, int(pct))))
            if payload.get('phase'):
                self._set_phase(str(payload.get('phase')))

    def _set_phase(self, phase: str):
        phases = {'msst': 0, 'rvc': 1, 'mix': 2, 'done': 3}
        active_idx = phases.get(phase, -1)
        for i, lb in enumerate((self.lbl_phase_msst, self.lbl_phase_rvc, self.lbl_phase_mix)):
            if i < active_idx:
                style = 'padding:4px 8px;border-radius:6px;color:#fff;background:#16a34a;'
            elif i == active_idx:
                style = 'padding:4px 8px;border-radius:6px;color:#fff;background:#2563eb;'
            else:
                style = 'padding:4px 8px;border-radius:6px;color:#64748b;background:#f1f5f9;'
            lb.setStyleSheet(style)

    def show_offline_result(self, result: dict):
        self.offline_progress.setValue(100)
        self.offline_status.setText('制作完成')
        self._set_phase('done')
        self.result_list.clear()
        labels = (
            ('cover_path', '成品'),
            ('converted_vocal_path', 'AI 人声'),
            ('vocals_noreverb_path', '干声'),
            ('instrumental_path', '伴奏'),
            ('lrc_path', '歌词'),
        )
        for key, label in labels:
            path = (result or {}).get(key)
            if path:
                item = QListWidgetItem('%s：%s' % (label, path))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.result_list.addItem(item)
        self.set_offline_running(False)

    def show_offline_failed(self, message: str):
        self.offline_status.setText('失败：%s' % (message or '未知错误'))
        self.set_offline_running(False)

    def show_offline_cancelled(self, message: str = ''):
        self.offline_status.setText(message or '制作已取消')
        self.offline_progress.setValue(0)
        self._set_phase('')
        self.set_offline_running(False)

    def import_models(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            '导入 RVC 模型',
            str(self.project_root),
            'RVC 模型 (*.pth);;Index 索引 (*.index);;全部 (*.pth *.index)',
        )
        if not paths:
            return
        self._weights_dir().mkdir(parents=True, exist_ok=True)
        self._indices_dir().mkdir(parents=True, exist_ok=True)
        prev = self.offline_model.currentText()
        copied_pth, copied_idx, skipped = [], [], []
        for src in paths:
            name = Path(src).name
            suffix = Path(src).suffix.lower()
            if suffix == '.pth':
                target = self._weights_dir() / name
                copied_pth.append(name)
            elif suffix == '.index':
                target = self._indices_dir() / name
                copied_idx.append(name)
            else:
                skipped.append(name)
                continue
            shutil.copy2(src, target)
        self._reload_model_combo()
        pick = copied_pth[-1] if copied_pth else prev
        if pick:
            idx = self.offline_model.findText(pick)
            if idx >= 0:
                self.offline_model.setCurrentIndex(idx)
        self._update_index_hint()
        parts = []
        if copied_pth:
            parts.append('模型：%s' % '、'.join(copied_pth))
        if copied_idx:
            parts.append('Index：%s' % '、'.join(copied_idx))
        if skipped:
            parts.append('已跳过：%s' % '、'.join(skipped))
        msg = '\n'.join(parts) if parts else '未导入任何文件'
        QMessageBox.information(self, '导入完成', msg)
        all_files = copied_pth + copied_idx
        if all_files:
            self.bridge.emit_action('model_import', files=all_files, log='已导入: %s' % ', '.join(all_files))
