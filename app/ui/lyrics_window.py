"""悬浮歌词窗口（无边框、置顶、可拖拽；支持逐字高亮）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LyricsWindow(QWidget):
    """独立悬浮歌词层，供 OBS 采集。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.9)
        self.label = QLabel('歌词悬浮窗', self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            'color: #ffffff; background: rgba(0,0,0,170); padding: 16px; border-radius: 8px;'
        )
        font = QFont('Microsoft YaHei UI', 20)
        self.label.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.resize(560, 140)

    def set_line(self, text, highlight=False):
        color = '#fbbf24' if highlight else '#ffffff'
        self.label.setText('<span style="color:%s;">%s</span>' % (color, text or ''))

    def set_lyric_tick(self, payload: dict):
        html = (payload or {}).get('html') or ''
        text = (payload or {}).get('text') or ''
        if html and (payload or {}).get('has_words'):
            self.label.setText(html)
        else:
            self.set_line(text, highlight=True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
