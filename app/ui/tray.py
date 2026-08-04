"""系统托盘菜单。"""

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def build_tray(bridge, main_window, lyrics_window=None):
    """创建托盘图标与菜单；无可用图标时使用系统默认样式。"""
    tray = QSystemTrayIcon(main_window)
    icon = QIcon.fromTheme('audio-headphones')
    if icon.isNull():
        icon = main_window.windowIcon()
    if not icon.isNull():
        tray.setIcon(icon)
    tray.setToolTip('RVC AI 跟唱客户端')

    menu = QMenu(main_window)

    act_show = QAction('打开主界面', main_window)
    act_show.triggered.connect(main_window.showNormal)
    act_show.triggered.connect(main_window.raise_)
    menu.addAction(act_show)

    if lyrics_window is not None:
        act_lyrics = QAction('显示/隐藏歌词窗', main_window)

        def toggle_lyrics():
            lyrics_window.setVisible(not lyrics_window.isVisible())

        act_lyrics.triggered.connect(toggle_lyrics)
        menu.addAction(act_lyrics)

    act_ai = QAction('启停 AI（占位）', main_window)
    act_ai.triggered.connect(lambda: bridge.emit_action('ai_toggle', log='AI 启停：音频模块未接入'))
    menu.addAction(act_ai)

    act_update = QAction('检查更新（占位）', main_window)
    act_update.triggered.connect(lambda: bridge.emit_action('check_update', log='检查更新：运维模块待集成'))
    menu.addAction(act_update)

    menu.addSeparator()
    act_quit = QAction('退出', main_window)
    act_quit.triggered.connect(QApplication.instance().quit)
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: main_window.showNormal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    return tray
