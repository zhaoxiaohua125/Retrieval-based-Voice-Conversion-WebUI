"""歌词同步与时钟模块。"""

from app.lyrics.lrc_parser import load_lrc_file, parse_lrc_text, shift_document
from app.lyrics.matcher import LyricMatch, LyricMatcher
from app.lyrics.mtc_reader import MtcPlaybackClock
from app.lyrics.osc_client import ManualPlaybackClock, OscPlaybackClock, SimPlaybackClock
from app.lyrics.service import LyricsService
from app.lyrics.types import LyricDocument, LyricLine

__all__ = [
    'LyricDocument',
    'LyricLine',
    'LyricMatch',
    'LyricMatcher',
    'LyricsService',
    'ManualPlaybackClock',
    'MtcPlaybackClock',
    'OscPlaybackClock',
    'SimPlaybackClock',
    'load_lrc_file',
    'parse_lrc_text',
    'shift_document',
]
