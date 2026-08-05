"""UI 与调度层之间的信号桥（界面不直接调用 MSST/RVC）。"""

from PyQt6.QtCore import QObject, pyqtSignal


class UiBridge(QObject):
    """所有 UI 用户操作统一由此转发至 AppScheduler。"""

    user_action = pyqtSignal(str, dict)
    log_message = pyqtSignal(str)
    ui_status = pyqtSignal(dict)
    ui_progress = pyqtSignal(dict)

    def emit_action(self, action: str, **payload):
        self.user_action.emit(action, payload)
        if payload.get('log'):
            self.log_message.emit(str(payload['log']))
