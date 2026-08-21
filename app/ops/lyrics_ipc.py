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


def _lyrics_spawn_flags() -> int:
    if sys.platform != 'win32':
        return 0
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class LyricsIpcServer(QObject):
    def __init__(self, root: str, config=None):
        super().__init__()
        self._root = Path(root)
        self._config = config
        self._key = ipc_key(root)
        self._proc = None
        QLocalServer.removeServer(self._key)
        self._server = QLocalServer()
        if not self._server.listen(self._key):
            QLocalServer.removeServer(self._key)
            self._server.listen(self._key)
        self._sock = None
        self._pending = []
        self._server.newConnection.connect(self._accept)

    def key(self) -> str:
        return self._key

    def process(self):
        return self._proc

    def _proc_dead(self) -> bool:
        return self._proc is None or self._proc.poll() is not None

    def start_process(self, root: Path = None, config=None) -> bool:
        if not self._proc_dead():
            return True
        root = Path(root or self._root)
        cfg = config if config is not None else self._config
        script = root / 'scripts' / 'run_desktop_lyrics.py'
        if not script.is_file():
            return False
        launcher = resolve_lyrics_launcher(root, cfg)
        cmd = [launcher, str(script), '--ipc', self._key, '--root', str(root.resolve())]
        try:
            self._proc = subprocess.Popen(cmd, cwd=str(root), creationflags=_lyrics_spawn_flags())
            return True
        except OSError:
            self._proc = None
            return False

    def ensure_alive(self) -> bool:
        if not self._proc_dead():
            return True
        self._sock = None
        return self.start_process()

    def stop_process(self):
        if self._connected():
            self._write({'op': 'quit'})
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
        self._sock = None
        self._pending.clear()

    def _accept(self):
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        if self._sock is not None:
            try:
                self._sock.disconnected.disconnect(self._on_disconnect)
            except Exception:
                pass
            try:
                self._sock.disconnectFromServer()
            except Exception:
                pass
        self._sock = sock
        self._sock.disconnected.connect(self._on_disconnect)
        self._flush_pending()

    def _on_disconnect(self):
        self._sock = None

    def _connected(self) -> bool:
        return self._sock is not None and self._sock.state() == QLocalSocket.LocalSocketState.ConnectedState

    def _write(self, msg: dict) -> bool:
        if not self._connected():
            return False
        try:
            line = json.dumps(msg, ensure_ascii=False) + '\n'
            if self._sock.write(line.encode('utf-8')) < 0:
                return False
            if not self._sock.waitForBytesWritten(500):
                return False
            return True
        except Exception:
            return False

    def _flush_pending(self):
        if not self._connected():
            return
        pending = self._pending
        self._pending = []
        for msg in pending:
            if not self._write(msg):
                self._pending.append(msg)
                break

    def _queue(self, msg: dict):
        op = str((msg or {}).get('op') or '')
        if op == 'tick':
            self._pending = [m for m in self._pending if m.get('op') != 'tick']
        self._pending.append(dict(msg or {}))

    def send(self, msg: dict):
        op = str((msg or {}).get('op') or '')
        if op == 'quit':
            if self._connected():
                self._write({'op': 'quit'})
            return
        if self._proc_dead() and not self.ensure_alive():
            self._queue(msg)
            return
        if not self._connected():
            self._queue(msg)
            return
        if not self._write(msg):
            self._sock = None
            if self._proc_dead():
                self.ensure_alive()
            self._queue(msg)


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
        was_visible = self._visible
        self._server.ensure_alive()
        self._server.send({'op': 'style', 'kwargs': {
            'bg_alpha': bg_alpha, 'opacity': opacity, 'capture_mode': capture_mode,
            'chroma_color': chroma_color, 'click_through': click_through, 'stay_on_top': stay_on_top,
            'text_color': text_color, 'highlight_color': highlight_color,
        }})
        if was_visible:
            self._visible = True
            self._server.send({'op': 'show'})
            self.sync_desktop_stack()

    def show(self):
        self._visible = True
        self._server.ensure_alive()
        self._server.send({'op': 'show'})

    def hide(self):
        self._visible = False
        self._server.send({'op': 'hide'})

    def setVisible(self, visible: bool):
        self._visible = bool(visible)
        self._server.ensure_alive()
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
        self._server.stop_process()
