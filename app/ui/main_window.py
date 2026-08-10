"""主窗口 Shell：顶栏三 Tab + 页面栈 + 底状态栏/日志。"""

import threading
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
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
from app.ui.playback_shortcuts import PlaybackShortcutBinder
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """SoundTrail 风格：播放 | 制作歌曲 | 公告。"""

    TAB_NAMES = HeaderBar.TAB_NAMES

    def __init__(self, bridge, project_root=None, config_store=None):
        super().__init__()
        self.bridge = bridge
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        if config_store is None:
            from app.config_store import ConfigStore
            config_store = ConfigStore().load()
        self.config_store = config_store
        self._controller = None
        self.setWindowTitle('RVC 声迹客户端 v%s' % self._client_version())
        self.resize(1280, 800)
        self._build_ui()
        self._restore_layout()
        self._gpu_timer = QTimer(self)
        self._gpu_timer.timeout.connect(self._refresh_gpu_status)
        self._gpu_timer.start(8000)
        self._quitting = False
        self._quit_worker = None
        self._quit_timer = None
        self._quit_shutdown = None

    @staticmethod
    def _client_version():
        try:
            from app.ops.version import CLIENT_VERSION
            return CLIENT_VERSION
        except Exception:
            return 'dev'

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
        self._shortcut_binder = PlaybackShortcutBinder(
            self, self.page_playback, self.config_store, playback_tab_index=HeaderBar.TAB_PLAYBACK
        )

    @property
    def song_make_page(self):
        return self.page_song_make

    def set_controller(self, controller):
        self._controller = controller

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
        snap = self._controller.snapshot_playback() if self._controller else None
        dlg = SettingsDialog(
            self.bridge, self.config_store, project_root=self.project_root,
            song_make_page=self.page_song_make, parent=self,
        )
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if accepted:
            payload = dlg.collect_payload()
            layout = load_ui_layout()
            layout['settings'] = {
                'osc_port': payload['osc_port'],
                'update_url': payload['update_url'],
                'log_dir': payload['log_dir'],
            }
            save_ui_layout(layout)
            self.bridge.emit_action('settings_save', **payload, log='设置已保存到 config/client.json')
            self._shortcut_binder.apply(self.config_store)
        if self._controller:
            self._controller.restore_playback_after_settings(snap)

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
            x, y, w, h = [int(v) for v in geo]
            from PyQt6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                w = max(640, min(w, avail.width()))
                h = max(480, min(h, avail.height()))
                off_screen = x + 40 < avail.left() or x > avail.right() - 40 or y + 40 < avail.top() or y > avail.bottom() - 40
                if off_screen:
                    x = avail.x() + max(0, (avail.width() - w) // 2)
                    y = avail.y() + max(0, (avail.height() - h) // 2)
            self.setGeometry(x, y, w, h)
        tab = layout.get('active_nav_tab', layout.get('active_tab', HeaderBar.TAB_SONG_MAKE))
        if isinstance(tab, int) and 0 <= tab < self.stack.count():
            self.header.set_active_tab(tab)
            self.stack.setCurrentIndex(tab)

    def _save_window_layout(self):
        layout = load_ui_layout()
        g = self.geometry()
        layout['geometry'] = [g.x(), g.y(), g.width(), g.height()]
        layout['active_nav_tab'] = self.stack.currentIndex()
        save_ui_layout(layout)

    def request_quit(self, confirm=True):
        if self._quitting:
            return True
        if confirm:
            btn = QMessageBox.question(
                self,
                '确认退出',
                '确定要退出 RVC 声迹客户端吗？\n进行中的任务将被停止。',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if btn != QMessageBox.StandardButton.Yes:
                return False
        self._quitting = True
        self._save_window_layout()
        self._gpu_timer.stop()
        self.setEnabled(False)
        self.status.showMessage('正在退出，请稍候…')
        self._quit_worker = threading.Thread(target=self._run_shutdown, name='app-quit', daemon=True)
        self._quit_worker.start()
        self._quit_timer = QTimer(self)
        self._quit_timer.timeout.connect(self._finish_quit)
        self._quit_timer.start(50)
        return True

    def _run_shutdown(self):
        fn = self._quit_shutdown
        if fn:
            try:
                fn()
            except Exception:
                pass

    def _finish_quit(self):
        if self._quit_worker and self._quit_worker.is_alive():
            return
        if self._quit_timer:
            self._quit_timer.stop()
        lyrics = getattr(self, '_quit_lyrics', None)
        if lyrics is not None:
            lyrics.close()
        tray = getattr(self, '_quit_tray', None)
        if tray is not None:
            tray.hide()
        self.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.request_quit(confirm=True)
