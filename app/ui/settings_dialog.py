"""系统设置：侧栏 Tab + 音频/播放/歌词/常规/快捷键。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.audio.devices import (
    device_ref_for_config,
    is_auto_device,
    list_devices,
    list_hostapis,
    pick_monitor_default,
    pick_voicemeeter_defaults,
    resolve_device_index,
    vm_default_echo_risk,
    refresh_portaudio,
)
from app.config_store import ConfigStore
from app.integration.controller import PLAY_MODE_LABELS, PLAY_MODES
from app.ui.ai_follow_mix_panel import _DEFAULTS as PF_DEFAULTS
from app.ui.ai_follow_mix_panel import _att_from_slider, _slider_from_att
from app.ui.layout_store import load_ui_layout
from app.ui.playback_shortcuts import DEFAULT_SHORTCUTS, SHORTCUT_KEYS, SHORTCUT_LABELS
from app.ui.qt_util import clicked
from app.ui.rvc_advanced_dialog import RvcAdvancedDialog

_NAV_STYLE = (
    'QListWidget{background:#f8fafc;border:none;outline:0;padding:8px 6px;}'
    'QListWidget::item{padding:10px 12px;border-radius:6px;color:#334155;}'
    'QListWidget::item:selected{background:#2563eb;color:#fff;}'
)


class SettingsDialog(QDialog):
    """系统设置弹窗：写入 config/client.json，无需手改 JSON。"""

    _TABS = (
        ('audio', '音频与路由'),
        ('playback', '播放设置'),
        ('lyrics', '歌词'),
        ('general', '常规'),
        ('shortcuts', '快捷键'),
    )

    def __init__(self, bridge, config: ConfigStore, project_root=None, song_make_page=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.config = config
        self.project_root = project_root
        self.song_make_page = song_make_page
        self._mic_testing = False
        self._lyric_style_preview = False
        self._realtime_payload = None
        self._pf_sliders = {}
        self.setWindowTitle('系统设置')
        self.setMinimumSize(860, 620)
        self.resize(920, 680)
        self._build_ui()
        self._load_values()
        self._reload_devices()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if hasattr(self, 'lbl_vm_default_warn'):
            self.lbl_vm_default_warn.setText(vm_default_echo_risk(self._hostapi_filter()) or '')

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._nav = QListWidget()
        self._nav.setFixedWidth(156)
        self._nav.setStyleSheet(_NAV_STYLE)
        for _, label in self._TABS:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            self._nav.addItem(item)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        outer.addWidget(self._nav)

        right = QVBoxLayout()
        right.setContentsMargins(20, 16, 20, 12)
        self._page_title = QLabel('')
        self._page_title.setStyleSheet('font-size:18px;font-weight:700;color:#0f172a;')
        self._page_sub = QLabel('')
        self._page_sub.setWordWrap(True)
        self._page_sub.setStyleSheet('color:#64748b;font-size:12px;margin-bottom:4px;')
        right.addWidget(self._page_title)
        right.addWidget(self._page_sub)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_audio())
        self._stack.addWidget(self._page_playback())
        self._stack.addWidget(self._page_lyrics())
        self._stack.addWidget(self._page_general())
        self._stack.addWidget(self._page_shortcuts())
        right.addWidget(self._stack, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(clicked(self.reject))
        btn_save = QPushButton('保存设置')
        btn_save.clicked.connect(clicked(self.accept))
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        right.addLayout(btn_row)
        outer.addLayout(right, stretch=1)
        self._nav.setCurrentRow(0)

    def _on_nav_changed(self, row: int):
        if row < 0:
            return
        self._stack.setCurrentIndex(row)
        key, label = self._TABS[row]
        self._page_title.setText(label)
        subs = {
            'audio': '选择输入/输出设备、采样率与试麦（本机通道输出）。',
            'playback': '歌库播放模式、说话/混响、AI 跟唱默认混音；智能切依据 converted_vocal 能量（无需歌词）。',
            'lyrics': '逐字歌词生成、高亮同步；桌面歌词窗可供直播伴侣窗口采集。',
            'general': '更新检查、日志目录等全局项。',
            'shortcuts': '仅在「播放」Tab 生效的快捷键。',
        }
        self._page_sub.setText(subs.get(key, ''))

    def _scroll_page(self, builder):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        builder(root)
        root.addStretch()
        scroll.setWidget(body)
        return scroll

    def _page_audio(self):
        def build(root):
            box = QGroupBox('本机音频设备')
            layout = QVBoxLayout(box)
            host_row = QHBoxLayout()
            host_row.addWidget(QLabel('设备类型'))
            self.cmb_hostapi = QComboBox()
            self.cmb_hostapi.setMinimumWidth(220)
            self.cmb_hostapi.currentIndexChanged.connect(self._reload_devices)
            self.chk_wasapi = QCheckBox('独占 WASAPI 设备')
            host_row.addWidget(self.cmb_hostapi, stretch=1)
            host_row.addWidget(self.chk_wasapi)
            layout.addLayout(host_row)
            form = QFormLayout()
            self.cmb_input = QComboBox()
            self.cmb_input.setMinimumWidth(420)
            self.cmb_output = QComboBox()
            self.cmb_output.setMinimumWidth(420)
            form.addRow('输入设备', self.cmb_input)
            form.addRow('输出设备（直播）', self.cmb_output)
            self.cmb_monitor = QComboBox()
            self.cmb_monitor.setMinimumWidth(420)
            self.cmb_monitor.setToolTip(
                '双路输出：直播走「输出设备 Aux→B1」，耳机走「监听设备 VAIO→A1」。\n'
                '普通/混响：耳机仅伴奏；AI 唱歌/跟唱：耳机为完整混音（>100% 时耳机音量封顶 100%）。\n'
                'AUX 只勾 B1、VAIO 只勾 A1，AUX 勿勾 A1。\n'
                'Windows 系统默认播放请设 Realtek 等物理声卡，勿设 VoiceMeeter Input。'
            )
            form.addRow('监听设备（耳机）', self.cmb_monitor)
            self.chk_dual_monitor = QCheckBox('双路监听（普通/混响说话时耳机不含干声）')
            self.chk_dual_monitor.setToolTip(
                '普通/混响：直播 Aux→B1（含人声），监听 VAIO→A1（仅伴奏）。\n'
                'AI 唱歌/跟唱：直播 Aux→B1，监听 VAIO→A1（完整混音）；AUX 勿勾 A1。'
            )
            form.addRow('', self.chk_dual_monitor)
            self.chk_dual_monitor.toggled.connect(lambda on: self.cmb_monitor.setEnabled(on))
            self.lbl_vm_default_warn = QLabel('')
            self.lbl_vm_default_warn.setWordWrap(True)
            self.lbl_vm_default_warn.setStyleSheet('color:#E65100;font-size:12px;')
            form.addRow('', self.lbl_vm_default_warn)
            layout.addLayout(form)
            sr_row = QHBoxLayout()
            self.btn_reload = QPushButton('重载设备列表')
            self.btn_reload.clicked.connect(clicked(self._reload_devices))
            self.radio_sr_model = QRadioButton('使用模型采样率')
            self.radio_sr_device = QRadioButton('使用设备采样率')
            self.sr_group = QButtonGroup(self)
            self.sr_group.addButton(self.radio_sr_model)
            self.sr_group.addButton(self.radio_sr_device)
            self.lbl_sample_rate = QLabel('采样率：48000')
            sr_row.addWidget(self.btn_reload)
            sr_row.addWidget(self.radio_sr_model)
            sr_row.addWidget(self.radio_sr_device)
            sr_row.addStretch()
            sr_row.addWidget(self.lbl_sample_rate)
            layout.addLayout(sr_row)
            self.spin_sample_rate = QSpinBox()
            self.spin_sample_rate.setRange(8000, 192000)
            self.spin_sample_rate.setSingleStep(1000)
            self.spin_sample_rate.setValue(48000)
            self.spin_sample_rate.valueChanged.connect(lambda v: self.lbl_sample_rate.setText('采样率：%s' % v))
            self.radio_sr_device.toggled.connect(self._sync_sr_controls)
            self.radio_sr_model.toggled.connect(self._sync_sr_controls)
            self.cmb_input.currentIndexChanged.connect(self._sync_device_sample_rate_hint)
            self.cmb_output.currentIndexChanged.connect(self._sync_device_sample_rate_hint)
            mic_row = QHBoxLayout()
            self.btn_test_mic = QPushButton('试麦')
            self.btn_test_mic.setToolTip('启动干声直通测试，对着麦克风说话；再次点击停止')
            self.btn_test_mic.clicked.connect(clicked(self._toggle_test_mic))
            self.lbl_mic_hint = QLabel('试麦：直通输入→输出，不经 RVC')
            self.lbl_mic_hint.setStyleSheet('color:#64748b;font-size:12px;')
            mic_row.addWidget(self.btn_test_mic)
            mic_row.addWidget(self.lbl_mic_hint, stretch=1)
            layout.addLayout(mic_row)
            root.addWidget(box)
        return self._scroll_page(build)

    def _page_playback(self):
        def build(root):
            lib = QGroupBox('歌库播放')
            lib_form = QFormLayout(lib)
            self.cmb_play_mode = QComboBox()
            for mode in PLAY_MODES:
                self.cmb_play_mode.addItem(PLAY_MODE_LABELS[mode], mode)
            lib_form.addRow('播放模式', self.cmb_play_mode)
            root.addWidget(lib)

            smart = QGroupBox('智能切模式')
            smart_form = QFormLayout(smart)
            self.chk_smart_switch = QCheckBox('前奏 / 间奏 / 尾奏自动切「混响说话」')
            self.chk_smart_switch.setToolTip(
                '分析 converted_vocal 人声音轨能量（与波形虚线同源），无需 LRC。\n'
                '唱段自动回到所选 AI 唱歌/跟唱。手动点「混响说话/普通说话」后本首不再自动切换。'
            )
            self.spin_smart_gap = QSpinBox()
            self.spin_smart_gap.setRange(1, 10)
            self.spin_smart_gap.setSuffix(' 秒')
            self.spin_smart_gap.setToolTip('连续检测无人声达到此秒数后才切混响（防抖，避免句尾误触）')
            smart_form.addRow(self.chk_smart_switch)
            smart_form.addRow('静音保持', self.spin_smart_gap)
            root.addWidget(smart)

            talk = QGroupBox('说话 / 混响')
            talk_layout = QVBoxLayout(talk)
            pt_row = QHBoxLayout()
            pt_row.addWidget(QLabel('普通说话音量'))
            self.slider_passthrough = QSlider(Qt.Orientation.Horizontal)
            self.slider_passthrough.setRange(0, 400)
            self.slider_passthrough.setToolTip(
                '0%～400%，默认 100%=2 倍增益；控制直播输出中的人声大小。\n'
                '检测到人声时会自动补增益到合适电平。\n'
                'VM：H1 只 B2；AUX 只 B1（勿勾 B2/A1，否则约 2 秒后出现延迟人声回音）。'
            )
            self.lbl_passthrough = QLabel('')
            self.lbl_passthrough.setMinimumWidth(44)
            self.lbl_passthrough.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.slider_passthrough.valueChanged.connect(lambda v: self.lbl_passthrough.setText('%s%%' % v))
            pt_row.addWidget(self.slider_passthrough, stretch=1)
            pt_row.addWidget(self.lbl_passthrough)
            talk_layout.addLayout(pt_row)
            ai_row = QHBoxLayout()
            ai_row.addWidget(QLabel('AI 直播人声'))
            self.slider_ai_vocal = QSlider(Qt.Orientation.Horizontal)
            self.slider_ai_vocal.setRange(0, 400)
            self.slider_ai_vocal.setToolTip(
                '0%～400%，与普通说话同一刻度：400% 时直播人声目标电平一致。\n'
                '超过 100% 时直播更响，耳机监听封顶 100%。AUX 只 B1、VAIO 只 A1。'
            )
            self.lbl_ai_vocal = QLabel('')
            self.lbl_ai_vocal.setMinimumWidth(44)
            self.lbl_ai_vocal.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.slider_ai_vocal.valueChanged.connect(lambda v: self.lbl_ai_vocal.setText('%s%%' % v))
            ai_row.addWidget(self.slider_ai_vocal, stretch=1)
            ai_row.addWidget(self.lbl_ai_vocal)
            talk_layout.addLayout(ai_row)
            for key, label, lo, hi, tip, scale in (
                ('reverb_mix', '混响湿度', 0, 100, '混响说话模式下湿声比例', 100.0),
                ('reverb_decay', '混响衰减', 50, 95, '越大混响尾音越长', 100.0),
            ):
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(lo, hi)
                if tip:
                    slider.setToolTip(tip)
                val_lbl = QLabel('')
                val_lbl.setMinimumWidth(44)
                val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                slider.valueChanged.connect(lambda v, lbl=val_lbl, s=scale: lbl.setText('%.0f%%' % (v / s * 100) if s == 100 else '%.2f' % (v / s)))
                row.addWidget(slider, stretch=1)
                row.addWidget(val_lbl)
                talk_layout.addLayout(row)
                setattr(self, 'slider_%s' % key, slider)
                setattr(self, 'lbl_%s' % key, val_lbl)
            root.addWidget(talk)

            follow = QGroupBox('AI 跟唱默认混音（🔊 面板初始值）')
            follow_layout = QVBoxLayout(follow)
            for key, label, lo, hi, tip in (
                ('inst_ui', '伴奏音量', 0, 100, ''),
                ('mic_ui', 'AI 人声音量', 0, 150, 'VAD 门控打开时 converted_vocal 音量'),
                ('orig_ui', '原唱监听', 0, 100, '不参与 VAD，始终叠加 converted_vocal'),
                ('threshold', '跟唱阈值', 0, 100, '越高越不易误触；越低越容易跟唱'),
                ('attenuation_ui', '跟唱衰减', 1, 11, '停麦后 AI 人声保持时长'),
            ):
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(lo, hi)
                if tip:
                    slider.setToolTip(tip)
                val_lbl = QLabel('')
                val_lbl.setMinimumWidth(44)
                val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                def _sync(v, k=key, lbl=val_lbl):
                    lbl.setText('%.2f' % _att_from_slider(v) if k == 'attenuation_ui' else str(v))

                slider.valueChanged.connect(_sync)
                row.addWidget(slider, stretch=1)
                row.addWidget(val_lbl)
                follow_layout.addLayout(row)
                self._pf_sliders[key] = (slider, val_lbl)
            root.addWidget(follow)

            rvc_row = QHBoxLayout()
            self.lbl_model = QLabel('')
            self.lbl_model.setStyleSheet('color:#334155;font-size:13px;')
            self.btn_advanced = QPushButton('RVC 高级设置…')
            self.btn_advanced.setToolTip('模型选择、音调/Index/性能参数（对标 realtime_gui）')
            self.btn_advanced.clicked.connect(clicked(self._open_advanced))
            rvc_row.addWidget(self.lbl_model, stretch=1)
            rvc_row.addWidget(self.btn_advanced)
            root.addLayout(rvc_row)
        return self._scroll_page(build)

    def _page_lyrics(self):
        def build(root):
            box = QGroupBox('逐字歌词（「生成逐字」时生效）')
            form = QFormLayout(box)
            self.cmb_align_engine = QComboBox()
            self.cmb_align_engine.addItem('人声能量（推荐日常）', 'energy')
            self.cmb_align_engine.addItem('Whisper 识别（更准、更慢）', 'whisper')
            self.cmb_align_engine.setToolTip(
                '决定点「生成逐字」时用哪种算法写进 LRC。\n'
                '· 人声能量：轻量，几乎不占显存，速度快\n'
                '· Whisper：整曲语音识别对齐，更贴人声，耗 CPU/可选 GPU\n'
                '注意：只改这里不会自动重算；已有逐字的歌需再点一次「生成逐字」。'
            )
            self.cmb_align_engine.currentIndexChanged.connect(self._sync_lyrics_controls)
            self.cmb_whisper_model = QComboBox()
            for size, tip in (
                ('tiny', '最快最粗'),
                ('base', '较快'),
                ('small', '平衡，推荐'),
                ('medium', '更准更慢，更吃资源'),
                ('large-v3', '最准最慢，很吃资源'),
            ):
                self.cmb_whisper_model.addItem('%s（%s）' % (size, tip), size)
            self.cmb_whisper_device = QComboBox()
            self.cmb_whisper_device.addItem('CPU（稳定，不占显存，推荐）', 'cpu')
            self.cmb_whisper_device.addItem('CUDA 显卡（更快，吃显存）', 'cuda')
            self.cmb_whisper_device.addItem('自动（优先 CUDA，失败再 CPU）', 'auto')
            self.spin_lead_ms = QSpinBox()
            self.spin_lead_ms.setRange(-2000, 2000)
            self.spin_lead_ms.setSingleStep(20)
            self.spin_lead_ms.setSuffix(' ms')
            self.spin_offset_ms = QSpinBox()
            self.spin_offset_ms.setRange(-10000, 10000)
            self.spin_offset_ms.setSingleStep(50)
            self.spin_offset_ms.setSuffix(' ms')
            form.addRow('对齐引擎', self.cmb_align_engine)
            form.addRow('Whisper 模型', self.cmb_whisper_model)
            form.addRow('Whisper 设备', self.cmb_whisper_device)
            form.addRow('高亮提前', self.spin_lead_ms)
            form.addRow('整体偏移', self.spin_offset_ms)
            self.lbl_lyrics_hint = QLabel('改引擎后请对当前歌曲再点「生成逐字」才会重写 LRC。')
            self.lbl_lyrics_hint.setWordWrap(True)
            self.lbl_lyrics_hint.setStyleSheet('color:#64748b;font-size:12px;')
            form.addRow(self.lbl_lyrics_hint)
            root.addWidget(box)
            desk = QGroupBox('桌面歌词（直播采集）')
            desk_form = QFormLayout(desk)
            self.chk_lyric_chroma = QCheckBox('直播抠像（绿幕，推荐）')
            self.chk_lyric_chroma.setToolTip(
                '抖音窗口采集吃不掉透明通道，会变成黑底。开启后歌词窗用纯绿不透明底，伴侣里对「桌面歌词」开绿幕抠掉即可。'
            )
            self.cmb_lyric_chroma = QComboBox()
            self.cmb_lyric_chroma.addItem('纯绿 #00FF00（直播推荐）', '#00FF00')
            self.cmb_lyric_chroma.addItem('纯品红 #FF00FF', '#FF00FF')
            self.cmb_lyric_chroma.addItem('直播绿 #00B140（易糊字）', '#00B140')
            self.cmb_lyric_text_color = QComboBox()
            self.cmb_lyric_text_color.addItem('纯白 #FFFFFF（直播常用）', '#FFFFFF')
            self.cmb_lyric_text_color.addItem('蓝色 #2563EB', '#2563EB')
            self.cmb_lyric_text_color.addItem('橙黄 #FB923C', '#FB923C')
            self.cmb_lyric_text_color.addItem('纯红 #FF0000（抠绿稳）', '#FF0000')
            self.cmb_lyric_text_color.addItem('纯黄 #FFFF00', '#FFFF00')
            self.cmb_lyric_highlight_color = QComboBox()
            self.cmb_lyric_highlight_color.addItem('橙黄 #FB923C（当前字）', '#FB923C')
            self.cmb_lyric_highlight_color.addItem('同歌词色（仅加粗）', 'same')
            self.cmb_lyric_highlight_color.addItem('纯白 #FFFFFF', '#FFFFFF')
            self.cmb_lyric_highlight_color.addItem('纯红 #FF0000', '#FF0000')
            self.chk_lyric_click_through = QCheckBox('鼠标穿透（不挡后面点击，直播推荐）')
            self.chk_lyric_click_through.setToolTip('绿幕模式下歌词窗仍可被伴侣窗口采集，但鼠标会穿透到后面的主程序/伴侣界面。')
            self.chk_lyric_stay_on_top = QCheckBox('窗口置顶')
            self.chk_lyric_stay_on_top.setToolTip('关闭后置顶时，歌词窗不会一直盖住主程序；伴侣仍可按窗口名采集「桌面歌词」。')
            self.slider_lyric_bg = QSlider(Qt.Orientation.Horizontal)
            self.slider_lyric_bg.setRange(0, 100)
            self.slider_lyric_bg.setToolTip('仅普通模式：歌词背后黑底实度。直播请用上方「直播抠像」。')
            self.lbl_lyric_bg = QLabel('')
            self.lbl_lyric_bg.setMinimumWidth(44)
            self.lbl_lyric_bg.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bg_row = QHBoxLayout()
            bg_row.addWidget(self.slider_lyric_bg, stretch=1)
            bg_row.addWidget(self.lbl_lyric_bg)
            self.slider_lyric_opacity = QSlider(Qt.Orientation.Horizontal)
            self.slider_lyric_opacity.setRange(20, 100)
            self.slider_lyric_opacity.setToolTip('仅普通模式：整窗变淡。抠像模式下固定不透明。')
            self.lbl_lyric_opacity = QLabel('')
            self.lbl_lyric_opacity.setMinimumWidth(44)
            self.lbl_lyric_opacity.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            op_row = QHBoxLayout()
            op_row.addWidget(self.slider_lyric_opacity, stretch=1)
            op_row.addWidget(self.lbl_lyric_opacity)
            desk_form.addRow(self.chk_lyric_chroma)
            desk_form.addRow('抠像底色', self.cmb_lyric_chroma)
            desk_form.addRow('歌词颜色', self.cmb_lyric_text_color)
            desk_form.addRow('当前字颜色', self.cmb_lyric_highlight_color)
            desk_form.addRow(self.chk_lyric_click_through)
            desk_form.addRow(self.chk_lyric_stay_on_top)
            desk_form.addRow('背景不透明度', bg_row)
            desk_form.addRow('窗口不透明度', op_row)
            self.btn_lyric_reposition = QPushButton('歌词窗移到主窗旁')
            self.btn_lyric_reposition.setToolTip('绿条叠在主程序上时点一下，自动挪到主窗右侧并置底')
            self.btn_lyric_reposition.clicked.connect(clicked(self._move_lyrics_beside_main))
            desk_form.addRow(self.btn_lyric_reposition)
            hint = QLabel(
                '绿幕模式：窗口大小请自行拖拽。「歌词颜色」建议直播用纯白；「当前字」可设橙黄高亮。'
                '伴侣键色与抠像底色一致，相似度 280~380。'
                '直播伴侣采集请选「【直播歌词】桌面歌词」；若与主程序同为 python.exe 易绑错，'
                '可将 python 复制为项目根目录「桌面歌词.exe」后重启（歌词会独立进程启动）。'
            )
            hint.setWordWrap(True)
            hint.setStyleSheet('color:#64748b;font-size:12px;')
            desk_form.addRow(hint)
            self.chk_lyric_chroma.toggled.connect(self._on_desktop_lyric_style)
            self.cmb_lyric_chroma.currentIndexChanged.connect(self._on_desktop_lyric_style)
            self.cmb_lyric_text_color.currentIndexChanged.connect(self._on_desktop_lyric_style)
            self.cmb_lyric_highlight_color.currentIndexChanged.connect(self._on_desktop_lyric_style)
            self.chk_lyric_click_through.toggled.connect(self._on_desktop_lyric_style)
            self.chk_lyric_stay_on_top.toggled.connect(self._on_desktop_lyric_style)
            self.slider_lyric_bg.valueChanged.connect(self._on_desktop_lyric_style)
            self.slider_lyric_opacity.valueChanged.connect(self._on_desktop_lyric_style)
            root.addWidget(desk)
            osc_box = QGroupBox('OSC 歌词同步')
            osc_form = QFormLayout(osc_box)
            self.spin_osc = QSpinBox()
            self.spin_osc.setRange(1, 65535)
            osc_form.addRow('OSC 端口', self.spin_osc)
            root.addWidget(osc_box)
        return self._scroll_page(build)

    def _page_general(self):
        def build(root):
            box = QGroupBox('常规')
            form = QFormLayout(box)
            self.edit_server_base = QLineEdit()
            self.edit_server_base.setPlaceholderText('如 http://59.110.142.252')
            self.edit_nginx_prefix = QLineEdit()
            self.edit_nginx_prefix.setPlaceholderText('如 ai-sound，无前缀留空')
            self.edit_update_url = QLineEdit()
            self.edit_log_dir = QLineEdit()
            self.chk_auto_check = QCheckBox('启动时自动检查更新')
            self.chk_crash_upload = QCheckBox('崩溃时自动上报日志')
            self.edit_log_upload_url = QLineEdit()
            self.edit_log_upload_url.setPlaceholderText('留空则按服务器地址+前缀推导 /api/logs/upload')
            form.addRow('服务器地址', self.edit_server_base)
            form.addRow('Nginx 前缀', self.edit_nginx_prefix)
            form.addRow('更新地址', self.edit_update_url)
            form.addRow('', self.chk_auto_check)
            form.addRow('', self.chk_crash_upload)
            form.addRow('日志上报地址', self.edit_log_upload_url)
            form.addRow('日志目录', self.edit_log_dir)
            root.addWidget(box)
        return self._scroll_page(build)

    def _page_shortcuts(self):
        def build(root):
            box = QGroupBox('播放页快捷键')
            form = QFormLayout(box)
            self._key_edits = {}
            for key in SHORTCUT_KEYS:
                edit = QKeySequenceEdit()
                edit.setClearButtonEnabled(True)
                edit.setToolTip('点击后按下目标键；留空表示禁用')
                form.addRow(SHORTCUT_LABELS[key], edit)
                self._key_edits[key] = edit
            root.addWidget(box)
        return self._scroll_page(build)

    def _set_combo_data(self, combo: QComboBox, value, default=None):
        target = value if value is not None else default
        idx = combo.findData(target)
        if idx < 0 and default is not None:
            idx = combo.findData(default)
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)

    def _sync_lyrics_controls(self):
        use_whisper = str(self.cmb_align_engine.currentData() or '') == 'whisper'
        self.cmb_whisper_model.setEnabled(use_whisper)
        self.cmb_whisper_device.setEnabled(use_whisper)

    def _on_desktop_lyric_style(self, *_args):
        self._lyric_style_preview = True
        chroma = bool(self.chk_lyric_chroma.isChecked())
        self.cmb_lyric_chroma.setEnabled(chroma)
        self.cmb_lyric_text_color.setEnabled(chroma)
        self.cmb_lyric_highlight_color.setEnabled(chroma)
        self.slider_lyric_bg.setEnabled(not chroma)
        self.slider_lyric_opacity.setEnabled(not chroma)
        bg = int(self.slider_lyric_bg.value())
        op = int(self.slider_lyric_opacity.value())
        self.lbl_lyric_bg.setText('%s%%' % bg)
        self.lbl_lyric_opacity.setText('%s%%' % op)
        win = getattr(self.parent(), '_quit_lyrics', None)
        if win is not None:
            win.apply_desktop_style(
                bg_alpha=int(round(bg * 2.55)),
                opacity=op / 100.0,
                capture_mode='chroma' if chroma else 'normal',
                chroma_color=str(self.cmb_lyric_chroma.currentData() or '#00FF00'),
                click_through=self.chk_lyric_click_through.isChecked(),
                stay_on_top=self.chk_lyric_stay_on_top.isChecked(),
                text_color=str(self.cmb_lyric_text_color.currentData() or '#FFFFFF'),
                highlight_color=str(self.cmb_lyric_highlight_color.currentData() or '#FB923C'),
            )

    def _move_lyrics_beside_main(self):
        main = self.parent()
        win = getattr(main, '_quit_lyrics', None) if main is not None else None
        if win is None:
            return
        win.set_anchor_window(main)
        if not win.isVisible():
            win.show()
        if not win.move_beside_anchor():
            win.sync_desktop_stack()

    def _load_pitchfix_sliders(self):
        pf = self.config.get('pitchfix', {}) or {}
        values = dict(PF_DEFAULTS)
        if 'inst_ui' in pf:
            values['inst_ui'] = int(pf['inst_ui'])
        elif pf.get('inst_gain') is not None:
            values['inst_ui'] = int(round(float(pf['inst_gain']) * 100))
        if 'mic_ui' in pf:
            values['mic_ui'] = int(pf['mic_ui'])
        elif pf.get('mic_gain') is not None:
            values['mic_ui'] = int(round(float(pf['mic_gain']) * 100))
        for key in ('orig_ui', 'threshold', 'attenuation_ui'):
            if key in pf:
                values[key] = int(pf[key])
            elif key == 'orig_ui' and pf.get('ref_vocal_gain') is not None:
                values['orig_ui'] = int(round(float(pf['ref_vocal_gain']) * 100))
            elif key == 'threshold' and pf.get('follow_threshold') is not None:
                values['threshold'] = int(round(float(pf['follow_threshold'])))
            elif key == 'attenuation_ui' and pf.get('follow_attenuation') is not None:
                values['attenuation_ui'] = _slider_from_att(float(pf['follow_attenuation']))
        for key, (slider, val_lbl) in self._pf_sliders.items():
            slider.blockSignals(True)
            slider.setValue(values[key])
            slider.blockSignals(False)
            val_lbl.setText('%.2f' % _att_from_slider(values[key]) if key == 'attenuation_ui' else str(values[key]))

    def _load_values(self):
        layout = load_ui_layout().get('settings') or {}
        self.spin_osc.setValue(int(self.config.get('lyrics.osc_port', layout.get('osc_port', 9000))))
        self.edit_server_base.setText(str(self.config.get('server.base_url', '')))
        self.edit_nginx_prefix.setText(str(self.config.get('server.nginx_prefix', '')))
        self.edit_update_url.setText(str(self.config.get('update.check_url', layout.get('update_url', ''))))
        self.chk_auto_check.setChecked(bool(self.config.get('update.auto_check', True)))
        self.chk_crash_upload.setChecked(bool(self.config.get('logs.auto_upload_crash', True)))
        self.edit_log_upload_url.setText(str(self.config.get('logs.upload_url', '')))
        self.edit_log_dir.setText(str(self.config.get('paths.log_dir', layout.get('log_dir', 'logs/client'))))
        self.spin_sample_rate.setValue(int(self.config.get('audio.sample_rate', 48000)))
        self.chk_wasapi.setChecked(bool(self.config.get('audio.wasapi_exclusive', False)))
        self.chk_dual_monitor.setChecked(bool(self.config.get('audio.dual_monitor', True)))
        pt_ui = int(self.config.get('audio.passthrough_ui', 100))
        self.slider_passthrough.setValue(max(0, min(400, pt_ui)))
        self.lbl_passthrough.setText('%s%%' % self.slider_passthrough.value())
        av_ui = int(self.config.get('audio.ai_vocal_ui', 100))
        self.slider_ai_vocal.setValue(max(0, min(400, av_ui)))
        self.lbl_ai_vocal.setText('%s%%' % self.slider_ai_vocal.value())
        mix = float(self.config.get('audio.reverb_mix', 0.35) or 0.35)
        decay = float(self.config.get('audio.reverb_decay', 0.72) or 0.72)
        self.slider_reverb_mix.setValue(int(round(mix * 100)))
        self.lbl_reverb_mix.setText('%s%%' % int(round(mix * 100)))
        self.slider_reverb_decay.setValue(int(round(decay * 100)))
        self.lbl_reverb_decay.setText('%.0f%%' % (decay * 100))
        mode = str(self.config.get('playback.play_mode', 'sequential') or 'sequential')
        self._set_combo_data(self.cmb_play_mode, mode if mode in PLAY_MODES else 'sequential', 'sequential')
        self.chk_smart_switch.setChecked(bool(self.config.get('playback.smart_switch', False)))
        self.spin_smart_gap.setValue(int(round(float(self.config.get('playback.smart_switch_min_gap_sec', 3.0) or 3.0))))
        self._load_pitchfix_sliders()
        engine = str(self.config.get('lyrics.align_engine', 'energy') or 'energy').strip().lower()
        engine = 'whisper' if engine.startswith('whisper') or engine in ('faster-whisper', 'asr') else 'energy'
        self._set_combo_data(self.cmb_align_engine, engine, 'energy')
        self._set_combo_data(self.cmb_whisper_model, str(self.config.get('lyrics.whisper_model', 'small') or 'small'), 'small')
        device = str(self.config.get('lyrics.whisper_device', 'cpu') or 'cpu').strip().lower()
        if device not in ('cpu', 'cuda', 'auto'):
            device = 'cpu'
        self._set_combo_data(self.cmb_whisper_device, device, 'cpu')
        self.spin_lead_ms.setValue(int(self.config.get('lyrics.lead_ms', -80) or 0))
        self.spin_offset_ms.setValue(int(self.config.get('lyrics.offset_ms', 0) or 0))
        bg_alpha = max(0, min(255, int(self.config.get('lyrics.desktop_bg_alpha', 170) or 0)))
        op = max(0.2, min(1.0, float(self.config.get('lyrics.desktop_opacity', 0.9) or 0.9)))
        mode = str(self.config.get('lyrics.desktop_capture_mode', 'normal') or 'normal').strip().lower()
        chroma_on = mode in ('chroma', 'chroma_key', 'live', 'green')
        chroma_color = str(self.config.get('lyrics.desktop_chroma_color', '#00FF00') or '#00FF00').strip().upper()
        if not chroma_color.startswith('#'):
            chroma_color = '#' + chroma_color
        self._orig_lyric_bg = bg_alpha
        self._orig_lyric_opacity = op
        self._orig_lyric_capture_mode = 'chroma' if chroma_on else 'normal'
        self._orig_lyric_chroma_color = chroma_color
        text_color = str(self.config.get('lyrics.desktop_chroma_text_color', '#FFFFFF') or '#FFFFFF').strip().upper()
        if not text_color.startswith('#'):
            text_color = '#' + text_color
        highlight_color = str(self.config.get('lyrics.desktop_chroma_highlight_color', '#FB923C') or '#FB923C').strip()
        if highlight_color.lower() != 'same' and not highlight_color.startswith('#'):
            highlight_color = '#' + highlight_color
        self._orig_lyric_text_color = text_color
        self._orig_lyric_highlight_color = highlight_color
        click_through = bool(self.config.get('lyrics.desktop_click_through', chroma_on))
        stay_on_top = bool(self.config.get('lyrics.desktop_stay_on_top', not chroma_on))
        self._orig_lyric_click_through = click_through
        self._orig_lyric_stay_on_top = stay_on_top
        bg_pct = int(round(bg_alpha / 2.55))
        op_pct = int(round(op * 100))
        self.chk_lyric_chroma.blockSignals(True)
        self.cmb_lyric_chroma.blockSignals(True)
        self.cmb_lyric_text_color.blockSignals(True)
        self.cmb_lyric_highlight_color.blockSignals(True)
        self.chk_lyric_click_through.blockSignals(True)
        self.chk_lyric_stay_on_top.blockSignals(True)
        self.slider_lyric_bg.blockSignals(True)
        self.slider_lyric_opacity.blockSignals(True)
        self.chk_lyric_chroma.setChecked(chroma_on)
        self._set_combo_data(self.cmb_lyric_chroma, chroma_color, '#00FF00')
        self._set_combo_data(self.cmb_lyric_text_color, text_color, '#FFFFFF')
        self._set_combo_data(self.cmb_lyric_highlight_color, highlight_color, '#FB923C')
        self.chk_lyric_click_through.setChecked(click_through)
        self.chk_lyric_stay_on_top.setChecked(stay_on_top)
        self.slider_lyric_bg.setValue(bg_pct)
        self.slider_lyric_opacity.setValue(op_pct)
        self.chk_lyric_chroma.blockSignals(False)
        self.cmb_lyric_chroma.blockSignals(False)
        self.cmb_lyric_text_color.blockSignals(False)
        self.cmb_lyric_highlight_color.blockSignals(False)
        self.chk_lyric_click_through.blockSignals(False)
        self.chk_lyric_stay_on_top.blockSignals(False)
        self.slider_lyric_bg.blockSignals(False)
        self.slider_lyric_opacity.blockSignals(False)
        self.lbl_lyric_bg.setText('%s%%' % bg_pct)
        self.lbl_lyric_opacity.setText('%s%%' % op_pct)
        self.cmb_lyric_chroma.setEnabled(chroma_on)
        self.cmb_lyric_text_color.setEnabled(chroma_on)
        self.cmb_lyric_highlight_color.setEnabled(chroma_on)
        self.slider_lyric_bg.setEnabled(not chroma_on)
        self.slider_lyric_opacity.setEnabled(not chroma_on)
        self._sync_lyrics_controls()
        for key in SHORTCUT_KEYS:
            val = str((self.config.get('shortcuts', {}) or {}).get(key) or DEFAULT_SHORTCUTS.get(key) or '')
            self._key_edits[key].setKeySequence(val)
        sr_type = str(self.config.get('realtime.sr_type', 'sr_model'))
        self.radio_sr_device.setChecked(sr_type == 'sr_device')
        self.radio_sr_model.setChecked(sr_type != 'sr_device')
        self._sync_sr_controls()
        self.cmb_hostapi.blockSignals(True)
        self.cmb_hostapi.clear()
        self.cmb_hostapi.addItem('全部 HostAPI', None)
        saved_host = self.config.get('audio.hostapi')
        pick_idx = 0
        for i, name in enumerate(list_hostapis()):
            self.cmb_hostapi.addItem(name, name)
            if saved_host and name == saved_host:
                pick_idx = i + 1
        self.cmb_hostapi.setCurrentIndex(pick_idx)
        self.cmb_hostapi.blockSignals(False)
        self._refresh_model_label()

    def _refresh_model_label(self):
        sid = self.config.get('realtime.model_sid', '')
        self.lbl_model.setText('当前模型：%s' % (sid or '未选择'))

    def _open_advanced(self):
        dlg = RvcAdvancedDialog(
            self.config, project_root=self.project_root, song_make_page=self.song_make_page, parent=self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._realtime_payload = dlg.collect_realtime_payload()
        for key, val in self._realtime_payload.items():
            self.config.set('realtime.%s' % key, val)
        self._refresh_model_label()

    def _hostapi_filter(self):
        data = self.cmb_hostapi.currentData()
        return data if data else None

    def _reload_devices(self):
        refresh_portaudio()
        self.bridge.emit_action('audio_after_device_reload')
        hostapi = self._hostapi_filter()
        devices = list_devices(hostapi=hostapi)
        in_ref = self.config.get('audio.input_device')
        out_ref = self.config.get('audio.output_device')
        mon_ref = self.config.get('audio.monitor_output_device', 'auto')
        def_in, def_out = pick_voicemeeter_defaults(devices)

        def fill_combo(combo, items, selected_ref, default_idx, need_input=False, need_output=False):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('自动识别 Voicemeeter（优先 Aux）', 'auto')
            sel_row = 0 if is_auto_device(selected_ref) else -1
            selected_idx = None
            if not is_auto_device(selected_ref):
                selected_idx = resolve_device_index(
                    selected_ref, need_input=need_input, need_output=need_output, devices=items
                )
            for dev in items:
                combo.addItem('[%s] %s' % (dev.index, dev.name), dev.name)
                if sel_row >= 0:
                    continue
                if selected_idx is not None and dev.index == selected_idx:
                    sel_row = combo.count() - 1
                elif isinstance(selected_ref, str) and selected_ref.strip().lower() == dev.name.lower():
                    sel_row = combo.count() - 1
            if sel_row < 0 and default_idx is not None:
                for i in range(1, combo.count()):
                    name = combo.itemData(i)
                    if any(d.index == default_idx and d.name == name for d in items):
                        sel_row = i
                        break
            combo.setCurrentIndex(sel_row if sel_row >= 0 else 0)
            combo.blockSignals(False)

        inputs = [d for d in devices if d.max_input_channels > 0]
        outputs = [d for d in devices if d.max_output_channels > 0]
        fill_combo(self.cmb_input, inputs, in_ref, def_in, need_input=True)
        fill_combo(self.cmb_output, outputs, out_ref, def_out, need_output=True)
        out_idx = resolve_device_index(out_ref, need_output=True, devices=devices)
        if out_idx is None and is_auto_device(out_ref):
            out_idx = def_out
        self.cmb_monitor.blockSignals(True)
        self.cmb_monitor.clear()
        self.cmb_monitor.addItem('自动（配对 VAIO / Aux）', 'auto')
        self.cmb_monitor.addItem('关闭', 'off')
        sel_mon = 0 if is_auto_device(mon_ref) else 1 if str(mon_ref).lower() == 'off' else -1
        mon_idx = None
        if not is_auto_device(mon_ref) and str(mon_ref).lower() != 'off':
            mon_idx = resolve_device_index(mon_ref, need_output=True, devices=devices)
        for dev in outputs:
            self.cmb_monitor.addItem('[%s] %s' % (dev.index, dev.name), dev.name)
            if sel_mon >= 0:
                continue
            if mon_idx is not None and dev.index == mon_idx:
                sel_mon = self.cmb_monitor.count() - 1
            elif isinstance(mon_ref, str) and mon_ref.strip().lower() == dev.name.lower():
                sel_mon = self.cmb_monitor.count() - 1
        if sel_mon < 0:
            def_mon = pick_monitor_default(devices, out_idx)
            if def_mon is not None:
                for i in range(2, self.cmb_monitor.count()):
                    name = self.cmb_monitor.itemData(i)
                    if any(d.index == def_mon and d.name == name for d in outputs):
                        sel_mon = i
                        break
        self.cmb_monitor.setCurrentIndex(sel_mon if sel_mon >= 0 else 0)
        self.cmb_monitor.blockSignals(False)
        self.cmb_monitor.setEnabled(self.chk_dual_monitor.isChecked())
        risk = vm_default_echo_risk(hostapi)
        self.lbl_vm_default_warn.setText(risk or '')
        if risk:
            self.lbl_vm_default_warn.setToolTip('若刚修改 Windows 默认播放设备，点「重载设备列表」刷新；播放中会短暂重启音频流。')
        else:
            self.lbl_vm_default_warn.setToolTip('')
        self._sync_device_sample_rate_hint()

    def _sync_sr_controls(self):
        use_device = self.radio_sr_device.isChecked()
        self.spin_sample_rate.setEnabled(not use_device)
        self.lbl_sample_rate.setText(
            '采样率：设备默认' if use_device else '采样率：%s' % self.spin_sample_rate.value()
        )

    def _sync_device_sample_rate_hint(self):
        if not self.radio_sr_device.isChecked():
            return
        ref = self.cmb_input.currentData()
        hostapi = self._hostapi_filter()
        devices = list_devices(hostapi=hostapi)
        idx = resolve_device_index(ref, need_input=True, devices=devices)
        if idx is None and is_auto_device(ref):
            idx, _ = pick_voicemeeter_defaults(devices)
        if idx is None:
            return
        for d in devices:
            if d.index == idx and d.default_samplerate:
                self.lbl_sample_rate.setText('采样率：%s（输入设备）' % int(d.default_samplerate))
                break

    def _toggle_test_mic(self):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True, log='试麦已停止')
            self._mic_testing = False
            self.btn_test_mic.setText('试麦')
            return
        self.bridge.emit_action('audio_test_mic', start=True, log='试麦：请对着麦克风说话…')
        self._mic_testing = True
        self.btn_test_mic.setText('停止试麦')

    def _collect_pitchfix(self) -> dict:
        out = {}
        for key, (slider, _) in self._pf_sliders.items():
            out[key] = slider.value()
        out['inst_gain'] = out['inst_ui'] / 100.0
        out['mic_gain'] = out['mic_ui'] / 100.0
        out['ref_vocal_gain'] = out['orig_ui'] / 100.0
        out['follow_threshold'] = float(out['threshold'])
        out['follow_attenuation'] = _att_from_slider(out['attenuation_ui'])
        return out

    def closeEvent(self, event):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True)
            self._mic_testing = False
        super().closeEvent(event)

    def reject(self):
        if self._mic_testing:
            self.bridge.emit_action('audio_test_mic', stop=True)
            self._mic_testing = False
        win = getattr(self.parent(), '_quit_lyrics', None)
        if getattr(self, '_lyric_style_preview', False) and win is not None:
            win.apply_desktop_style(
                bg_alpha=getattr(self, '_orig_lyric_bg', 170),
                opacity=getattr(self, '_orig_lyric_opacity', 0.9),
                capture_mode=getattr(self, '_orig_lyric_capture_mode', 'normal'),
                chroma_color=getattr(self, '_orig_lyric_chroma_color', '#00FF00'),
                click_through=getattr(self, '_orig_lyric_click_through', True),
                stay_on_top=getattr(self, '_orig_lyric_stay_on_top', False),
                text_color=getattr(self, '_orig_lyric_text_color', '#FFFFFF'),
                highlight_color=getattr(self, '_orig_lyric_highlight_color', '#FB923C'),
            )
            if win.isVisible():
                win.show()
                win.sync_desktop_stack()
            ctrl = getattr(self.parent(), '_controller', None)
            if ctrl is not None and ctrl.state.loaded_lyrics:
                ctrl._reset_playback_lyrics(ctrl._current_song_position())
        self._lyric_style_preview = False
        super().reject()

    def collect_payload(self) -> dict:
        sr_type = 'sr_device' if self.radio_sr_device.isChecked() else 'sr_model'
        sample_rate = int(self.spin_sample_rate.value())
        hostapi = self._hostapi_filter()
        devices = list_devices(hostapi=hostapi)
        in_ref = device_ref_for_config(self.cmb_input.currentData(), devices)
        out_ref = device_ref_for_config(self.cmb_output.currentData(), devices)
        dual_mon = self.chk_dual_monitor.isChecked()
        mon_data = self.cmb_monitor.currentData()
        mon_ref = 'off' if not dual_mon else str(mon_data or 'auto')
        if dual_mon and mon_data not in ('auto', 'off'):
            mon_ref = device_ref_for_config(mon_data, devices)
        if sr_type == 'sr_device':
            idx = resolve_device_index(in_ref, need_input=True, devices=devices)
            if idx is None and is_auto_device(in_ref):
                idx, _ = pick_voicemeeter_defaults(devices)
            if idx is not None:
                for d in devices:
                    if d.index == idx and d.default_samplerate:
                        sample_rate = int(d.default_samplerate)
                        break
        payload = {
            'osc_port': self.spin_osc.value(),
            'server_base_url': self.edit_server_base.text().strip(),
            'server_nginx_prefix': self.edit_nginx_prefix.text().strip().strip('/'),
            'update_url': self.edit_update_url.text().strip(),
            'update_auto_check': self.chk_auto_check.isChecked(),
            'crash_auto_upload': self.chk_crash_upload.isChecked(),
            'log_upload_url': self.edit_log_upload_url.text().strip(),
            'log_dir': self.edit_log_dir.text().strip(),
            'sr_type': sr_type,
            'lyrics': {
                'align_engine': str(self.cmb_align_engine.currentData() or 'energy'),
                'whisper_model': str(self.cmb_whisper_model.currentData() or 'small'),
                'whisper_device': str(self.cmb_whisper_device.currentData() or 'cpu'),
                'lead_ms': int(self.spin_lead_ms.value()),
                'offset_ms': int(self.spin_offset_ms.value()),
                'desktop_bg_alpha': int(round(self.slider_lyric_bg.value() * 2.55)),
                'desktop_opacity': round(self.slider_lyric_opacity.value() / 100.0, 2),
                'desktop_capture_mode': 'chroma' if self.chk_lyric_chroma.isChecked() else 'normal',
                'desktop_chroma_color': str(self.cmb_lyric_chroma.currentData() or '#00FF00'),
                'desktop_click_through': self.chk_lyric_click_through.isChecked(),
                'desktop_stay_on_top': self.chk_lyric_stay_on_top.isChecked(),
                'desktop_chroma_text_color': str(self.cmb_lyric_text_color.currentData() or '#FFFFFF'),
                'desktop_chroma_highlight_color': str(self.cmb_lyric_highlight_color.currentData() or '#FB923C'),
            },
            'audio': {
                'hostapi': hostapi,
                'wasapi_exclusive': self.chk_wasapi.isChecked(),
                'input_device': in_ref,
                'output_device': out_ref,
                'dual_monitor': dual_mon,
                'monitor_output_device': mon_ref,
                'sample_rate': sample_rate,
                'passthrough_ui': int(self.slider_passthrough.value()),
                'passthrough_gain': round(int(self.slider_passthrough.value()) / 50.0, 3),
                'ai_vocal_ui': int(self.slider_ai_vocal.value()),
                'ai_vocal_gain': round(int(self.slider_ai_vocal.value()) / 100.0, 3),
                'reverb_mix': round(self.slider_reverb_mix.value() / 100.0, 3),
                'reverb_decay': round(self.slider_reverb_decay.value() / 100.0, 3),
            },
            'playback': {
                'play_mode': str(self.cmb_play_mode.currentData() or 'sequential'),
                'smart_switch': self.chk_smart_switch.isChecked(),
                'smart_switch_min_gap_sec': float(self.spin_smart_gap.value()),
            },
            'pitchfix': self._collect_pitchfix(),
            'shortcuts': {key: self._key_edits[key].keySequence().toString() for key in SHORTCUT_KEYS},
        }
        if self._realtime_payload:
            payload['realtime'] = dict(self._realtime_payload)
        else:
            rt = self.config.get('realtime', {}) or {}
            if rt.get('model_sid'):
                payload['realtime'] = {
                    'model_sid': rt.get('model_sid'),
                    'index_path': rt.get('index_path', ''),
                    'pitch': rt.get('pitch', 0),
                    'formant': rt.get('formant', 0.0),
                    'index_rate': rt.get('index_rate', 0.0),
                    'f0_method': rt.get('f0_method', 'rmvpe'),
                    'block_time': rt.get('block_time', 0.25),
                    'crossfade_time': rt.get('crossfade_time', 0.05),
                    'extra_time': rt.get('extra_time', 2.5),
                    'threhold': rt.get('threhold', -60),
                    'rms_mix_rate': rt.get('rms_mix_rate', 0.0),
                    'I_noise_reduce': rt.get('I_noise_reduce', False),
                    'O_noise_reduce': rt.get('O_noise_reduce', False),
                }
        return payload
