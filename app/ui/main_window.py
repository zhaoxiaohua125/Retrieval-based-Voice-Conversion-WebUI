"""主窗口 Shell：顶栏三 Tab + 页面栈 + 底状态栏/日志。"""

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from app.ui.header_bar import HeaderBar
from app.ui.layout_store import load_ui_layout, save_ui_layout
from app.ui.pages import AnnouncePage, PlaybackPage, SongMakePage


class MainWindow(QMainWindow):
    """SoundTrail 风格：播放 | 制作歌曲 | 公告。"""

    TAB_NAMES = HeaderBar.TAB_NAMES

    def __init__(self, bridge, project_root=None):
        super().__init__()
        self.bridge = bridge
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.setWindowTitle('RVC 声迹客户端')
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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = HeaderBar()
        self.header.tab_changed.connect(self._on_nav_changed)
        self.header.btn_settings.clicked.connect(self._open_settings_dialog)
        outer.addWidget(self.header)

        self.stack = QStackedWidget()
        self.page_playback = PlaybackPage(self.bridge)
        self.page_song_make = SongMakePage(self.bridge, project_root=self.project_root)
        self.page_announce = AnnouncePage(self.bridge)
        self.stack.addWidget(self.page_playback)
        self.stack.addWidget(self.page_song_make)
        self.stack.addWidget(self.page_announce)
        outer.addWidget(self.stack, stretch=1)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText('运行日志…')
        self.log_view.setMaximumHeight(120)
        outer.addWidget(self.log_view)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage('就绪')
        self.plugin_label = QLabel('● 插件已连接')
        self.plugin_label.setStyleSheet('color:#16a34a;')
        self.gpu_label = QLabel('GPU: --')
        self.status.addPermanentWidget(self.gpu_label)
        self.status.addPermanentWidget(self.plugin_label)
        self.bridge.log_message.connect(self.append_log)

    @property
    def song_make_page(self):
        return self.page_song_make

    def _on_nav_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        name = self.TAB_NAMES[index] if 0 <= index < len(self.TAB_NAMES) else ''
        self.status.showMessage('切换到%s页面' % name)
        self.bridge.emit_action('nav_tab', index=index, name=name)

    def switch_to_playback(self, song_title: str | None = None):
        self.header.set_active_tab(HeaderBar.TAB_PLAYBACK)
        if song_title:
            self.page_playback.select_song_by_title(song_title)

    def _open_settings_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('系统设置')
        layout = QVBoxLayout(dlg)
        form = QFormLayout()
        self.set_osc_port = QSpinBox()
        self.set_osc_port.setRange(1, 65535)
        self.set_osc_port.setValue(9000)
        self.set_update_url = QLineEdit('')
        self.set_log_dir = QLineEdit('logs/client')
        form.addRow('OSC 端口', self.set_osc_port)
        form.addRow('更新地址', self.set_update_url)
        form.addRow('日志目录', self.set_log_dir)
        layout.addLayout(form)
        btn_import = QPushButton('导入 RVC 模型…')
        btn_import.clicked.connect(self.page_song_make.import_models)
        btn_save = QPushButton('保存设置')
        btn_save.clicked.connect(lambda: (self._save_settings(), dlg.accept()))
        layout.addWidget(btn_import)
        layout.addWidget(btn_save)
        layout_data = load_ui_layout().get('settings') or {}
        if layout_data.get('osc_port'):
            self.set_osc_port.setValue(int(layout_data['osc_port']))
        self.set_update_url.setText(layout_data.get('update_url', ''))
        self.set_log_dir.setText(layout_data.get('log_dir', 'logs/client'))
        dlg.exec()

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
        tab = layout.get('active_nav_tab', layout.get('active_tab', HeaderBar.TAB_SONG_MAKE))
        if isinstance(tab, int) and 0 <= tab < self.stack.count():
            self.header.set_active_tab(tab)
            self.stack.setCurrentIndex(tab)

    def closeEvent(self, event):
        layout = load_ui_layout()
        g = self.geometry()
        layout['geometry'] = [g.x(), g.y(), g.width(), g.height()]
        layout['active_nav_tab'] = self.stack.currentIndex()
        save_ui_layout(layout)
        event.accept()
