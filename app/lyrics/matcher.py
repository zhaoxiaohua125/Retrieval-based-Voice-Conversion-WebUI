"""播放时间 T 匹配歌词行/字。"""

from dataclasses import dataclass
from html import escape

from app.lyrics.types import LyricDocument, LyricLine


@dataclass
class LyricMatch:
    index: int
    line: LyricLine | None
    time_sec: float
    word_index: int = -1
    next_text: str = ''
    page_base: int = 0
    page_top_text: str = ''
    page_bot_text: str = ''
    page_top_html: str = ''
    page_bot_html: str = ''
    page_has_words: bool = False

    def to_dict(self):
        line = self.line
        return {
            'index': self.index,
            'word_index': self.word_index,
            'time_sec': self.time_sec,
            'text': line.text if line else '',
            'next_text': self.next_text or '',
            'html': line.highlight_html(self.word_index, 'dark') if line else '',
            'html_light': line.highlight_html(self.word_index, 'light') if line else '',
            'has_words': bool(line and line.words),
            'start_sec': line.start_sec if line else 0.0,
            'end_sec': line.end_sec if line else 0.0,
            'page_base': self.page_base,
            'page_top_text': self.page_top_text or '',
            'page_bot_text': self.page_bot_text or '',
            'page_top_html': self.page_top_html or '',
            'page_bot_html': self.page_bot_html or '',
            'page_has_words': bool(self.page_has_words),
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
        next_text = ''
        if chosen_index >= 0 and chosen_index + 1 < len(self.document.lines):
            next_text = self.document.lines[chosen_index + 1].text or ''
        elif chosen_index < 0 and self.document.lines:
            next_text = self.document.lines[0].text or ''
        page = self._page_pair(chosen_index, word_index)
        return LyricMatch(
            index=chosen_index,
            line=chosen,
            time_sec=t,
            word_index=word_index,
            next_text=next_text,
            **page,
        )

    def _page_pair(self, chosen_index: int, word_index: int) -> dict:
        """酷狗双行页：0/1 一页，2/3 一页；页内两行都唱完才翻页。"""
        lines = self.document.lines
        if not lines:
            return {}
        page_base = 0 if chosen_index < 0 else (chosen_index // 2) * 2
        top = lines[page_base] if page_base < len(lines) else None
        bot = lines[page_base + 1] if page_base + 1 < len(lines) else None
        top_text = (top.text if top else '') or ''
        bot_text = (bot.text if bot else '') or ''
        has_words = bool((top and top.words) or (bot and bot.words))

        def _html(line: LyricLine | None, wi: int) -> str:
            if not line:
                return ''
            if line.words:
                return line.highlight_html(wi, 'dark')
            if wi < 0:
                return '<span style="color:#e2e8f0;">%s</span>' % escape(line.text or '')
            if wi >= 10**9:
                return '<span style="color:#93c5fd;">%s</span>' % escape(line.text or '')
            return '<span style="color:#fbbf24;">%s</span>' % escape(line.text or '')

        if chosen_index < 0:
            top_html, bot_html = _html(top, -1), _html(bot, -1)
        elif chosen_index == page_base:
            top_html = _html(top, word_index if (top and top.words) else 0)
            bot_html = _html(bot, -1)
        else:
            top_done = len(top.words) if (top and top.words) else 10**9
            top_html = _html(top, top_done)
            bot_html = _html(bot, word_index if (bot and bot.words) else 0)
        return {
            'page_base': page_base,
            'page_top_text': top_text,
            'page_bot_text': bot_text,
            'page_top_html': top_html,
            'page_bot_html': bot_html,
            'page_has_words': has_words,
        }


def _line_sing_end(line: LyricLine, next_line: LyricLine | None) -> float:
    """估算本句实际演唱结束时刻（LRC 行 end 常等于下一句 start，不能用来判间奏）。"""
    if line.words:
        content = [w for w in line.words if not w.text.isspace()]
        if content:
            return max(float(content[-1].end_sec), float(line.start_sec) + 0.25)
    text = (line.text or '').strip()
    est = max(1.2, min(12.0, max(len(text), 1) * 0.28))
    end = float(line.start_sec) + est
    if next_line is not None:
        end = min(end, float(next_line.start_sec) - 0.05)
    else:
        end = min(max(end, float(line.start_sec) + 0.5), float(line.end_sec))
    return max(end, float(line.start_sec) + 0.2)


def is_vocal_region(time_sec: float, document: LyricDocument, offset_ms: int = 0, min_gap_sec: float = 3.0) -> bool:
    """True=唱段（AI 唱歌/跟唱）；False=前奏/长间奏/尾奏（智能切混响说话）。"""
    lines = document.lines if document else []
    if not lines:
        return True
    t = float(time_sec) + int(offset_ms) / 1000.0
    min_gap = max(0.5, float(min_gap_sec or 3.0))
    if t < lines[0].start_sec:
        return False
    for i, line in enumerate(lines):
        sing_end = _line_sing_end(line, lines[i + 1] if i + 1 < len(lines) else None)
        if line.start_sec <= t < sing_end:
            return True
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            gap = float(nxt.start_sec) - sing_end
            if gap >= min_gap and sing_end <= t < nxt.start_sec:
                return False
            if sing_end <= t < nxt.start_sec:
                return True
    last_end = _line_sing_end(lines[-1], None)
    return t < last_end
