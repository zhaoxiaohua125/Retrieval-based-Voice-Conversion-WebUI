"""歌词数据结构（行级 + 字级）。"""

from dataclasses import dataclass, field
from html import escape


@dataclass
class LyricWord:
    start_sec: float
    end_sec: float
    text: str
    index: int = 0

    def to_dict(self):
        return {
            'index': self.index,
            'start_sec': self.start_sec,
            'end_sec': self.end_sec,
            'text': self.text,
        }


@dataclass
class LyricLine:
    start_sec: float
    end_sec: float
    text: str
    index: int = 0
    words: list[LyricWord] = field(default_factory=list)

    def to_dict(self):
        return {
            'index': self.index,
            'start_sec': self.start_sec,
            'end_sec': self.end_sec,
            'text': self.text,
            'words': [w.to_dict() for w in self.words],
        }

    def highlight_html(self, word_index: int = -1, theme: str = 'dark') -> str:
        if not self.words:
            return escape(self.text or '')
        if theme == 'light':
            cur, past, future = '#d97706', '#2563eb', '#94a3b8'
        else:
            cur, past, future = '#fbbf24', '#93c5fd', '#e2e8f0'
        # word_index == len(words) 表示本句已全部唱完
        done = word_index >= len(self.words)
        parts = []
        for i, w in enumerate(self.words):
            t = escape(w.text)
            if done or (word_index >= 0 and i < word_index):
                parts.append('<span style="color:%s;">%s</span>' % (past, t))
            elif i == word_index:
                parts.append('<span style="color:%s;font-weight:700;">%s</span>' % (cur, t))
            else:
                parts.append('<span style="color:%s;">%s</span>' % (future, t))
        return ''.join(parts)


@dataclass
class LyricDocument:
    title: str = ''
    artist: str = ''
    lines: list[LyricLine] = field(default_factory=list)
    # whisper | energy | even | ''（未知/仅行级）
    align_mode: str = ''

    @property
    def has_words(self) -> bool:
        return any(ln.words for ln in self.lines)

    def to_dict(self):
        return {
            'title': self.title,
            'artist': self.artist,
            'has_words': self.has_words,
            'align_mode': self.align_mode,
            'lines': [line.to_dict() for line in self.lines],
        }
