"""桌面歌词独立进程 IPC（主程序发指令，歌词子进程显示窗口）。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def ipc_key(root: str) -> str:
    return 'rvc_lyrics_%s' % hashlib.md5(str(root).encode('utf-8')).hexdigest()[:12]


def resolve_lyrics_launcher(root: Path, config=None) -> str:
    if config:
        custom = str(config.get('lyrics.desktop_launcher', '') or '').strip()
        if custom and Path(custom).is_file():
            return custom
    root = Path(root)
    exe_dir = Path(getattr(sys, 'executable', '') or '').resolve().parent
    for base in (root, exe_dir):
        for name in ('桌面歌词.exe', 'DesktopLyrics.exe'):
            p = base / name
            if p.is_file():
                return str(p)
    return sys.executable


class LyricsIpcServer(QObject):
    def __init__(self, root: str):
        super().__init__()
        self._key = ipc_key(root)
        self._proc = None
        QLocalServer.removeServer(self._key)
        self._server = QLocalServer()
        if not self._server.listen(self._key):
            QLocalServer.removeServer(self._key)
            self._server.listen(self._key)
        self._sock = None
        self._server.newConnection.connect(self._accept)

    def key(self) -> str:
        return self._key

    def process(self):
        return self._proc

    def start_process(self, root: Path, config=None) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        script = root / 'scripts' / 'run_desktop_lyrics.py'
        if not script.is_file():
            return False
        launcher = resolve_lyrics_launcher(root, config)
        cmd = [launcher, str(script), '--ipc', self._key, '--root', str(root.resolve())]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if launcher.lower().endswith('python.exe') else 0
        try:
            self._proc = subprocess.Popen(cmd, cwd=str(root), creationflags=flags)
            return True
        except OSError:
            self._proc = None
            return False

    def stop_process(self):
        self.send({'op': 'quit'})
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    def _accept(self):
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        if self._sock is not None:
            try:
                self._sock.disconnectFromServer()
            except Exception:
                pass
        self._sock = sock

    def send(self, msg: dict):
        if self._sock is None or self._sock.state() != QLocalSocket.LocalSocketState.ConnectedState:
            return
        try:
            line = json.dumps(msg, ensure_ascii=False) + '\n'
            self._sock.write(line.encode('utf-8'))
            self._sock.waitForBytesWritten(500)
        except Exception:
            pass


class LyricsWindowProxy:
    """主进程内替代 LyricsWindow，指令转发到独立歌词进程。"""

    def __init__(self, server: LyricsIpcServer, anchor=None):
        self._server = server
        self._anchor = anchor
        self._visible = False

    def set_anchor_window(self, window):
        self._anchor = window

    def _anchor_geo(self):
        if self._anchor is None:
            return None
        try:
            g = self._anchor.frameGeometry()
            return [g.x(), g.y(), g.width(), g.height()]
        except Exception:
            return None

    def set_lyric_tick(self, payload: dict):
        self._server.send({'op': 'tick', 'payload': dict(payload or {})})

    def apply_desktop_style(self, bg_alpha=None, opacity=None, capture_mode=None, chroma_color=None,
                            click_through=None, stay_on_top=None, text_color=None, highlight_color=None):
        self._server.send({'op': 'style', 'kwargs': {
            'bg_alpha': bg_alpha, 'opacity': opacity, 'capture_mode': capture_mode,
            'chroma_color': chroma_color, 'click_through': click_through, 'stay_on_top': stay_on_top,
            'text_color': text_color, 'highlight_color': highlight_color,
        }})

    def show(self):
        self._visible = True
        self._server.send({'op': 'show'})

    def hide(self):
        self._visible = False
        self._server.send({'op': 'hide'})

    def setVisible(self, visible: bool):
        self._visible = bool(visible)
        self._server.send({'op': 'visible', 'visible': self._visible})

    def isVisible(self) -> bool:
        return self._visible

    def sync_desktop_stack(self):
        self._server.send({'op': 'sync', 'anchor': self._anchor_geo()})

    def move_beside_anchor(self) -> bool:
        geo = self._anchor_geo()
        if not geo:
            return False
        self._server.send({'op': 'move_beside', 'anchor': geo})
        return True

    def toggle_orientation(self):
        self._server.send({'op': 'toggle_orient'})

    def stay_on_top(self) -> bool:
        return False

    def click_through(self) -> bool:
        return True

    def close(self):
        self._server.send({'op': 'quit'})
