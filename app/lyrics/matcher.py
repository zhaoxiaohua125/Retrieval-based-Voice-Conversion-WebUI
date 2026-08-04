"""播放时间 T 匹配歌词条目。"""

from dataclasses import dataclass

from app.lyrics.types import LyricDocument, LyricLine


@dataclass
class LyricMatch:
    index: int
    line: LyricLine | None
    time_sec: float

    def to_dict(self):
        return {
            'index': self.index,
            'time_sec': self.time_sec,
            'text': self.line.text if self.line else '',
            'start_sec': self.line.start_sec if self.line else 0.0,
            'end_sec': self.line.end_sec if self.line else 0.0,
        }


class LyricMatcher:
    """根据全局时间 T（含延迟补偿）匹配当前行。"""

    def __init__(self, document: LyricDocument | None = None, offset_ms: int = 0):
        self.document = document or LyricDocument()
        self.offset_ms = int(offset_ms)

    @property
    def offset_sec(self):
        return self.offset_ms / 1000.0

    def set_document(self, document: LyricDocument):
        self.document = document

    def set_offset_ms(self, offset_ms: int):
        self.offset_ms = int(offset_ms)

    def match(self, time_sec: float | None) -> LyricMatch:
        if time_sec is None or not self.document.lines:
            return LyricMatch(index=-1, line=None, time_sec=time_sec or 0.0)
        t = float(time_sec) + self.offset_sec
        chosen = None
        chosen_index = -1
        for line in self.document.lines:
            if line.start_sec <= t < line.end_sec:
                chosen = line
                chosen_index = line.index
                break
            if t >= line.start_sec:
                chosen = line
                chosen_index = line.index
        return LyricMatch(index=chosen_index, line=chosen, time_sec=t)
