"""登录页：提交账号密码，由主窗口调用后台登录接口。"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.qt_util import clicked

_PAGE_STYLE = """
LoginPage {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #dbeafe, stop:0.45 #f8fafc, stop:1 #e0e7ff);
}
#loginCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
}
QLineEdit {
    padding: 11px 14px;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    background: #f8fafc;
    font-size: 14px;
    color: #0f172a;
}
QLineEdit:focus {
    border: 1px solid #2563eb;
    background: #ffffff;
}
"""


class LoginPage(QWidget):
    login_requested = pyqtSignal(str, str)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setObjectName('LoginPage')
        self.setStyleSheet(_PAGE_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(2)
        card = QFrame()
        card.setObjectName('loginCard')
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 28)
        card_layout.setSpacing(10)
        # badge = QLabel('来取文化')
        # badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # badge.setFixedSize(65, 65)
        # badge.setStyleSheet(
        #     'background:#2563eb;color:#fff;font-size:15px;font-weight:700;border-radius:26px;'
        # )
        title = QLabel('来趣文化')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size:26px;font-weight:700;color:#0f172a;margin-top:4px;')
        sub = QLabel('登录后使用客户端')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet('color:#64748b;font-size:13px;margin-bottom:8px;')
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        # badge_row.addWidget(badge)
        badge_row.addStretch()
        card_layout.addLayout(badge_row)
        card_layout.addWidget(title)
        card_layout.addWidget(sub)
        user_lbl = QLabel('账号')
        user_lbl.setStyleSheet('color:#475569;font-size:13px;font-weight:600;margin-top:6px;')
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText('请输入用户名')
        pass_lbl = QLabel('密码')
        pass_lbl.setStyleSheet('color:#475569;font-size:13px;font-weight:600;margin-top:4px;')
        self.edit_pass = QLineEdit()
        self.edit_pass.setPlaceholderText('请输入密码')
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass.returnPressed.connect(clicked(self._on_login))
        card_layout.addWidget(user_lbl)
        card_layout.addWidget(self.edit_user)
        card_layout.addWidget(pass_lbl)
        card_layout.addWidget(self.edit_pass)
        self.btn_login = QPushButton('登 录')
        self.btn_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_login.setStyleSheet(
            'QPushButton{margin-top:14px;padding:12px;border:none;border-radius:10px;'
            'background:#2563eb;color:#fff;font-size:15px;font-weight:600;}'
            'QPushButton:hover{background:#1d4ed8;}'
            'QPushButton:pressed{background:#1e40af;}'
            'QPushButton:disabled{background:#93c5fd;color:#eff6ff;}'
        )
        self.btn_login.clicked.connect(clicked(self._on_login))
        card_layout.addWidget(self.btn_login)
        self.lbl_hint = QLabel('后台加载中；点击登录后若未完成将显示进度')
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hint.setStyleSheet('color:#94a3b8;font-size:12px;margin-top:6px;')
        card_layout.addWidget(self.lbl_hint)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch(3)

    def set_busy(self, busy: bool, text: str = '正在进入…'):
        self.btn_login.setEnabled(not busy)
        self.btn_login.setText(text if busy else '登 录')
        self.edit_user.setEnabled(not busy)
        self.edit_pass.setEnabled(not busy)
        if busy:
            self.lbl_hint.setText(text)
            self.lbl_hint.setStyleSheet('color:#64748b;font-size:12px;margin-top:6px;')
        else:
            self.lbl_hint.setStyleSheet('color:#94a3b8;font-size:12px;margin-top:6px;')
        app = QApplication.instance()
        if app is not None:
            app.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor))
            if busy:
                app.processEvents()

    def set_busy_text(self, text: str):
        if not self.btn_login.isEnabled():
            self.btn_login.setText(text)
            self.lbl_hint.setText(text)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

    def show_error(self, text: str):
        self.set_busy(False)
        self.lbl_hint.setText(text)
        self.lbl_hint.setStyleSheet('color:#dc2626;font-size:12px;margin-top:6px;')

    def set_status(self, text: str):
        self.set_busy(True, text)

    def set_boot_hint(self, text: str):
        if self.btn_login.isEnabled():
            self.lbl_hint.setText(text)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

    def _on_login(self):
        username = self.edit_user.text().strip()
        password = self.edit_pass.text()
        if not username:
            self.set_boot_hint('请输入账号')
            self.edit_user.setFocus()
            return
        if not password:
            self.set_boot_hint('请输入密码')
            self.edit_pass.setFocus()
            return
        self.set_status('正在登录…')
        self.login_requested.emit(username, password)
