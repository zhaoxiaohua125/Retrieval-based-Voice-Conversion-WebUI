"""播放 Tab 骨架：歌库 + 波形区 + 歌词/改词侧栏（功能后续接入）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PlaybackPage(QWidget):
    """对标 SoundTrail「播放」页。"""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        lib = QWidget()
        lib_layout = QVBoxLayout(lib)
        lib_layout.addWidget(QLabel('我的歌库'))
        self.song_list = QListWidget()
        self.song_list.addItems(['（歌库模块待接入）', '示例：张学友 - 离开以后'])
        lib_layout.addWidget(self.song_list)
        splitter.addWidget(lib)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel('播放显示区 / 波形（阶段 3/6 接入）'), stretch=1)
        wave = QLabel('▁▂▃▅▇ 波形占位 ▇▅▃▂▁')
        wave.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wave.setStyleSheet('background:#f1f5f9; padding: 48px; border-radius: 8px;')
        center_layout.addWidget(wave)
        ctrl = QHBoxLayout()
        for label, action in (
            ('AI 跟唱', 'playback_ai_follow'),
            ('AI 唱歌', 'playback_ai_sing'),
            ('混响说话', 'playback_reverb_talk'),
            ('普通说话', 'playback_normal_talk'),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _, a=action, t=label: self.bridge.emit_action(a, log='%s：音频模块未接入' % t)
            )
            ctrl.addWidget(btn)
        center_layout.addLayout(ctrl)
        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel('歌词列表 / 改词（阶段 6 接入）'))
        self.lyrics_list = QListWidget()
        self.lyrics_list.addItems(['01 歌词行占位…', '02 …'])
        right_layout.addWidget(self.lyrics_list)
        right_layout.addWidget(QLabel('目标歌词'))
        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlaceholderText('改词编辑区占位')
        self.lyrics_edit.setMaximumHeight(100)
        right_layout.addWidget(self.lyrics_edit)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
