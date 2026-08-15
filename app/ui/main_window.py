"""主窗口 Shell：登录 → 顶栏三 Tab + 页面栈 + 底状态栏/日志。"""

import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
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
from app.ui.pages import AnnouncePage, BootSplashPage, LoginPage, PlaybackPage, SongMakePage
from app.ui.playback_shortcuts import PlaybackShortcutBinder
from app.ui.qt_util import clicked
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """SoundTrail 风格：播放 | 制作歌曲 | 公告。"""

    TAB_NAMES = HeaderBar.TAB_NAMES
    main_entered = pyqtSignal()
    _login_result = pyqtSignal(dict)
    _gpu_status_ready = pyqtSignal(str)

    def __init__(self, bridge, project_root=None, config_store=None):
        super().__init__()
        self.bridge = bridge
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        if config_store is None:
            from app.config_store import ConfigStore
            config_store = ConfigStore().load()
        self.config_store = config_store
        self._require_login = bool(config_store.get('auth.show_login', True))
        self._app_name = str(config_store.get('brand.app_name', '来趣文化') or '来趣文化')
        self._product_name = str(config_store.get('brand.product_name', '唱歌伴侣') or '唱歌伴侣')
        self._controller = None
        self._main_ready = False
        self._backend_ready = False
        self._login_pending = False
        self._auth_token = ''
        self._auth_user = None
        self._pending_nav_tab = HeaderBar.TAB_PLAYBACK
        self._page_playback = None
        self._page_song_make = None
        self._page_announce = None
        self._shell_frame = False
        self._load_slot = None
        self._shortcut_binder = None
        self._gpu_probe_busy = False
        self.setWindowTitle('%s v%s' % (self._app_name, self._client_version()))
        self.resize(1280, 800)
        self._build_ui()
        self._login_result.connect(self._on_login_result)
        self._gpu_status_ready.connect(self._on_gpu_status_ready)
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

    def require_login(self) -> bool:
        return self._require_login

    def is_main_ready(self) -> bool:
        return self._main_ready

    def is_backend_ready(self) -> bool:
        return self._backend_ready

    def mark_backend_ready(self):
        self._backend_ready = True
        if self._login_pending:
            if self._require_login:
                self.page_login.set_status('正在进入…')
            else:
                self.page_boot.set_status('正在进入…')
            QTimer.singleShot(0, self._enter_main)

    def begin_guest_boot(self):
        if self._require_login or self._main_ready:
            return
        self._login_pending = True
        self.page_boot.set_status('正在初始化…')
        self.page_boot.progress.start_anim()

    def on_boot_failed(self):
        self._login_pending = False
        if self._require_login:
            self.page_login.set_busy(False)

    def set_login_wait_text(self, text: str):
        if self._require_login and (self._login_pending or not self.page_login.btn_login.isEnabled()):
            self.page_login.set_busy_text(text)

    def set_boot_status(self, text: str):
        if self._main_ready:
            return
        if self._require_login:
            if self._login_pending or not self.page_login.btn_login.isEnabled():
                self.page_login.set_busy_text(text)
            else:
                self.page_login.set_boot_hint(text)
        else:
            self.page_boot.set_status(text)

    def _pump_boot_splash(self):
        if self._require_login or self._main_ready:
            QApplication.processEvents()
            return
        self.page_boot.pump()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.root_stack = QStackedWidget()
        outer.addWidget(self.root_stack)
        self.page_boot = BootSplashPage()
        self.page_login = LoginPage(self.bridge, app_name=self._app_name)
        self.page_login.login_requested.connect(self._on_login_requested)
        if self._require_login:
            self.root_stack.addWidget(self.page_login)
            self.root_stack.setCurrentWidget(self.page_login)
        else:
            self.root_stack.addWidget(self.page_boot)
            self.root_stack.setCurrentWidget(self.page_boot)
        self.main_shell = QWidget()
        self.root_stack.addWidget(self.main_shell)

    def _clear_boot_chrome(self):
        self.root_stack.setStyleSheet('')
        root = self.centralWidget()
        if root is not None:
            root.setAutoFillBackground(False)
            root.setPalette(QApplication.style().standardPalette())

    def _build_main_shell_frame(self):
        if self._shell_frame:
            return
        shell = QVBoxLayout(self.main_shell)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.header = HeaderBar(product_name=self._product_name)
        self.header.tab_changed.connect(self._on_nav_changed)
        self.header.btn_settings.clicked.connect(clicked(self._open_settings_dialog))
        shell.addWidget(self.header)
        self.stack = QStackedWidget()
        self._load_slot = QLabel('正在加载播放页…')
        self._load_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_slot.setStyleSheet('font-size:16px;color:#64748b;background:#f8fafc;')
        self.stack.addWidget(self._load_slot)
        self._slot_make = QWidget()
        self._slot_announce = QWidget()
        self.stack.addWidget(self._slot_make)
        self.stack.addWidget(self._slot_announce)
        shell.addWidget(self.stack, stretch=1)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText('运行日志…')
        self.log_view.setMaximumHeight(120)
        shell.addWidget(self.log_view)
        self.status = QStatusBar()
        shell.addWidget(self.status)
        self.status.showMessage('就绪')
        self.plugin_label = QLabel('● 插件已连接')
        self.plugin_label.setStyleSheet('color:#16a34a;')
        self.gpu_label = QLabel('GPU: --')
        self.status.addPermanentWidget(self.gpu_label)
        self.status.addPermanentWidget(self.plugin_label)
        self.bridge.log_message.connect(self.append_log)
        self._shell_frame = True

    def _build_playback_page(self):
        if self._page_playback is not None:
            return
        pump = None if self._require_login else self._pump_boot_splash
        if pump:
            pump()
        self._page_playback = PlaybackPage(self.bridge, ui_pump=pump)
        if pump:
            pump()
        if self._load_slot is not None:
            self.stack.removeWidget(self._load_slot)
            self._load_slot.deleteLater()
            self._load_slot = None
        self.stack.insertWidget(HeaderBar.TAB_PLAYBACK, self._page_playback)
        self._shortcut_binder = PlaybackShortcutBinder(
            self, self._page_playback, self.config_store, playback_tab_index=HeaderBar.TAB_PLAYBACK
        )
        self._main_ready = True
        tab = self._pending_nav_tab
        if isinstance(tab, int) and 0 <= tab < self.stack.count():
            self.header.set_active_tab(tab)
        QTimer.singleShot(0, self._refresh_gpu_status)

    def _ensure_main_shell(self):
        if self._main_ready:
            return
        self._build_main_shell_frame()
        self._build_playback_page()

    def _ensure_tab_page(self, index: int):
        if index == HeaderBar.TAB_SONG_MAKE and self._page_song_make is None:
            self._page_song_make = SongMakePage(self.bridge, project_root=self.project_root)
            self.stack.removeWidget(self._slot_make)
            self._slot_make.deleteLater()
            self._slot_make = None
            self.stack.insertWidget(HeaderBar.TAB_SONG_MAKE, self._page_song_make)
        elif index == HeaderBar.TAB_ANNOUNCE and self._page_announce is None:
            self._page_announce = AnnouncePage(self.bridge)
            self.stack.removeWidget(self._slot_announce)
            self._slot_announce.deleteLater()
            self._slot_announce = None
            self.stack.insertWidget(HeaderBar.TAB_ANNOUNCE, self._page_announce)

    @property
    def page_song_make(self):
        self._ensure_main_shell()
        self._ensure_tab_page(HeaderBar.TAB_SONG_MAKE)
        return self._page_song_make

    @property
    def page_announce(self):
        self._ensure_main_shell()
        self._ensure_tab_page(HeaderBar.TAB_ANNOUNCE)
        return self._page_announce

    @property
    def page_playback(self):
        self._ensure_main_shell()
        return self._page_playback

    @property
    def song_make_page(self):
        return self.page_song_make

    def set_controller(self, controller):
        self._controller = controller

    def _on_nav_changed(self, index: int):
        if not self._main_ready:
            return
        self._ensure_tab_page(index)
        self.stack.setCurrentIndex(index)
        name = self.TAB_NAMES[index] if 0 <= index < len(self.TAB_NAMES) else ''
        self.status.showMessage('切换到%s页面' % name)
        self.bridge.emit_action('nav_tab', index=index, name=name)

    def _on_login_requested(self, username: str, password: str):
        self.page_login.set_status('正在登录…')

        def _work():
            try:
                from app.ops.auth_client import login as remote_login
                result = remote_login(username, password, self.config_store)
            except Exception as exc:
                result = {'ok': False, 'message': '登录异常：%s' % exc}
            self._login_result.emit(result)

        threading.Thread(target=_work, name='login-auth', daemon=True).start()

    def _on_login_result(self, result: dict):
        if not result.get('ok'):
            msg = result.get('message') or '登录失败'
            self.page_login.show_error(msg)
            QMessageBox.warning(self, '登录失败', msg)
            return
        self._auth_token = str(result.get('token') or '')
        self._auth_user = result.get('user') or {}
        name = str((self._auth_user or {}).get('user_real') or (self._auth_user or {}).get('user_name') or '')
        self.bridge.emit_action('login', log='登录成功：%s' % (name or '用户'))
        self._on_login_success()

    def _on_login_success(self):
        if self._backend_ready:
            self.page_login.set_status('正在加载界面…')
            QTimer.singleShot(0, self._enter_main)
            return
        self._login_pending = True
        self.page_login.set_status('正在初始化…')

    def _enter_main(self):
        if self._require_login:
            self.page_login.set_status('正在加载界面…')
        else:
            self.page_boot.set_status('正在加载界面…')
        QTimer.singleShot(10, self._enter_main_build)

    def _enter_main_build(self):
        if self._require_login:
            self.page_login.set_busy_text('正在加载播放页…')
        else:
            self.page_boot.set_status('正在加载播放页')
            self.page_boot.progress.start_anim()
        QApplication.processEvents()
        QTimer.singleShot(0, self._enter_main_load)

    def _enter_main_load(self):
        self._build_main_shell_frame()
        QApplication.processEvents()
        if not self._require_login:
            self.page_boot.progress.start_anim()
        self._build_playback_page()
        QApplication.processEvents()
        self._enter_main_show()
        self._enter_main_finish()

    def _enter_main_show(self):
        if not self._require_login:
            self._clear_boot_chrome()
        self.root_stack.setCurrentWidget(self.main_shell)
        self.header.set_active_tab(HeaderBar.TAB_PLAYBACK)
        if self._require_login:
            self.page_login.set_busy(False)
        self._login_pending = False

    def _enter_main_finish(self):
        self.status.showMessage('已进入播放页' if not self._require_login else '登录成功，已进入播放页')
        QTimer.singleShot(0, self._emit_main_entered)
        self.bridge.emit_action('login_success', log='已进入播放页')

    def _emit_main_entered(self):
        self.main_entered.emit()

    def switch_to_playback(self, song_title: str | None = None):
        if not self._main_ready:
            self._pending_nav_tab = HeaderBar.TAB_PLAYBACK
            return
        self.header.set_active_tab(HeaderBar.TAB_PLAYBACK)
        if song_title:
            self.page_playback.select_song_by_title(song_title)

    def _open_settings_dialog(self):
        self._ensure_main_shell()
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
        if not self._main_ready:
            return
        self.log_view.append(text)

    def _on_gpu_status_ready(self, text: str):
        self._gpu_probe_busy = False
        if self._main_ready and getattr(self, 'gpu_label', None) is not None:
            self.gpu_label.setText(text)

    def _probe_gpu_worker(self):
        try:
            from app.ops.hardware import collect_environment_info
            cuda = collect_environment_info().get('cuda', {})
            if cuda.get('available'):
                text = 'GPU: %s %sGB' % (cuda.get('device_name', 'CUDA'), cuda.get('total_memory_gb', ''))
            else:
                text = 'GPU: CPU 模式'
        except Exception:
            text = 'GPU: 未检测'
        self._gpu_status_ready.emit(text)

    def _refresh_gpu_status(self):
        if not self._main_ready or self._gpu_probe_busy:
            return
        if getattr(self, 'gpu_label', None) is None:
            return
        self._gpu_probe_busy = True
        if self.gpu_label.text() in ('GPU: --', 'GPU: 检测中…'):
            self.gpu_label.setText('GPU: 检测中…')
        threading.Thread(target=self._probe_gpu_worker, name='gpu-probe', daemon=True).start()

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
        tab = layout.get('active_nav_tab', layout.get('active_tab', HeaderBar.TAB_PLAYBACK))
        if isinstance(tab, int) and 0 <= tab < len(HeaderBar.TAB_NAMES):
            self._pending_nav_tab = tab

    def _save_window_layout(self):
        if not self._main_ready:
            return
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
                '确定要退出 %s吗？\n进行中的任务将被停止。' % self._app_name,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if btn != QMessageBox.StandardButton.Yes:
                return False
        self._quitting = True
        if self._main_ready:
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
