"""悬浮歌词窗口（无边框、置顶、可拖拽）。"""

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LyricsWindow(QWidget):
    """独立悬浮歌词层，供 OBS 采集；首版仅展示与高亮占位。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.85)
        self.label = QLabel('歌词悬浮窗\n（等待 LRC 同步模块接入）', self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(
            'color: #ffffff; background: rgba(0,0,0,160); padding: 16px; border-radius: 8px;'
        )
        font = QFont('Microsoft YaHei UI', 16)
        self.label.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.resize(480, 120)

    def set_line(self, text, highlight=False):
        color = '#ffd54f' if highlight else '#ffffff'
        self.label.setStyleSheet(
            'color: %s; background: rgba(0,0,0,160); padding: 16px; border-radius: 8px;' % color
        )
        self.label.setText(text or '')

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
