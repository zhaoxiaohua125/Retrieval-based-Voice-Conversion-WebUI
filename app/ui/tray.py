"""系统托盘菜单。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def _char_round_icon(text: str, bg: str, font_size: int = 30) -> QIcon:
    px = QPixmap(64, 64)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawRoundedRect(6, 6, 52, 52, 14, 14)
    painter.setPen(QColor('#FFFFFF'))
    font = painter.font()
    font.setFamily('Microsoft YaHei UI')
    font.setBold(True)
    font.setPixelSize(font_size)
    painter.setFont(font)
    painter.drawText(px.rect(), int(Qt.AlignmentFlag.AlignCenter), text)
    painter.end()
    return QIcon(px)


def main_app_icon() -> QIcon:
    return _char_round_icon('趣', '#2563EB')


def fallback_app_icon() -> QIcon:
    return main_app_icon()


def desktop_lyrics_icon() -> QIcon:
    return _char_round_icon('词', '#16A34A')


def build_tray(bridge, main_window, lyrics_window=None, controller=None):
    """创建托盘图标与菜单；无可用图标时使用内嵌 fallback。"""
    tray = QSystemTrayIcon(main_window)
    icon = QIcon.fromTheme('audio-headphones')
    if icon.isNull():
        icon = main_window.windowIcon()
    if icon.isNull():
        icon = fallback_app_icon()
    tray.setIcon(icon)
    tray.setToolTip('RVC AI 跟唱客户端')

    menu = QMenu(main_window)

    act_show = QAction('打开主界面', main_window)
    act_show.triggered.connect(main_window.showNormal)
    act_show.triggered.connect(main_window.raise_)
    menu.addAction(act_show)

    if lyrics_window is not None:
        act_lyrics = QAction('显示/隐藏桌面歌词', main_window)

        def toggle_lyrics():
            lyrics_window.setVisible(not lyrics_window.isVisible())
            if lyrics_window.isVisible():
                lyrics_window.sync_desktop_stack()

        act_lyrics.triggered.connect(toggle_lyrics)
        menu.addAction(act_lyrics)
        act_orient = QAction('桌面歌词横/竖切换', main_window)
        act_orient.triggered.connect(lyrics_window.toggle_orientation)
        menu.addAction(act_orient)

    act_ai = QAction('启停 AI 跟唱', main_window)
    act_ai.triggered.connect(lambda: bridge.emit_action('ai_toggle'))
    menu.addAction(act_ai)

    act_update = QAction('检查更新', main_window)
    act_update.triggered.connect(lambda: bridge.emit_action('check_update'))
    menu.addAction(act_update)

    menu.addSeparator()
    act_quit = QAction('退出', main_window)
    act_quit.triggered.connect(lambda: main_window.request_quit(confirm=True))
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: main_window.showNormal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    return tray
