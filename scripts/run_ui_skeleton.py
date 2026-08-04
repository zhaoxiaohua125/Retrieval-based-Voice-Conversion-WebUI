"""启动 PyQt6 客户端（任务 7 全量集成）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.integration import ClientController
from app.ops.rotating_log import setup_rotating_logging
from app.scheduler import AppScheduler
from app.ui import MainWindow, LyricsWindow, UiBridge, build_tray


def main():
    setup_rotating_logging()
    scheduler = AppScheduler.instance().start()
    app = QApplication(sys.argv)
    app.setApplicationName('RVC 声迹客户端')

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, '提示', '当前系统托盘不可用，托盘菜单将跳过')

    bridge = UiBridge()
    controller = ClientController(scheduler, project_root=ROOT)
    controller.set_ui_bridge(bridge)
    controller.start()

    def on_user_action(action: str, payload: dict):
        from app.events import BusMessage, ModuleId, SignalType
        scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': action, **(payload or {})}))
        if payload.get('log'):
            bridge.log_message.emit(str(payload['log']))

    bridge.user_action.connect(on_user_action)

    window = MainWindow(bridge, project_root=ROOT)
    lyrics = LyricsWindow()
    lyrics.move(window.x() + 40, window.y() + 80)
    controller.set_lyrics_window(lyrics)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = build_tray(bridge, window, lyrics, controller)
        tray.show()

    window.show()
    bridge.log_message.emit('客户端已启动（离线做歌 / AI 跟唱 / 歌词同步已接入调度层）')

    code = app.exec()
    controller.shutdown()
    scheduler.shutdown()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
