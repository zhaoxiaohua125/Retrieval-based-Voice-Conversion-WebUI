"""歌词同步与时钟模块。"""

from app.lyrics.aligner import (
    align_with_whisper,
    align_words_by_energy,
    enhance_lrc_file,
    ensure_words,
    fill_even_words,
    prepare_word_timing,
    refresh_karaoke_timing,
    whisper_available,
)
from app.lyrics.enhanced_lrc import dump_enhanced_lrc, load_enhanced_lrc, parse_enhanced_lrc, save_enhanced_lrc
from app.lyrics.lrc_parser import load_lrc_file, parse_lrc_text, shift_document
from app.lyrics.matcher import LyricMatch, LyricMatcher
from app.lyrics.mtc_reader import MtcPlaybackClock
from app.lyrics.osc_client import ManualPlaybackClock, OscPlaybackClock, SimPlaybackClock
from app.lyrics.rewrite import remap_line, rewrite_line
from app.lyrics.service import LyricsService
from app.lyrics.types import LyricDocument, LyricLine, LyricWord

__all__ = [
    'LyricDocument',
    'LyricLine',
    'LyricWord',
    'LyricMatch',
    'LyricMatcher',
    'LyricsService',
    'ManualPlaybackClock',
    'MtcPlaybackClock',
    'OscPlaybackClock',
    'SimPlaybackClock',
    'align_with_whisper',
    'align_words_by_energy',
    'dump_enhanced_lrc',
    'enhance_lrc_file',
    'ensure_words',
    'fill_even_words',
    'prepare_word_timing',
    'refresh_karaoke_timing',
    'whisper_available',
    'load_enhanced_lrc',
    'load_lrc_file',
    'parse_enhanced_lrc',
    'parse_lrc_text',
    'remap_line',
    'rewrite_line',
    'save_enhanced_lrc',
    'shift_document',
]
