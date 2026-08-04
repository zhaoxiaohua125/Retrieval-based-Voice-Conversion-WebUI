"""LRC 解析与时间校准。"""

import re
from pathlib import Path

from app.lyrics.types import LyricDocument, LyricLine

META_RE = re.compile(r'^\[([a-zA-Z]+):(.+)\]$')
TIME_TAG_RE = re.compile(r'\[(\d{1,2}):(\d{2})([.:])(\d{2,3})\]')


def _parse_timestamp(mm: str, ss: str, sep: str, frac: str) -> float:
    base = int(mm) * 60 + int(ss)
    if sep == '.':
        if len(frac) == 2:
            return base + int(frac) / 100.0
        return base + int(frac) / 1000.0
    return base + int(frac) / 100.0


def parse_lrc_text(text: str, default_tail_sec: float = 5.0) -> LyricDocument:
    """解析 LRC 文本为结构化歌词；结束时间取下一句起始或默认尾长。"""
    doc = LyricDocument()
    raw_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        meta = META_RE.match(line)
        if meta:
            key, value = meta.group(1).lower(), meta.group(2).strip()
            if key == 'ti':
                doc.title = value
            elif key == 'ar':
                doc.artist = value
            continue
        tags = list(TIME_TAG_RE.finditer(line))
        if not tags:
            continue
        text_part = TIME_TAG_RE.sub('', line).strip()
        for tag in tags:
            start = _parse_timestamp(tag.group(1), tag.group(2), tag.group(3), tag.group(4))
            raw_lines.append((start, text_part))
    raw_lines.sort(key=lambda item: item[0])
    for i, (start, txt) in enumerate(raw_lines):
        end = raw_lines[i + 1][0] if i + 1 < len(raw_lines) else start + default_tail_sec
        doc.lines.append(LyricLine(start_sec=start, end_sec=max(end, start + 0.05), text=txt, index=i))
    return doc


def load_lrc_file(path: str | Path) -> LyricDocument:
    data = Path(path).read_text(encoding='utf-8', errors='replace')
    return parse_lrc_text(data)


def shift_document(doc: LyricDocument, offset_sec: float) -> LyricDocument:
    """整体时间轴校准（秒）。"""
    if not offset_sec:
        return doc
    lines = []
    for line in doc.lines:
        lines.append(
            LyricLine(
                start_sec=max(0.0, line.start_sec + offset_sec),
                end_sec=max(0.05, line.end_sec + offset_sec),
                text=line.text,
                index=line.index,
            )
        )
    return LyricDocument(title=doc.title, artist=doc.artist, lines=lines)
