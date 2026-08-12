"""公告 Tab 骨架。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget

from app.ui.qt_util import clicked


class AnnouncePage(QWidget):
    """对标 SoundTrail「公告」页：列表 + 详情。"""

    DEMO_ITEMS = (
        ('客户端骨架已就绪', '2026-08-04', 'UI 三 Tab 结构已对齐 SoundTrail，功能将分阶段接入。'),
        ('离线做歌链路', '2026-08-04', 'MSST 多阶段 + RVC 离线推理已在 app/rvc 完成，待 UI 集成。'),
    )

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        row = QHBoxLayout()
        row.addWidget(QLabel('公告列表'))
        btn_refresh = QPushButton('刷新')
        btn_refresh.clicked.connect(clicked(self._reload))
        row.addStretch()
        row.addWidget(btn_refresh)
        left_layout.addLayout(row)
        self.list = QListWidget()
        left_layout.addWidget(self.list)
        splitter.addWidget(left)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(1, 1)

        self.list.currentRowChanged.connect(self._show_detail)
        self._reload()

    def _reload(self):
        self.list.clear()
        for title, date, _ in self.DEMO_ITEMS:
            self.list.addItem('%s  %s' % (title, date))
        if self.list.count():
            self.list.setCurrentRow(0)
        self.bridge.emit_action('announce_refresh', log='公告列表已刷新（本地占位）')

    def _show_detail(self, row):
        if row < 0 or row >= len(self.DEMO_ITEMS):
            self.detail.clear()
            return
        title, date, body = self.DEMO_ITEMS[row]
        self.detail.setPlainText('%s\n%s\n\n%s' % (title, date, body))
