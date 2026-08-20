"""桌面歌词独立进程（供直播伴侣按进程名/窗口名采集，避免与主程序 python.exe 混淆）。"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.runtime_env import bootstrap_runtime

bootstrap_runtime(ROOT)

from PyQt6.QtNetwork import QLocalSocket
from PyQt6.QtWidgets import QApplication

from app.config_store import ConfigStore
from app.ops.lyrics_ipc import ipc_key
from app.ui.lyrics_window import LyricsWindow
from app.ui.tray import desktop_lyrics_icon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ipc', required=True)
    ap.add_argument('--root', default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cfg = ConfigStore(root / 'config' / 'client.json').load()
    app = QApplication(sys.argv)
    icon = desktop_lyrics_icon()
    app.setApplicationName('桌面歌词')
    app.setWindowIcon(icon)
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('LaiquCulture.DesktopLyrics.1')
        except Exception:
            pass
    win = LyricsWindow(config=cfg)
    buf = b''

    def apply_anchor(geo):
        if not isinstance(geo, (list, tuple)) or len(geo) != 4:
            return
        class _Fake:
            def isVisible(self):
                return True

            def frameGeometry(self):
                from PyQt6.QtCore import QRect
                return QRect(int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))

        win.set_anchor_window(_Fake())

    def handle(msg: dict):
        op = str(msg.get('op') or '')
        if op == 'tick':
            win.set_lyric_tick(msg.get('payload') or {})
        elif op == 'style':
            was_visible = win.isVisible()
            kw = msg.get('kwargs') or {}
            win.apply_desktop_style(**{k: v for k, v in kw.items() if v is not None})
            if was_visible:
                win.showNormal()
                win.sync_desktop_stack()
        elif op == 'show':
            win.show()
            win.sync_desktop_stack()
        elif op == 'hide':
            win.hide()
        elif op == 'visible':
            win.setVisible(bool(msg.get('visible')))
            if win.isVisible():
                win.sync_desktop_stack()
        elif op == 'sync':
            apply_anchor(msg.get('anchor'))
            win.sync_desktop_stack()
        elif op == 'move_beside':
            apply_anchor(msg.get('anchor'))
            win.move_beside_anchor()
        elif op == 'toggle_orient':
            win.toggle_orientation()
        elif op == 'quit':
            app.quit()

    sock = QLocalSocket()
    sock.connectToServer(args.ipc or ipc_key(str(root)))
    if not sock.waitForConnected(5000):
        sys.exit(1)

    def on_read():
        nonlocal buf
        buf += bytes(sock.readAll())
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            if not line.strip():
                continue
            try:
                handle(json.loads(line.decode('utf-8')))
            except Exception:
                pass

    sock.readyRead.connect(on_read)
    win.show()
    win.sync_desktop_stack()
    code = app.exec()
    sock.disconnectFromServer()
    sys.exit(code)


if __name__ == '__main__':
    main()
