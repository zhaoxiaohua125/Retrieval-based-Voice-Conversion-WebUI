"""客户端全局运行状态。"""

from dataclasses import dataclass, field

DEFAULT_PLAYBACK_MODE = 'normal_talk'


@dataclass
class ClientState:
    mode: str = 'idle'
    selected_mode: str = DEFAULT_PLAYBACK_MODE
    offline_running: bool = False
    realtime_running: bool = False
    passthrough_running: bool = False
    playback_running: bool = False
    ai_follow_running: bool = False
    ai_follow_preparing: bool = False
    lyrics_running: bool = False
    last_error: str = ''
    loaded_lyrics: bool = False
    current_model: str = ''
    selected_song: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'mode': self.mode,
            'selected_mode': self.selected_mode,
            'offline_running': self.offline_running,
            'realtime_running': self.realtime_running,
            'ai_follow_running': self.ai_follow_running,
            'ai_follow_preparing': self.ai_follow_preparing,
            'passthrough_running': self.passthrough_running,
            'playback_running': self.playback_running,
            'lyrics_running': self.lyrics_running,
            'last_error': self.last_error,
            'loaded_lyrics': self.loaded_lyrics,
            'current_model': self.current_model,
            'selected_song': self.selected_song,
        }
