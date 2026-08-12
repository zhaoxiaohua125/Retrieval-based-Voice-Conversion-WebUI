"""系统设置：侧栏 Tab + 音频/播放/歌词/常规/快捷键。"""

from PyQt6.QtCore import Qt
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

from app.audio.devices import list_devices, list_hostapis, pick_voicemeeter_defaults
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
        self._realtime_payload = None
        self._pf_sliders = {}
        self.setWindowTitle('系统设置')
        self.setMinimumSize(860, 620)
        self.resize(920, 680)
        self._build_ui()
        self._load_values()
        self._reload_devices()

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
            'lyrics': '逐字歌词生成与高亮同步参数。',
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
            form.addRow('输出设备', self.cmb_output)
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
            self.slider_passthrough.setRange(50, 200)
            self.slider_passthrough.setToolTip('50%～200%，默认 100%=2 倍增益；保存后请重开「普通说话」')
            self.lbl_passthrough = QLabel('')
            self.lbl_passthrough.setMinimumWidth(44)
            self.lbl_passthrough.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.slider_passthrough.valueChanged.connect(lambda v: self.lbl_passthrough.setText('%s%%' % v))
            pt_row.addWidget(self.slider_passthrough, stretch=1)
            pt_row.addWidget(self.lbl_passthrough)
            talk_layout.addLayout(pt_row)
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
            self.edit_update_url = QLineEdit()
            self.edit_log_dir = QLineEdit()
            self.chk_auto_check = QCheckBox('启动时自动检查更新')
            self.chk_crash_upload = QCheckBox('崩溃时自动上报日志')
            self.edit_log_upload_url = QLineEdit()
            self.edit_log_upload_url.setPlaceholderText('留空则从更新地址推导 /api/logs/upload')
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
        self.edit_update_url.setText(str(self.config.get('update.check_url', layout.get('update_url', ''))))
        self.chk_auto_check.setChecked(bool(self.config.get('update.auto_check', True)))
        self.chk_crash_upload.setChecked(bool(self.config.get('logs.auto_upload_crash', True)))
        self.edit_log_upload_url.setText(str(self.config.get('logs.upload_url', '')))
        self.edit_log_dir.setText(str(self.config.get('paths.log_dir', layout.get('log_dir', 'logs/client'))))
        self.spin_sample_rate.setValue(int(self.config.get('audio.sample_rate', 48000)))
        self.chk_wasapi.setChecked(bool(self.config.get('audio.wasapi_exclusive', False)))
        pt_ui = int(self.config.get('audio.passthrough_ui', 100))
        self.slider_passthrough.setValue(max(50, min(200, pt_ui)))
        self.lbl_passthrough.setText('%s%%' % self.slider_passthrough.value())
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
        hostapi = self._hostapi_filter()
        devices = list_devices(hostapi=hostapi)
        in_idx = self.config.get('audio.input_device')
        out_idx = self.config.get('audio.output_device')
        if in_idx is None or out_idx is None:
            def_in, def_out = pick_voicemeeter_defaults(devices)
            in_idx = in_idx if in_idx is not None else def_in
            out_idx = out_idx if out_idx is not None else def_out

        def fill_combo(combo, items, selected):
            combo.blockSignals(True)
            combo.clear()
            sel_row = -1
            for dev in items:
                combo.addItem('[%s] %s' % (dev.index, dev.name), dev.index)
                if selected is not None and dev.index == selected:
                    sel_row = combo.count() - 1
            if sel_row >= 0:
                combo.setCurrentIndex(sel_row)
            elif combo.count():
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        inputs = [d for d in devices if d.max_input_channels > 0]
        outputs = [d for d in devices if d.max_output_channels > 0]
        fill_combo(self.cmb_input, inputs, in_idx)
        fill_combo(self.cmb_output, outputs, out_idx)
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
        dev = self.cmb_input.currentData()
        if dev is None:
            return
        for d in list_devices(hostapi=self._hostapi_filter()):
            if d.index == dev and d.default_samplerate:
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
        super().reject()

    def collect_payload(self) -> dict:
        sr_type = 'sr_device' if self.radio_sr_device.isChecked() else 'sr_model'
        sample_rate = int(self.spin_sample_rate.value())
        if sr_type == 'sr_device':
            dev = self.cmb_input.currentData()
            if dev is not None:
                for d in list_devices(hostapi=self._hostapi_filter()):
                    if d.index == dev and d.default_samplerate:
                        sample_rate = int(d.default_samplerate)
                        break
        payload = {
            'osc_port': self.spin_osc.value(),
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
            },
            'audio': {
                'hostapi': self._hostapi_filter(),
                'wasapi_exclusive': self.chk_wasapi.isChecked(),
                'input_device': self.cmb_input.currentData(),
                'output_device': self.cmb_output.currentData(),
                'sample_rate': sample_rate,
                'passthrough_ui': int(self.slider_passthrough.value()),
                'passthrough_gain': round(int(self.slider_passthrough.value()) / 50.0, 3),
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
