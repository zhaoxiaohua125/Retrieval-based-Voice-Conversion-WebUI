"""播放时间 T 匹配歌词行/字。"""

from dataclasses import dataclass

from app.lyrics.types import LyricDocument, LyricLine


@dataclass
class LyricMatch:
    index: int
    line: LyricLine | None
    time_sec: float
    word_index: int = -1

    def to_dict(self):
        line = self.line
        return {
            'index': self.index,
            'word_index': self.word_index,
            'time_sec': self.time_sec,
            'text': line.text if line else '',
            'html': line.highlight_html(self.word_index, 'dark') if line else '',
            'html_light': line.highlight_html(self.word_index, 'light') if line else '',
            'has_words': bool(line and line.words),
            'start_sec': line.start_sec if line else 0.0,
            'end_sec': line.end_sec if line else 0.0,
        }


class LyricMatcher:
    """根据全局时间 T（含延迟补偿）匹配当前行与字。"""

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
            return LyricMatch(index=-1, line=None, time_sec=time_sec or 0.0, word_index=-1)
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
        word_index = -1
        if chosen and chosen.words:
            content = [w for w in chosen.words if not w.text.isspace()]
            if content and t >= content[-1].end_sec:
                # 本句唱完：全部视为已唱，避免句尾空白里一直停在最后一字
                word_index = len(chosen.words)
            else:
                for w in chosen.words:
                    if w.text.isspace():
                        continue
                    if t >= w.start_sec:
                        word_index = w.index
                    else:
                        break
        return LyricMatch(index=chosen_index, line=chosen, time_sec=t, word_index=word_index)
