"""生成 assets/*.ico（主程序「趣」、桌面歌词「词」）。"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.ui.tray import desktop_lyrics_icon, main_app_icon


def _png_bytes(icon: QIcon, size: int) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    icon.pixmap(size, size).save(buf, 'PNG')
    return bytes(ba)


def _build_ico(images):
    count = len(images)
    header = struct.pack('<HHH', 0, 1, count)
    offset = 6 + count * 16
    entries = b''
    data = b''
    for size, png in images:
        w = size if size < 256 else 0
        entries += struct.pack('<BBBBHHII', w, w, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        data += png
    return header + entries + data


def _write_ico(path: Path, icon: QIcon):
    images = [(s, _png_bytes(icon, s)) for s in (16, 32, 48, 64, 128, 256)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_build_ico(images))


def main():
    app = QApplication(sys.argv)
    assets = ROOT / 'assets'
    main_ico = assets / 'main_app.ico'
    lyrics_ico = assets / 'desktop_lyrics.ico'
    _write_ico(main_ico, main_app_icon())
    _write_ico(lyrics_ico, desktop_lyrics_icon())
    print(main_ico)
    print(lyrics_ico)


if __name__ == '__main__':
    main()
