"""发现新版本时的更新提示与进度。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class UpdatePromptDialog(QDialog):
    def __init__(self, bridge, payload: dict, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.payload = dict(payload or {})
        self._updating = False
        self.setWindowTitle('发现新版本')
        self.setMinimumWidth(440)
        self._build_ui()
        self._fill_info()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.lbl_current = QLabel()
        self.lbl_latest = QLabel()
        self.lbl_current.setStyleSheet('color:#64748b;')
        self.lbl_latest.setStyleSheet('font-size:15px;font-weight:600;color:#0f172a;')
        root.addWidget(self.lbl_current)
        root.addWidget(self.lbl_latest)
        self.txt_desc = QTextEdit()
        self.txt_desc.setReadOnly(True)
        self.txt_desc.setMaximumHeight(120)
        root.addWidget(self.txt_desc)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.lbl_status = QLabel('')
        self.lbl_status.setStyleSheet('color:#64748b;font-size:12px;')
        root.addWidget(self.lbl_status)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_later = QPushButton('稍后')
        self.btn_skip = QPushButton('跳过此版本')
        self.btn_update = QPushButton('立即更新')
        self.btn_update.setDefault(True)
        self.btn_later.clicked.connect(self.reject)
        self.btn_skip.clicked.connect(self._on_skip)
        self.btn_update.clicked.connect(self._on_update)
        row.addWidget(self.btn_later)
        row.addWidget(self.btn_skip)
        row.addWidget(self.btn_update)
        root.addLayout(row)
        if self.payload.get('force_update'):
            self.btn_later.hide()
            self.btn_skip.hide()

    def _fill_info(self):
        cur = self.payload.get('current_version') or '未知'
        latest = self.payload.get('latest_version') or '未知'
        self.lbl_current.setText('当前版本：%s' % cur)
        self.lbl_latest.setText('最新版本：%s' % latest)
        desc = str(self.payload.get('update_desc') or '').strip()
        self.txt_desc.setPlainText(desc or '（无更新说明）')

    def _on_skip(self):
        version = str(self.payload.get('latest_version') or '').strip()
        if version:
            self.bridge.emit_action('skip_update', version=version)
        self.accept()

    def _on_update(self):
        if self._updating:
            return
        self._updating = True
        self.btn_later.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.btn_update.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_status.setText('正在下载更新包…')
        self.bridge.emit_action('apply_update', use_patch=True)

    def set_progress(self, percent: int, message: str = ''):
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, int(percent or 0))))
        if message:
            self.lbl_status.setText(message)

    def mark_failed(self, message: str):
        self._updating = False
        self.btn_later.setEnabled(True)
        self.btn_skip.setEnabled(not self.payload.get('force_update'))
        self.btn_update.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_status.setText('')
        QMessageBox.warning(self, '更新失败', message or '未知错误')


def show_update_prompt(parent, bridge, payload: dict):
    dlg = UpdatePromptDialog(bridge, payload, parent=parent)
    if payload.get('force_update'):
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.exec()
        return dlg
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
    return dlg
