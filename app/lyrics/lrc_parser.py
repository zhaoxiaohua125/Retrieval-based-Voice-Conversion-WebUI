"""LRC 解析与时间校准（兼容入口；字级见 enhanced_lrc）。"""

from pathlib import Path

from app.lyrics.enhanced_lrc import load_enhanced_lrc, parse_enhanced_lrc, shift_document
from app.lyrics.types import LyricDocument

parse_lrc_text = parse_enhanced_lrc


def load_lrc_file(path: str | Path) -> LyricDocument:
    return load_enhanced_lrc(path)


__all__ = ['load_lrc_file', 'parse_lrc_text', 'shift_document']
