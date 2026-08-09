"""Enhanced LRC 读/写：行标签 [mm:ss.xx] + 字标签 <mm:ss.xx>，兼容标准 LRC。"""

import re
from pathlib import Path

from app.lyrics.types import LyricDocument, LyricLine, LyricWord

META_RE = re.compile(r'^\[([a-zA-Z]+):(.+)\]$')
LINE_TAG_RE = re.compile(r'\[(\d{1,2}):(\d{2})([.:])(\d{2,3})\]')
WORD_TAG_RE = re.compile(r'<(\d{1,2}):(\d{2})([.:])(\d{2,3})>')


def _parse_timestamp(mm: str, ss: str, sep: str, frac: str) -> float:
    base = int(mm) * 60 + int(ss)
    if sep == '.':
        return base + int(frac) / (100.0 if len(frac) == 2 else 1000.0)
    return base + int(frac) / 100.0


def format_timestamp(sec: float, ms3: bool = False) -> str:
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = sec - m * 60
    if ms3:
        return '%02d:%06.3f' % (m, s)
    whole = int(s)
    cs = int(round((s - whole) * 100.0))
    if cs >= 100:
        whole += 1
        cs = 0
    return '%02d:%02d.%02d' % (m, whole, cs)


def _parse_words(content: str, line_end: float) -> tuple[str, list[LyricWord]]:
    matches = list(WORD_TAG_RE.finditer(content))
    if not matches:
        return content.strip(), []
    plain = WORD_TAG_RE.sub('', content).strip()
    words = []
    for i, m in enumerate(matches):
        start = _parse_timestamp(m.group(1), m.group(2), m.group(3), m.group(4))
        frag_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[m.end() : frag_end]
        next_start = (
            _parse_timestamp(matches[i + 1].group(1), matches[i + 1].group(2), matches[i + 1].group(3), matches[i + 1].group(4))
            if i + 1 < len(matches)
            else line_end
        )
        words.append(LyricWord(start_sec=start, end_sec=max(next_start, start + 0.02), text=text, index=i))
    return plain, words


def parse_enhanced_lrc(text: str, default_tail_sec: float = 5.0) -> LyricDocument:
    doc = LyricDocument()
    raw = []
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
            elif key in ('al', 'align', 'align_mode'):
                doc.align_mode = value.lower().strip()
            continue
        tags = list(LINE_TAG_RE.finditer(line))
        if not tags:
            continue
        content = LINE_TAG_RE.sub('', line)
        for tag in tags:
            start = _parse_timestamp(tag.group(1), tag.group(2), tag.group(3), tag.group(4))
            raw.append((start, content))
    raw.sort(key=lambda item: item[0])
    for i, (start, content) in enumerate(raw):
        end = raw[i + 1][0] if i + 1 < len(raw) else start + default_tail_sec
        end = max(end, start + 0.05)
        plain, words = _parse_words(content, end)
        line = LyricLine(start_sec=start, end_sec=end, text=plain, index=i, words=words)
        if words:
            from app.lyrics.aligner import normalize_line_words

            normalize_line_words(line)
        doc.lines.append(line)
    return doc


def dump_enhanced_lrc(doc: LyricDocument) -> str:
    out = []
    if doc.title:
        out.append('[ti:%s]' % doc.title)
    if doc.artist:
        out.append('[ar:%s]' % doc.artist)
    if doc.align_mode:
        out.append('[al:%s]' % doc.align_mode)
    for line in doc.lines:
        head = '[%s]' % format_timestamp(line.start_sec)
        if line.words:
            body = ''.join('<%s>%s' % (format_timestamp(w.start_sec), w.text) for w in line.words)
            out.append(head + body)
        else:
            out.append(head + (line.text or ''))
    return '\n'.join(out) + ('\n' if out else '')


def load_enhanced_lrc(path: str | Path) -> LyricDocument:
    data = Path(path).read_text(encoding='utf-8', errors='replace')
    return parse_enhanced_lrc(data)


def save_enhanced_lrc(doc: LyricDocument, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(dump_enhanced_lrc(doc), encoding='utf-8')
    return p


def shift_document(doc: LyricDocument, offset_sec: float) -> LyricDocument:
    if not offset_sec:
        return doc
    lines = []
    for line in doc.lines:
        words = [
            LyricWord(
                start_sec=max(0.0, w.start_sec + offset_sec),
                end_sec=max(0.05, w.end_sec + offset_sec),
                text=w.text,
                index=w.index,
            )
            for w in line.words
        ]
        lines.append(
            LyricLine(
                start_sec=max(0.0, line.start_sec + offset_sec),
                end_sec=max(0.05, line.end_sec + offset_sec),
                text=line.text,
                index=line.index,
                words=words,
            )
        )
    return LyricDocument(title=doc.title, artist=doc.artist, lines=lines)
