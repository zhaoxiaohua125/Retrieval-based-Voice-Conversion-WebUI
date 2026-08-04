"""启动 PyQt6 UI 骨架并连接 AppScheduler。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.events import BusMessage, ModuleId, SignalType
from app.ops.rotating_log import setup_rotating_logging
from app.scheduler import AppScheduler
from app.ui import MainWindow, LyricsWindow, UiBridge, build_tray


def _wire_lyrics(scheduler: AppScheduler, lyrics: LyricsWindow):
    from app.lyrics import LyricsService

    svc = LyricsService(scheduler).attach_scheduler()
    svc.set_tick_handler(lambda payload: lyrics.set_line(payload.get('text', ''), highlight=True))

    def on_status(msg: BusMessage):
        if msg.source != ModuleId.LYRICS:
            return
        if msg.payload.get('action') == 'lyrics_sync_started':
            lyrics.show()

    scheduler.subscribe(SignalType.STATUS, on_status)
    return svc


def _wire_scheduler(bridge: UiBridge, scheduler: AppScheduler):
    """UI 操作 → 调度总线；日志 → UI。"""

    def on_user_action(action: str, payload: dict):
        scheduler.publish(
            BusMessage(
                SignalType.STATUS,
                ModuleId.UI,
                {'action': action, **(payload or {})},
            )
        )
        if payload.get('log'):
            bridge.log_message.emit(str(payload['log']))

    bridge.user_action.connect(on_user_action)


def main():
    setup_rotating_logging()
    scheduler = AppScheduler.instance().start()
    app = QApplication(sys.argv)
    app.setApplicationName('RVC AI Follow Client')

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, '提示', '当前系统托盘不可用，托盘菜单将跳过')

    bridge = UiBridge()
    _wire_scheduler(bridge, scheduler)

    window = MainWindow(bridge, project_root=ROOT)
    lyrics = LyricsWindow()
    lyrics.move(window.x() + 40, window.y() + 80)
    _wire_lyrics(scheduler, lyrics)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = build_tray(bridge, window, lyrics)
        tray.show()

    window.show()
    bridge.log_message.emit('UI 骨架已启动（音频/推理模块将在后续阶段接入）')

    code = app.exec()
    scheduler.shutdown()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
