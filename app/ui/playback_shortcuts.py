"""播放页快捷键：5 个控制按钮映射，配置存 config/client.json shortcuts。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

SHORTCUT_KEYS = ('transport', 'ai_follow', 'ai_sing', 'reverb_talk', 'normal_talk')
DEFAULT_SHORTCUTS = {
    'transport': 'Space',
    'ai_follow': '1',
    'ai_sing': '2',
    'reverb_talk': '3',
    'normal_talk': '4',
}
SHORTCUT_LABELS = {
    'transport': '播放/暂停',
    'ai_follow': 'AI 跟唱',
    'ai_sing': 'AI 唱歌',
    'reverb_talk': '混响说话',
    'normal_talk': '普通说话',
}


def load_shortcuts(config) -> dict:
    raw = config.get('shortcuts', {}) or {}
    out = {}
    for key in SHORTCUT_KEYS:
        val = str(raw.get(key) or DEFAULT_SHORTCUTS.get(key) or '').strip()
        out[key] = val
    return out


class PlaybackShortcutBinder:
    def __init__(self, window, playback_page, config, playback_tab_index=0):
        self._window = window
        self._page = playback_page
        self._tab_index = playback_tab_index
        self._shortcuts: list[QShortcut] = []
        self.apply(config)

    def _on_playback_tab(self) -> bool:
        stack = getattr(self._window, 'stack', None)
        return stack is not None and stack.currentIndex() == self._tab_index

    def clear(self):
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

    def apply(self, config):
        self.clear()
        mapping = load_shortcuts(config)
        handlers = {
            'transport': self._page.trigger_transport,
            'ai_follow': self._page.trigger_ai_follow,
            'ai_sing': self._page.trigger_ai_sing,
            'reverb_talk': self._page.trigger_reverb_talk,
            'normal_talk': self._page.trigger_normal_talk,
        }
        for key, fn in handlers.items():
            text = mapping.get(key, '')
            if not text:
                continue
            seq = QKeySequence(text)
            if seq.isEmpty():
                continue
            sc = QShortcut(seq, self._window)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)

            def _wrap(handler=fn):
                if self._on_playback_tab():
                    handler()

            sc.activated.connect(_wrap)
            self._shortcuts.append(sc)
