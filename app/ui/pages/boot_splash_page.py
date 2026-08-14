"""启动闪屏：免登录时显示初始化/扫库进度。"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

_PAGE_STYLE = """
BootSplashPage {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1e6fd9, stop:0.45 #3b8eed, stop:1 #2563c7);
}
BootSplashPage QWidget#bootInner {
    background: transparent;
}
BootSplashPage QLabel {
    background: transparent;
    border: none;
}
"""


class _BootProgressBar(QWidget):
    """底轨 + 滑块 move()，不依赖 paintEvent。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 6)
        self._x = -70
        self._track = QFrame(self)
        self._track.setGeometry(0, 0, 260, 6)
        self._track.setStyleSheet('QFrame{background:rgba(0,0,0,0.22);border:none;border-radius:3px;}')
        self._chunk = QFrame(self)
        self._chunk.setFixedSize(70, 6)
        self._chunk.setStyleSheet('QFrame{background:#ffffff;border:none;border-radius:3px;}')
        self._chunk.raise_()
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._tick)

    def start_anim(self):
        self._x = -self._chunk.width()
        self._chunk.move(self._x, 0)
        if not self._timer.isActive():
            self._timer.start()

    def stop_anim(self):
        self._timer.stop()

    def _tick(self):
        self._x += 5
        if self._x > self.width():
            self._x = -self._chunk.width()
        self._chunk.move(int(self._x), 0)


class BootSplashPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('BootSplashPage')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor('#3b8eed'))
        self.setPalette(pal)
        self.setStyleSheet(_PAGE_STYLE)
        self._status_base = '正在扫描歌库'
        self._dot_i = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 24)
        outer.addStretch(1)
        inner = QWidget()
        inner.setObjectName('bootInner')
        col = QVBoxLayout(inner)
        col.setSpacing(14)
        col.setContentsMargins(0, 0, 0, 0)
        self.lbl_title = QLabel('来取文化')
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet('color:#ffffff;font-size:26px;font-weight:700;')
        self.lbl_status = QLabel('正在扫描歌库…')
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet('color:#e8f2ff;font-size:15px;')
        self.progress = _BootProgressBar()
        col.addWidget(self.lbl_title)
        col.addWidget(self.lbl_status)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.progress)
        row.addStretch()
        col.addLayout(row)
        box = QHBoxLayout()
        box.addStretch()
        box.addWidget(inner)
        box.addStretch()
        outer.addLayout(box)
        outer.addStretch(1)
        try:
            from app.ops.version import CLIENT_VERSION
            ver = CLIENT_VERSION
        except Exception:
            ver = 'dev'
        self.lbl_ver = QLabel('v%s' % ver)
        self.lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ver.setStyleSheet('color:#cfe0fb;font-size:12px;')
        outer.addWidget(self.lbl_ver)
        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(350)
        self._dot_timer.timeout.connect(self._tick_dots)
        QTimer.singleShot(0, self._start_anim)

    def _start_anim(self):
        self.progress.start_anim()
        if not self._dot_timer.isActive():
            self._dot_timer.start()

    def _tick_dots(self):
        self._dot_i = (self._dot_i + 1) % 4
        dots = '…' if self._dot_i == 0 else '.' * self._dot_i
        self.lbl_status.setText('%s%s' % (self._status_base, dots))

    def showEvent(self, event):
        super().showEvent(event)
        self._start_anim()

    def hideEvent(self, event):
        self._dot_timer.stop()
        self.progress.stop_anim()
        super().hideEvent(event)

    def pump(self):
        self.progress._tick()
        self._dot_i = (self._dot_i + 1) % 4
        dots = '…' if self._dot_i == 0 else '.' * self._dot_i
        self.lbl_status.setText('%s%s' % (self._status_base, dots))
        self.progress.repaint()
        self.repaint()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_status(self, text: str):
        if text:
            self._status_base = text.rstrip('.').rstrip('…')
            self._dot_i = 0
            self.lbl_status.setText('%s…' % self._status_base)
        self._start_anim()
