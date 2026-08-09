"""播放 Tab：歌库 + 歌词显示 + AI 唱歌控制。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.ai_follow_mix_panel import AiFollowMixPanel
from app.ui.waveform_widget import WaveformWidget


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
        self.lyric_main = QLabel('暂无歌词')
        self.lyric_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_main.setWordWrap(True)
        self.lyric_main.setTextFormat(Qt.TextFormat.RichText)
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
        self.waveform = WaveformWidget()
        self.waveform.seek_requested.connect(self._on_wave_seek)
        center_layout.addWidget(self.waveform)
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
        self.btn_play = QPushButton('▶')
        self.btn_play.setCheckable(True)
        self.btn_play.setFixedWidth(52)
        self.btn_play.setToolTip('播放 / 暂停')
        self.btn_play.clicked.connect(self._on_transport)
        ctrl.addWidget(self.btn_play)
        self.btn_ai_follow = QPushButton('AI 跟唱')
        self.btn_ai_follow.setCheckable(True)
        self.btn_ai_follow.setToolTip('AI 跟唱：伴奏按时间轴播放；麦克风有声音时门控输出 AI 人声（不识别音准）')
        self.btn_ai_follow.clicked.connect(self._on_ai_follow)
        ctrl.addWidget(self.btn_ai_follow)
        self.btn_ai_sing = QPushButton('AI 唱歌')
        self.btn_ai_sing.setCheckable(True)
        self.btn_ai_sing.setToolTip('播放离线生成的 AI 成品（cover.wav）')
        self.btn_ai_sing.clicked.connect(self._on_ai_sing)
        ctrl.addWidget(self.btn_ai_sing)
        self.btn_reverb_talk = QPushButton('混响说话')
        self.btn_reverb_talk.setCheckable(True)
        self.btn_reverb_talk.setToolTip('麦克风直通并叠加房间混响（不经 RVC）；播放中可听到伴奏')
        self.btn_reverb_talk.clicked.connect(self._on_reverb_talk)
        ctrl.addWidget(self.btn_reverb_talk)
        self.btn_normal_talk = QPushButton('普通说话')
        self.btn_normal_talk.setCheckable(True)
        self.btn_normal_talk.setToolTip('麦克风干声直通+伴奏（路由同混响说话，无混响）')
        self.btn_normal_talk.clicked.connect(self._on_normal_talk)
        ctrl.addWidget(self.btn_normal_talk)
        self._play_mode = 'sequential'
        self.btn_play_mode = QToolButton()
        self.btn_play_mode.setText('🔁')
        self.btn_play_mode.setToolTip('顺序播放（点击切换：单曲循环 / 随机播放）')
        self.btn_play_mode.setStyleSheet(
            'QToolButton{padding:8px 10px;border-radius:6px;border:1px solid #cbd5e1;background:#fff;font-size:16px;}'
            'QToolButton:hover{background:#f8fafc;}'
        )
        self.btn_play_mode.clicked.connect(lambda: self.bridge.emit_action('playback_set_play_mode'))
        ctrl.addWidget(self.btn_play_mode)
        self.btn_mix = QToolButton()
        self.btn_mix.setText('🔊')
        self.btn_mix.setToolTip('AI 跟唱混音调节（伴奏/人声/原唱/阈值）')
        self.btn_mix.setStyleSheet(
            'QToolButton{padding:8px 10px;border-radius:6px;border:1px solid #cbd5e1;background:#fff;font-size:16px;}'
            'QToolButton:hover{background:#f8fafc;}'
        )
        self.btn_mix.clicked.connect(self._toggle_mix_panel)
        ctrl.addWidget(self.btn_mix)
        self._mix_panel = AiFollowMixPanel(self.bridge, self)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for btn in (self.btn_ai_follow, self.btn_ai_sing, self.btn_reverb_talk, self.btn_normal_talk):
            self._mode_group.addButton(btn)
        for btn in (self.btn_play, self.btn_ai_follow, self.btn_ai_sing, self.btn_reverb_talk, self.btn_normal_talk):
            btn.setStyleSheet(self.BTN_STYLE)
        self._mode = 'ai_sing'
        self.btn_ai_sing.setChecked(True)
        ctrl.addStretch()
        center_layout.addLayout(ctrl)
        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_head = QHBoxLayout()
        right_head.addWidget(QLabel('歌词进度'))
        self.btn_enhance_lrc = QPushButton('生成逐字')
        self.btn_enhance_lrc.setToolTip(
            '按 lyrics.align_engine 生成逐字并写入 LRC。'
            '进歌只会快速能量补齐或沿用文件缓存；Whisper 需点此按钮。'
            'energy=轻量 / whisper=更准更慢'
        )
        self.btn_enhance_lrc.clicked.connect(lambda: self.bridge.emit_action('lyrics_enhance'))
        right_head.addStretch()
        right_head.addWidget(self.btn_enhance_lrc)
        right_layout.addLayout(right_head)
        self.lyrics_list = QListWidget()
        self.lyrics_list.setStyleSheet('font-size:13px;color:#64748b;')
        self.lyrics_list.currentRowChanged.connect(self._on_lyric_row)
        right_layout.addWidget(self.lyrics_list)
        self.lyric_edit = QLineEdit()
        self.lyric_edit.setPlaceholderText('改词：选中一行后编辑')
        right_layout.addWidget(self.lyric_edit)
        self.btn_save_lyric = QPushButton('保存改词')
        self.btn_save_lyric.clicked.connect(self._on_save_rewrite)
        right_layout.addWidget(self.btn_save_lyric)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 760, 220])
        self._lyric_lines = []
        self._lyric_row = -1

    def apply_library(self, songs: list):
        keep = self._selected
        self._songs = list(songs or [])
        self._filter_songs(self.search_box.text(), auto_select=not keep)

    def _filter_songs(self, keyword: str, auto_select: bool = True):
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
        if auto_select and self.song_list.count() and self.song_list.currentRow() < 0:
            self.select_initial_song()

    def select_initial_song(self):
        if self.song_list.count() <= 0:
            return
        self.song_list.blockSignals(True)
        self.song_list.setCurrentRow(0)
        self.song_list.blockSignals(False)
        self._apply_row_song(0, resume_if_playing=False)

    def _on_row_changed(self, row: int):
        self._apply_row_song(row, resume_if_playing=True)

    def _apply_row_song(self, row: int, resume_if_playing: bool = True):
        if row < 0:
            self._selected = None
            return
        item = self.song_list.item(row)
        if not item:
            return
        song = item.data(Qt.ItemDataRole.UserRole) or {}
        self._selected = song
        self.title_label.setText(song.get('title', '未命名'))
        play_path = song.get('play_path') or song.get('cover_path') or song.get('vocal_path')
        self.waveform.load_file(play_path or '')
        self.waveform.set_position_ratio(0.0)
        self.bridge.emit_action('playback_select_song', song=song, resume_if_playing=resume_if_playing)

    def _on_wave_seek(self, ratio: float):
        self.bridge.emit_action('playback_seek', ratio=ratio)

    def _on_transport(self):
        self.bridge.emit_action('playback_transport')

    def _select_mode_ui(self, mode: str):
        if mode not in ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk'):
            return
        if mode in ('ai_sing', 'ai_follow') and not self._selected:
            peer = {'ai_sing': self.btn_ai_sing, 'ai_follow': self.btn_ai_follow}[mode]
            peer.blockSignals(True)
            peer.setChecked(False)
            peer.blockSignals(False)
            self.bridge.emit_action('playback_select_mode', mode=mode, log='请先在歌库中选择歌曲')
            return
        self._uncheck_mode_buttons(mode)
        peer = {
            'ai_sing': self.btn_ai_sing,
            'ai_follow': self.btn_ai_follow,
            'reverb_talk': self.btn_reverb_talk,
            'normal_talk': self.btn_normal_talk,
        }[mode]
        peer.blockSignals(True)
        peer.setChecked(True)
        peer.blockSignals(False)
        self._mode = mode
        payload = {'mode': mode}
        if self._selected:
            payload['song'] = self._selected
        self.bridge.emit_action('playback_select_mode', **payload)

    def _sync_transport(self, playing: bool, paused: bool = False):
        active = bool(playing) and not bool(paused)
        self.btn_play.blockSignals(True)
        self.btn_play.setChecked(active)
        self.btn_play.setText('⏸' if active else '▶')
        self.btn_play.blockSignals(False)

    def _uncheck_mode_buttons(self, except_name: str = ''):
        for name, btn in (
            ('ai_sing', self.btn_ai_sing),
            ('reverb_talk', self.btn_reverb_talk),
            ('ai_follow', self.btn_ai_follow),
            ('normal_talk', self.btn_normal_talk),
        ):
            if name == except_name:
                continue
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

    def _on_normal_talk(self):
        self._select_mode_ui('normal_talk')

    def _on_ai_follow(self):
        self._select_mode_ui('ai_follow')

    def _on_reverb_talk(self):
        self._select_mode_ui('reverb_talk')

    def _on_ai_sing(self):
        self._select_mode_ui('ai_sing')

    def _toggle_mix_panel(self):
        self._mix_panel._load_from_config()
        g = self.btn_mix.mapToGlobal(self.btn_mix.rect().topLeft())
        self._mix_panel.adjustSize()
        self._mix_panel.move(max(8, g.x() - self._mix_panel.width() + self.btn_mix.width()), g.y() - self._mix_panel.height() - 8)
        self._mix_panel.show()
        self._mix_panel.raise_()

    def _on_seek(self):
        pos = self.progress.value() / 1000.0
        self.bridge.emit_action('playback_seek', ratio=pos)

    def set_playback_state(self, payload: dict):
        pos = float(payload.get('position', 0))
        dur = float(payload.get('duration', 0))
        playing = bool(payload.get('playing'))
        paused = bool(payload.get('paused'))
        self.time_label.setText('%s / %s' % (_fmt_time(pos), _fmt_time(dur)))
        if dur > 0:
            self.progress.blockSignals(True)
            self.progress.setValue(int(min(1.0, pos / dur) * 1000))
            self.progress.blockSignals(False)
            self.waveform.set_playback(pos, dur, playing and not paused)
        if self._mode in ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk'):
            self._sync_transport(playing, paused)

    def set_current_line(self, text: str):
        if text:
            self.lyric_main.setText(text)

    def set_lyric_tick(self, payload: dict):
        text = (payload or {}).get('text', '')
        index = int((payload or {}).get('index', -1))
        html = (payload or {}).get('html_light') or ''
        if html and (payload or {}).get('has_words'):
            self.lyric_main.setText(html)
        elif text:
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

    def _on_lyric_row(self, row: int):
        self._lyric_row = row
        if 0 <= row < len(self._lyric_lines):
            self.lyric_edit.setText(self._lyric_lines[row])

    def _on_save_rewrite(self):
        if self._lyric_row < 0:
            return
        self.bridge.emit_action(
            'lyrics_rewrite',
            line_index=self._lyric_row,
            text=self.lyric_edit.text(),
        )

    def set_lyrics_lines(self, lines: list):
        self._lyric_lines = list(lines or [])
        self.lyrics_list.clear()
        for i, line in enumerate(self._lyric_lines, 1):
            self.lyrics_list.addItem('%02d %s' % (i, line))
        self._lyric_row = 0 if self._lyric_lines else -1
        if self._lyric_lines:
            self.lyric_main.setText(self._lyric_lines[0])
            self.lyric_prev.setText('')
            self.lyric_next.setText(self._lyric_lines[1] if len(self._lyric_lines) > 1 else '')
            self.lyric_edit.setText(self._lyric_lines[0])
            self.lyrics_list.setCurrentRow(0)
        else:
            self.lyric_main.setText('暂无歌词')
            self.lyric_prev.setText('')
            self.lyric_next.setText('')
            self.lyric_edit.clear()

    def set_ai_follow_busy(self, busy: bool):
        self.btn_ai_follow.setEnabled(not busy)
        self.btn_ai_follow.setText('加载中…' if busy else 'AI 跟唱')
        if busy:
            self.btn_ai_follow.setChecked(True)
            self._sync_transport(False)

    def set_selected_mode(self, mode: str):
        if mode not in ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk'):
            return
        self._mode = mode
        self._uncheck_mode_buttons(mode)
        peer = {
            'ai_sing': self.btn_ai_sing,
            'ai_follow': self.btn_ai_follow,
            'reverb_talk': self.btn_reverb_talk,
            'normal_talk': self.btn_normal_talk,
        }.get(mode)
        if peer:
            peer.blockSignals(True)
            peer.setChecked(True)
            peer.blockSignals(False)

    def set_playback_stopped(self):
        self._sync_transport(False)

    def set_mode(self, mode: str, active: bool = False):
        if mode == 'idle':
            self.set_playback_stopped()
            return
        if mode == 'realtime':
            self._mode = 'realtime'
            self.btn_ai_follow.blockSignals(True)
            self.btn_ai_follow.setChecked(True)
            self.btn_ai_follow.blockSignals(False)
            for peer in (self.btn_ai_sing, self.btn_normal_talk, self.btn_reverb_talk):
                peer.setEnabled(False)
            return
        if active:
            self.set_selected_mode(mode)
        realtime = self._mode == 'realtime'
        self.btn_ai_sing.setEnabled(not realtime)
        self.btn_normal_talk.setEnabled(not realtime)
        self.btn_reverb_talk.setEnabled(not realtime)
        self.btn_ai_follow.setEnabled(not realtime)

    def selected_song(self):
        return self._selected

    def select_song_by_title(self, title: str):
        title = (title or '').strip()
        if not title:
            return
        for i in range(self.song_list.count()):
            item = self.song_list.item(i)
            if not item:
                continue
            song = item.data(Qt.ItemDataRole.UserRole) or {}
            if song.get('title') == title or item.text() == title:
                self.song_list.setCurrentRow(i)
                return

    def set_play_mode(self, mode: str):
        icons = {'sequential': '🔁', 'repeat_one': '🔂', 'shuffle': '🔀'}
        tips = {'sequential': '顺序播放', 'repeat_one': '单曲循环', 'shuffle': '随机播放'}
        mode = mode if mode in icons else 'sequential'
        self._play_mode = mode
        self.btn_play_mode.setText(icons[mode])
        self.btn_play_mode.setToolTip('%s（点击切换）' % tips[mode])

    def _toggle_mode_button(self, name: str, btn):
        btn.blockSignals(True)
        btn.setChecked(self._mode != name)
        btn.blockSignals(False)
        if name == 'ai_follow':
            self._on_ai_follow()
        elif name == 'ai_sing':
            self._on_ai_sing()
        elif name == 'reverb_talk':
            self._on_reverb_talk()
        elif name == 'normal_talk':
            self._on_normal_talk()

    def trigger_transport(self):
        self._on_transport()

    def trigger_ai_follow(self):
        self._on_ai_follow()

    def trigger_ai_sing(self):
        self._on_ai_sing()

    def trigger_reverb_talk(self):
        self._on_reverb_talk()

    def trigger_normal_talk(self):
        self._on_normal_talk()
