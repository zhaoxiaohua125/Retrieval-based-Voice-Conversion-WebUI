"""主窗口顶栏：SoundTrail 风格三 Tab 导航。"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class HeaderBar(QWidget):
    """播放 / 制作歌曲 / 公告 一级导航。"""

    tab_changed = pyqtSignal(int)

    TAB_PLAYBACK = 0
    TAB_SONG_MAKE = 1
    TAB_ANNOUNCE = 2
    TAB_NAMES = ('播放', '制作歌曲', '公告')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel('RVC 声迹')
        self.title.setStyleSheet('font-size: 18px; font-weight: bold; color: #2563eb;')
        layout.addWidget(self.title)
        layout.addStretch()
        for index, name in enumerate(self.TAB_NAMES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self.set_active_tab(i))
            self._buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch()
        self.btn_settings = QPushButton('设置')
        self.btn_settings.setFlat(True)
        layout.addWidget(self.btn_settings)
        self.set_active_tab(self.TAB_SONG_MAKE)

    def set_active_tab(self, index: int):
        index = max(0, min(index, len(self._buttons) - 1))
        for i, btn in enumerate(self._buttons):
            active = i == index
            btn.setChecked(active)
            btn.setStyleSheet(
                'padding: 8px 20px; border-radius: 16px;'
                + ('background:#2563eb;color:white;' if active else 'background:#eef2ff;color:#334155;')
            )
        self.tab_changed.emit(index)
