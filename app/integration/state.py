"""客户端全局运行状态。"""

from dataclasses import dataclass, field


@dataclass
class ClientState:
    mode: str = 'idle'
    offline_running: bool = False
    realtime_running: bool = False
    lyrics_running: bool = False
    last_error: str = ''
    loaded_lyrics: bool = False
    current_model: str = ''

    def to_dict(self):
        return {
            'mode': self.mode,
            'offline_running': self.offline_running,
            'realtime_running': self.realtime_running,
            'lyrics_running': self.lyrics_running,
            'last_error': self.last_error,
            'loaded_lyrics': self.loaded_lyrics,
            'current_model': self.current_model,
        }
