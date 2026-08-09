"""修词：改文本后按旧时间轴重映射；字数差大时可触发局部均分。"""

from __future__ import annotations

from app.lyrics.aligner import tokenize_lyric_text
from app.lyrics.enhanced_lrc import save_enhanced_lrc
from app.lyrics.types import LyricDocument, LyricLine, LyricWord


def remap_line(line: LyricLine, new_text: str) -> LyricLine:
    tokens = tokenize_lyric_text(new_text)
    if not tokens:
        return LyricLine(line.start_sec, line.end_sec, '', line.index, [])
    old = [w for w in line.words if w.text and not w.text.isspace()] or line.words
    if old and abs(len(tokens) - len(old)) <= max(2, len(old) // 3):
        # 句长接近：按比例映射到旧字时间戳
        words = []
        for i, tok in enumerate(tokens):
            ratio = i / max(1, len(tokens) - 1) if len(tokens) > 1 else 0.0
            src_i = min(len(old) - 1, int(round(ratio * (len(old) - 1))))
            src = old[src_i]
            if i + 1 < len(tokens):
                ratio2 = (i + 1) / max(1, len(tokens) - 1)
                src2_i = min(len(old) - 1, int(round(ratio2 * (len(old) - 1))))
                end = old[src2_i].start_sec
            else:
                end = line.end_sec
            start = src.start_sec if i == 0 else words[-1].end_sec
            words.append(LyricWord(start_sec=start, end_sec=max(end, start + 0.02), text=tok, index=i))
        if words:
            words[-1].end_sec = line.end_sec
        return LyricLine(line.start_sec, line.end_sec, ''.join(tokens), line.index, words)
    # 字数差大：整行均分
    dur = max(0.05, line.end_sec - line.start_sec)
    step = dur / len(tokens)
    words = []
    for i, tok in enumerate(tokens):
        s = line.start_sec + i * step
        e = line.start_sec + (i + 1) * step if i + 1 < len(tokens) else line.end_sec
        words.append(LyricWord(start_sec=s, end_sec=max(e, s + 0.02), text=tok, index=i))
    return LyricLine(line.start_sec, line.end_sec, ''.join(tokens), line.index, words)


def rewrite_line(doc: LyricDocument, line_index: int, new_text: str) -> LyricDocument:
    if line_index < 0 or line_index >= len(doc.lines):
        raise IndexError('line_index out of range')
    doc.lines[line_index] = remap_line(doc.lines[line_index], new_text)
    for i, ln in enumerate(doc.lines):
        ln.index = i
    return doc


def save_rewrite(doc: LyricDocument, path: str, line_index: int, new_text: str):
    rewrite_line(doc, line_index, new_text)
    return save_enhanced_lrc(doc, path)
