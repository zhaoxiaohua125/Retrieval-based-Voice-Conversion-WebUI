"""启动 PyQt6 客户端（任务 7 全量集成）。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.runtime_env import bootstrap_runtime

bootstrap_runtime(ROOT)


def _install_qt_log_filter():
    import sys
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    _warn = (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)

    def _handler(mode, context, message):
        text = str(message)
        if 'Could not parse stylesheet' in text:
            return
        if mode in _warn:
            sys.stderr.write(text + '\n')

    qInstallMessageHandler(_handler)


_install_qt_log_filter()

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.ops.version import CLIENT_VERSION
from app.events import BusMessage, ModuleId, SignalType
from app.integration import ClientController
from app.ops.rotating_log import setup_rotating_logging
from app.scheduler import AppScheduler
from app.ui import MainWindow, LyricsWindow, UiBridge, build_tray


def _install_crash_diagnostics():
    import faulthandler
    import logging
    import threading
    import traceback

    log_dir = ROOT / 'logs' / 'client'
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        faulthandler.enable(file=open(log_dir / 'crash.log', 'a', encoding='utf-8'), all_threads=True)
    except OSError:
        faulthandler.enable()
    logger = logging.getLogger('rvc_client')

    def _thread_hook(args):
        logger.error(
            'uncaught thread exception in %s:\n%s',
            args.thread,
            ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        )

    threading.excepthook = _thread_hook


def main():
    import logging
    import threading

    console_level = logging.WARNING if (ROOT / 'VERSION').is_file() else logging.INFO
    setup_rotating_logging(console_level=console_level)
    _install_crash_diagnostics()
    scheduler = AppScheduler.instance().start()
    app = QApplication(sys.argv)
    app.setApplicationName('RVC 声迹客户端')
    app.setApplicationVersion(CLIENT_VERSION)

    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QLabel

    splash = QLabel('RVC 声迹客户端\n正在启动…')
    splash.setAlignment(Qt.AlignmentFlag.AlignCenter)
    splash.setStyleSheet('QLabel{background:#2563eb;color:#fff;font-size:16px;padding:32px 48px;border-radius:8px;}')
    splash.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
    splash.show()
    app.processEvents()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, '提示', '当前系统托盘不可用，托盘菜单将跳过')

    bridge = UiBridge()
    controller = ClientController(scheduler, project_root=ROOT)
    controller.set_ui_bridge(bridge)
    controller.start()

    def on_user_action(action: str, payload: dict):
        scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': action, **(payload or {})}))
        if payload.get('log'):
            bridge.log_message.emit(str(payload['log']))

    bridge.user_action.connect(on_user_action)

    scan_done = threading.Event()

    def _startup_scan():
        try:
            controller._scan_library_blocking()
        finally:
            scan_done.set()

    threading.Thread(target=_startup_scan, name='startup-library-scan', daemon=True).start()
    splash.setText('RVC 声迹客户端\n正在扫描歌库…')
    while not scan_done.is_set():
        app.processEvents()
        scan_done.wait(0.02)

    window = MainWindow(bridge, project_root=ROOT, config_store=controller.config_store)
    window.set_controller(controller)
    lyrics = LyricsWindow()
    lyrics.move(window.x() + 40, window.y() + 80)
    controller.set_lyrics_window(lyrics)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = build_tray(bridge, window, lyrics, controller)
        tray.show()
    window._quit_lyrics = lyrics
    window._quit_tray = tray
    window._quit_shutdown = lambda: scheduler.shutdown() if scheduler.running else None

    def _finalize():
        if scheduler.running:
            scheduler.shutdown()
        if tray is not None:
            tray.hide()
        lyrics.close()

    app.aboutToQuit.connect(_finalize)

    def _apply_scheduler_status(envelope: dict):
        source = envelope.get('source')
        payload = envelope.get('payload') or {}
        action = payload.get('action')
        page = window.page_playback
        make = window.page_song_make
        if action == 'lyric_tick' and source == ModuleId.LYRICS:
            page.set_lyric_tick(payload)
            return
        if source != ModuleId.SCHEDULER:
            return
        if action == 'offline_started':
            make.set_offline_running(True)
        elif action == 'offline_finished':
            make.show_offline_result(payload.get('result') or {})
            page.apply_library(controller.library)
            title = payload.get('title') or ''
            if title:
                window.switch_to_playback(title)
            else:
                window.switch_to_playback()
        elif action == 'offline_failed':
            make.show_offline_failed(payload.get('message', ''))
        elif action == 'offline_cancelled':
            make.show_offline_cancelled(payload.get('message', ''))
        elif action == 'library_updated':
            page.apply_library(payload.get('songs', []))
        elif action == 'song_deleted':
            page.clear_current_song()
        elif action == 'playback_tick':
            page.set_playback_state(payload)
        elif action == 'playback_started':
            page.set_mode('ai_sing', active=True)
            page.set_playback_state(payload)
        elif action == 'passthrough_started':
            page.set_mode(payload.get('mode') or 'normal_talk', active=True)
            if (payload.get('mode') or '') in ('reverb_talk', 'normal_talk') and float(payload.get('duration', 0) or 0) > 0:
                page.set_playback_state(payload)
        elif action in ('passthrough_stopped', 'passthrough_blocked'):
            page.set_playback_stopped()
        elif action == 'realtime_started':
            page.set_mode('realtime', active=True)
        elif action == 'realtime_stopped':
            page.set_mode('idle')
        elif action == 'ai_follow_preparing':
            page.set_ai_follow_busy(True)
            page.set_mode('ai_follow', active=True)
            if float(payload.get('duration', 0) or 0) > 0 or float(payload.get('position', 0) or 0) > 0:
                page.set_playback_state(payload)
        elif action == 'ai_follow_started':
            make.set_offline_running(False)
            page.set_ai_follow_busy(False)
            page.set_mode('ai_follow', active=True)
            page.set_playback_state(payload)
        elif action in ('ai_follow_stopped', 'ai_follow_finished', 'ai_follow_failed'):
            page.set_ai_follow_busy(False)
            page.set_playback_stopped()
        elif action in ('playback_paused', 'playback_resumed'):
            page.set_playback_state(payload)
        elif action == 'playback_idle':
            page.set_mode('idle')
        elif action in ('playback_stopped', 'playback_finished'):
            page.set_playback_stopped()
        elif action == 'mode_selected':
            page.set_selected_mode(payload.get('mode', 'ai_sing'))
        elif action == 'lyrics_loaded':
            page.set_lyrics_lines(payload.get('lines') or [])
        elif action == 'lyrics_missing':
            page.set_lyrics_lines([])
        elif action == 'play_mode_changed':
            page.set_play_mode(payload.get('mode', 'sequential'))
        elif action == 'select_song_ui':
            page.select_song_by_title(payload.get('title', ''))
        elif action == 'song_switched':
            page.set_song_switching(False)
        elif action == 'lyric_tick':
            page.set_lyric_tick(payload)

    bridge.ui_status.connect(_apply_scheduler_status)

    def on_scheduler_status(msg: BusMessage):
        bridge.ui_status.emit({'source': msg.source, 'payload': msg.payload or {}})

    scheduler.subscribe(SignalType.STATUS, on_scheduler_status)

    def on_scheduler_progress(msg: BusMessage):
        if msg.source != ModuleId.SCHEDULER or not controller.state.offline_running:
            return
        bridge.ui_progress.emit(msg.payload or {})

    bridge.ui_progress.connect(window.page_song_make.apply_offline_progress)
    scheduler.subscribe(SignalType.PROGRESS, on_scheduler_progress)
    window.page_playback.apply_library(controller.library)
    window.page_playback.set_play_mode(controller.config_store.get('playback.play_mode', 'sequential'))

    window.show()
    splash.close()
    QTimer.singleShot(0, window.page_playback.select_initial_song)
    bridge.log_message.emit('客户端已启动（AI 唱歌 / 离线做歌 / 歌词同步已接入）')

    code = app.exec()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
