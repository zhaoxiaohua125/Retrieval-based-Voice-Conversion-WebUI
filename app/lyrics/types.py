"""歌词数据结构。"""

from dataclasses import dataclass, field


@dataclass
class LyricLine:
    start_sec: float
    end_sec: float
    text: str
    index: int = 0

    def to_dict(self):
        return {'index': self.index, 'start_sec': self.start_sec, 'end_sec': self.end_sec, 'text': self.text}


@dataclass
class LyricDocument:
    title: str = ''
    artist: str = ''
    lines: list[LyricLine] = field(default_factory=list)

    def to_dict(self):
        return {'title': self.title, 'artist': self.artist, 'lines': [line.to_dict() for line in self.lines]}
