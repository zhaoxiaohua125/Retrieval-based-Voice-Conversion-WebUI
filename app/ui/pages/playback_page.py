"""播放 Tab：歌库 + 歌词显示 + AI 唱歌控制。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def _fmt_time(sec: float) -> str:
    sec = max(0.0, float(sec or 0))
    m, s = divmod(int(sec), 60)
    return '%02d:%02d' % (m, s)


class PlaybackPage(QWidget):
    """对标 SoundTrail「播放」页，优先完成 AI 唱歌。"""

    BTN_STYLE = (
        'QPushButton{padding:8px 16px;border-radius:6px;border:1px solid #cbd5e1;background:#fff;}'
        'QPushButton:hover{background:#f8fafc;}'
        'QPushButton:checked{background:#2563eb;color:#fff;border-color:#2563eb;}'
        'QPushButton:disabled{color:#94a3b8;background:#f1f5f9;}'
    )

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._songs = []
        self._selected = None
        self._mode = 'idle'
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        lib = QWidget()
        lib_layout = QVBoxLayout(lib)
        lib_head = QHBoxLayout()
        lib_head.addWidget(QLabel('我的歌库'))
        self.btn_refresh = QPushButton('刷新')
        self.btn_refresh.clicked.connect(lambda: self.bridge.emit_action('playback_refresh_library'))
        lib_head.addStretch()
        lib_head.addWidget(self.btn_refresh)
        lib_layout.addLayout(lib_head)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('搜索我的歌曲')
        self.search_box.textChanged.connect(self._filter_songs)
        lib_layout.addWidget(self.search_box)
        self.song_list = QListWidget()
        self.song_list.currentRowChanged.connect(self._on_row_changed)
        lib_layout.addWidget(self.song_list)
        splitter.addWidget(lib)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.title_label = QLabel('请从歌库选择歌曲')
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet('font-size:18px;color:#64748b;')
        center_layout.addWidget(self.title_label)

        self.lyric_panel = QWidget()
        lyric_layout = QVBoxLayout(self.lyric_panel)
        lyric_layout.setContentsMargins(24, 16, 24, 16)
        lyric_layout.setSpacing(12)
        self.lyric_prev = QLabel('')
        self.lyric_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_prev.setWordWrap(True)
        self.lyric_prev.setStyleSheet('font-size:16px;color:#94a3b8;')
        self.lyric_main = QLabel('—')
        self.lyric_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_main.setWordWrap(True)
        self.lyric_main.setStyleSheet('font-size:32px;font-weight:700;color:#2563eb;padding:8px 0;')
        self.lyric_next = QLabel('')
        self.lyric_next.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_next.setWordWrap(True)
        self.lyric_next.setStyleSheet('font-size:16px;color:#94a3b8;')
        lyric_layout.addStretch()
        lyric_layout.addWidget(self.lyric_prev)
        lyric_layout.addWidget(self.lyric_main)
        lyric_layout.addWidget(self.lyric_next)
        lyric_layout.addStretch()
        self.lyric_panel.setStyleSheet('background:#fff;border-radius:12px;')
        center_layout.addWidget(self.lyric_panel, stretch=1)
        self.wave_label = QLabel('▁▂▃▅▇ 波形占位 ▇▅▃▂▁')
        self.wave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wave_label.setStyleSheet('background:#f1f5f9;padding:32px;border-radius:8px;color:#64748b;')
        center_layout.addWidget(self.wave_label)
        progress_row = QHBoxLayout()
        self.time_label = QLabel('00:00 / 00:00')
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderReleased.connect(self._on_seek)
        progress_row.addWidget(self.time_label)
        progress_row.addWidget(self.progress, stretch=1)
        center_layout.addLayout(progress_row)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        self.btn_play = QPushButton('▶ 播放')
        self.btn_play.clicked.connect(lambda: self.bridge.emit_action('playback_toggle_pause'))
        ctrl.addWidget(self.btn_play)
        self.btn_stop = QPushButton('停止')
        self.btn_stop.clicked.connect(lambda: self.bridge.emit_action('playback_stop'))
        ctrl.addWidget(self.btn_stop)
        self.btn_ai_follow = QPushButton('AI 跟唱')
        self.btn_ai_follow.setToolTip('实时变声（Voicemeeter 路由待联调）')
        self.btn_ai_follow.clicked.connect(lambda: self.bridge.emit_action('playback_ai_follow'))
        ctrl.addWidget(self.btn_ai_follow)
        self.btn_ai_sing = QPushButton('AI 唱歌')
        self.btn_ai_sing.setCheckable(True)
        self.btn_ai_sing.setToolTip('播放离线生成的 AI 成品（cover.wav）')
        self.btn_ai_sing.clicked.connect(self._on_ai_sing)
        ctrl.addWidget(self.btn_ai_sing)
        for btn in (self.btn_play, self.btn_stop, self.btn_ai_follow, self.btn_ai_sing):
            btn.setStyleSheet(self.BTN_STYLE)
        ctrl.addStretch()
        center_layout.addLayout(ctrl)
        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel('歌词进度'))
        self.lyrics_list = QListWidget()
        self.lyrics_list.setStyleSheet('font-size:13px;color:#64748b;')
        right_layout.addWidget(self.lyrics_list)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 760, 180])
        self._lyric_lines = []

    def apply_library(self, songs: list):
        self._songs = list(songs or [])
        self._filter_songs(self.search_box.text())

    def _filter_songs(self, keyword: str):
        keyword = (keyword or '').strip().lower()
        self.song_list.blockSignals(True)
        self.song_list.clear()
        for song in self._songs:
            title = song.get('title', '')
            if keyword and keyword not in title.lower():
                continue
            item = QListWidgetItem(title or '未命名')
            item.setData(Qt.ItemDataRole.UserRole, song)
            self.song_list.addItem(item)
        self.song_list.blockSignals(False)
        if self.song_list.count() and self.song_list.currentRow() < 0:
            self.song_list.setCurrentRow(0)

    def _on_row_changed(self, row: int):
        if row < 0:
            self._selected = None
            return
        item = self.song_list.item(row)
        if not item:
            return
        song = item.data(Qt.ItemDataRole.UserRole) or {}
        self._selected = song
        self.title_label.setText(song.get('title', '未命名'))
        self.bridge.emit_action('playback_select_song', song=song)

    def _on_ai_sing(self):
        if self._selected:
            self.bridge.emit_action('playback_ai_sing', song=self._selected)
        else:
            self.bridge.emit_action('playback_ai_sing', log='请先在歌库中选择歌曲')

    def _on_seek(self):
        pos = self.progress.value() / 1000.0
        self.bridge.emit_action('playback_seek', ratio=pos)

    def set_playback_state(self, payload: dict):
        pos = float(payload.get('position', 0))
        dur = float(payload.get('duration', 0))
        self.time_label.setText('%s / %s' % (_fmt_time(pos), _fmt_time(dur)))
        if dur > 0:
            self.progress.blockSignals(True)
            self.progress.setValue(int(min(1.0, pos / dur) * 1000))
            self.progress.blockSignals(False)
        playing = bool(payload.get('playing'))
        paused = bool(payload.get('paused'))
        self.btn_play.setText('▶ 播放' if paused or not playing else '⏸ 暂停')

    def set_current_line(self, text: str):
        if text:
            self.lyric_main.setText(text)

    def set_lyric_tick(self, payload: dict):
        text = (payload or {}).get('text', '')
        index = int((payload or {}).get('index', -1))
        if text:
            self.lyric_main.setText(text)
        if index < 0 or not self._lyric_lines:
            return
        self.lyric_prev.setText(self._lyric_lines[index - 1] if index > 0 else '')
        self.lyric_next.setText(self._lyric_lines[index + 1] if index + 1 < len(self._lyric_lines) else '')
        self.lyrics_list.blockSignals(True)
        self.lyrics_list.setCurrentRow(index)
        self.lyrics_list.blockSignals(False)
        item = self.lyrics_list.item(index)
        if item:
            self.lyrics_list.scrollToItem(item)

    def set_lyrics_lines(self, lines: list):
        self._lyric_lines = list(lines or [])
        self.lyrics_list.clear()
        for i, line in enumerate(self._lyric_lines, 1):
            self.lyrics_list.addItem('%02d %s' % (i, line))
        if self._lyric_lines:
            self.lyric_main.setText(self._lyric_lines[0])
            self.lyric_prev.setText('')
            self.lyric_next.setText(self._lyric_lines[1] if len(self._lyric_lines) > 1 else '')
        else:
            self.lyric_main.setText('—')
            self.lyric_prev.setText('')
            self.lyric_next.setText('')

    def set_mode(self, mode: str, active: bool = False):
        self._mode = mode
        self.btn_ai_sing.setChecked(mode == 'ai_sing' and active)
        self.btn_ai_follow.setEnabled(mode != 'ai_sing' or not active)

    def selected_song(self):
        return self._selected
