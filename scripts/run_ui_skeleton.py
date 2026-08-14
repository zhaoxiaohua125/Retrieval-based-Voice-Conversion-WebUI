"""启动 PyQt6 客户端（任务 7 全量集成）。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _ensure_stdio(root: Path):
    log_dir = root / 'logs' / 'client'
    log_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(log_dir / 'stdout.log', 'a', encoding='utf-8', buffering=1)
    if sys.stderr is None:
        sys.stderr = open(log_dir / 'stderr.log', 'a', encoding='utf-8', buffering=1)


_ensure_stdio(ROOT)

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
            err = sys.stderr
            if err is not None:
                err.write(text + '\n')
                err.flush()

    qInstallMessageHandler(_handler)


_install_qt_log_filter()

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.ops.version import CLIENT_VERSION
from app.events import BusMessage, ModuleId, SignalType
from app.integration import ClientController
from app.ops.rotating_log import setup_rotating_logging
from app.scheduler import AppScheduler
from app.ui import MainWindow, LyricsWindow, UiBridge, build_tray
from app.ui.tray import fallback_app_icon


def _install_crash_diagnostics():
    import faulthandler

    log_dir = ROOT / 'logs' / 'client'
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        faulthandler.enable(file=open(log_dir / 'crash.log', 'a', encoding='utf-8'), all_threads=True)
    except OSError:
        faulthandler.enable()


def _startup_log(msg: str):
    import logging
    logging.getLogger('rvc_client').info('startup: %s', msg)
    if not (ROOT / 'VERSION').is_file():
        return
    try:
        log = ROOT / 'logs' / 'client' / 'startup.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
            f.flush()
    except OSError:
        pass


def _fatal_startup(app, title: str, detail: str, exc: BaseException | None = None):
    import logging
    import traceback

    text = detail
    if exc is not None:
        text = '%s\n\n%s' % (detail, traceback.format_exc())
    logging.getLogger('rvc_client').error('startup failed: %s\n%s', title, text)
    _startup_log('FATAL: %s\n%s' % (title, text))
    try:
        from app.config_store import ConfigStore
        from app.ops.crash_reporter import upload_crash_logs

        upload_crash_logs(ROOT, ConfigStore().load(), reason='startup_fatal', detail=text, sync=True)
    except Exception:
        pass
    try:
        if app is not None:
            QMessageBox.critical(None, title, detail if exc is None else '%s\n\n详见 logs/client/startup.log' % detail)
    except Exception:
        pass


def _setup_qt_runtime(root: Path):
    """打包目录内补齐 Qt 插件/DLL 搜索路径（CondaPack 常见）。"""
    if not (root / 'VERSION').is_file():
        return
    for rel in (
        'python/Lib/site-packages/PyQt6/Qt6/plugins/platforms',
        'python/Lib/site-packages/PyQt6/Qt/plugins/platforms',
    ):
        plat = root / rel
        if not (plat / 'qwindows.dll').is_file():
            continue
        os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', str(plat))
        qt_bin = plat.parent.parent / 'bin'
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(str(plat))
                if qt_bin.is_dir():
                    os.add_dll_directory(str(qt_bin))
            except OSError:
                pass
        break


def main():
    import logging
    import threading
    import traceback

    app = None
    try:
        console_level = logging.WARNING if (ROOT / 'VERSION').is_file() else logging.INFO
        setup_rotating_logging(console_level=console_level)
        _install_crash_diagnostics()
        from app.config_store import ConfigStore
        from app.ops.crash_reporter import install_crash_hooks, mark_clean_exit, startup_crash_check

        boot_config = ConfigStore().load()
        startup_crash_check(ROOT, boot_config)
        _setup_qt_runtime(ROOT)
        _startup_log('logging ready')
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName('来取文化')
        app.setApplicationVersion(CLIENT_VERSION)
        app_icon = fallback_app_icon()
        app.setWindowIcon(app_icon)

        from PyQt6.QtCore import QObject, QTimer, pyqtSignal

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.warning(None, '提示', '当前系统托盘不可用，托盘菜单将跳过')

        bridge = UiBridge()
        window = MainWindow(bridge, project_root=ROOT, config_store=boot_config)
        window.setWindowIcon(app_icon)
        window.show()
        window.raise_()
        window.activateWindow()
        app.processEvents()
        _startup_log('startup window shown login=%s' % boot_config.get('auth.show_login', True))
        if not boot_config.get('auth.show_login', True):
            window.begin_guest_boot()

        ctx = {'controller': None, 'scheduler': None, 'lyrics': None}

        class BootSignals(QObject):
            status = pyqtSignal(str)
            done = pyqtSignal()
            failed = pyqtSignal(str)

        boot = BootSignals()

        def on_boot_status(text: str):
            window.set_boot_status(text)

        def on_boot_failed(detail: str):
            window.on_boot_failed()
            _fatal_startup(app, '后台初始化失败', detail)

        boot.status.connect(on_boot_status)
        boot.failed.connect(on_boot_failed)

        def _bootstrap_thread():
            try:
                boot.status.emit('正在初始化…')
                scheduler = AppScheduler.instance().start()
                controller = ClientController(scheduler, project_root=ROOT, config=boot_config)
                controller.set_ui_bridge(bridge)
                controller.start()
                install_crash_hooks(ROOT, controller.config_store)
                ctx['scheduler'] = scheduler
                ctx['controller'] = controller
                boot.status.emit('正在扫描歌库…')
                controller._scan_library_blocking()
                _startup_log('library scan done count=%s' % len(controller.library))
                boot.done.emit()
            except Exception as exc:
                boot.failed.emit(str(exc))

        def _wire_after_boot():
            scheduler = ctx['scheduler']
            controller = ctx['controller']
            if scheduler is None or controller is None:
                return
            _startup_log('controller ready')

            def on_user_action(action: str, payload: dict):
                scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': action, **(payload or {})}))
                if payload.get('log'):
                    bridge.log_message.emit(str(payload['log']))

            bridge.user_action.connect(on_user_action)
            window.set_controller(controller)
            window._quit_lyrics = None
            window._quit_tray = None
            window._quit_shutdown = lambda: scheduler.shutdown() if scheduler.running else None

            def _finalize():
                try:
                    mark_clean_exit(ROOT, controller.config_store)
                except Exception:
                    pass
                if scheduler.running:
                    scheduler.shutdown()
                lyrics = getattr(window, '_quit_lyrics', None)
                if lyrics is not None:
                    lyrics.close()
                tray = getattr(window, '_quit_tray', None)
                if tray is not None:
                    tray.hide()

            app.aboutToQuit.connect(_finalize)
            _startup_log('hooks ready')

            def _apply_scheduler_status(envelope: dict):
                source = envelope.get('source')
                payload = envelope.get('payload') or {}
                action = payload.get('action')
                if not window.is_main_ready():
                    if not str(action or '').startswith('update'):
                        return
                page = window.page_playback if window.is_main_ready() else None
                make = window.page_song_make if window.is_main_ready() else None
                if action == 'lyric_tick' and source == ModuleId.LYRICS and page is not None:
                    page.set_lyric_tick(payload)
                    return
                if source != ModuleId.SCHEDULER:
                    return
                if page is None or make is None:
                    return
                if action == 'offline_started':
                    make.set_offline_running(True)
                elif action == 'offline_finished':
                    make.show_offline_result(payload.get('result') or {})
                    page.apply_library(controller.library, inst_songs=controller.library_inst)
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
                    page.apply_library(
                        payload.get('sing_songs') or payload.get('songs', []),
                        inst_songs=payload.get('inst_songs', []),
                    )
                elif action == 'song_deleted':
                    page.clear_current_song()
                elif action == 'playback_tick':
                    page.set_playback_state(payload)
                elif action == 'smart_switch_tick':
                    overlay = payload.get('overlay_mode') or ''
                    if overlay in ('ai_sing', 'ai_follow', 'reverb_talk', 'normal_talk'):
                        page.set_selected_mode(overlay)
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
                elif action == 'update_available':
                    from app.ui.update_dialog import show_update_prompt

                    window._update_dialog = show_update_prompt(window, bridge, payload)
                elif action == 'update_checked':
                    if not payload.get('silent'):
                        QMessageBox.information(window, '检查更新', payload.get('message') or '已是最新版本')
                elif action == 'update_failed':
                    msg = payload.get('message') or '更新失败'
                    dlg = getattr(window, '_update_dialog', None)
                    if dlg is not None and dlg.isVisible():
                        dlg.mark_failed(msg)
                    elif not payload.get('silent'):
                        QMessageBox.warning(window, '更新', msg)
                elif action == 'update_finished':
                    dlg = getattr(window, '_update_dialog', None)
                    if dlg is not None:
                        try:
                            dlg.accept()
                        except RuntimeError:
                            pass
                        window._update_dialog = None
                    if payload.get('updated'):
                        ans = QMessageBox.question(
                            window,
                            '更新完成',
                            '已更新至 %s，是否立即重启客户端？' % (payload.get('version') or ''),
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        )
                        if ans == QMessageBox.StandardButton.Yes:
                            from app.ops.install_root import relaunch_client

                            try:
                                relaunch_client(ROOT)
                            except Exception as exc:
                                QMessageBox.warning(window, '重启失败', str(exc))
                            else:
                                app.quit()
                    elif payload.get('message') and not payload.get('silent'):
                        QMessageBox.information(window, '更新', payload.get('message'))
                elif action == 'update_skipped':
                    window._update_dialog = None
                elif action == 'lyric_tick':
                    page.set_lyric_tick(payload)

            def _on_main_entered():
                window.page_playback.apply_library(
                    controller.library,
                    inst_songs=controller.library_inst,
                    auto_select=False,
                )
                window.page_playback.set_play_mode(controller.config_store.get('playback.play_mode', 'sequential'))
                QTimer.singleShot(120, window.page_playback.select_initial_song)
                _startup_log('main ui wired after login')

            window.main_entered.connect(_on_main_entered)
            bridge.ui_status.connect(_apply_scheduler_status)

            def on_scheduler_status(msg: BusMessage):
                bridge.ui_status.emit({'source': msg.source, 'payload': msg.payload or {}})

            scheduler.subscribe(SignalType.STATUS, on_scheduler_status)

            def on_scheduler_progress(msg: BusMessage):
                payload = msg.payload or {}
                if msg.source == ModuleId.SCHEDULER and payload.get('phase') == 'update':
                    dlg = getattr(window, '_update_dialog', None)
                    if dlg is not None:
                        dlg.set_progress(int(payload.get('percent', 0) or 0), str(payload.get('message') or ''))
                    return
                if msg.source != ModuleId.SCHEDULER or not controller.state.offline_running:
                    return
                bridge.ui_progress.emit(payload)

            def _forward_offline_progress(payload):
                if window.is_main_ready():
                    window.page_song_make.apply_offline_progress(payload)

            bridge.ui_progress.connect(_forward_offline_progress)
            scheduler.subscribe(SignalType.PROGRESS, on_scheduler_progress)
            _startup_log('ui wired')
            bridge.log_message.emit('客户端已启动（AI 唱歌 / 离线做歌 / 歌词同步已接入）')
            window.mark_backend_ready()

            def _init_lyrics_tray():
                lyrics = LyricsWindow()
                lyrics.move(window.x() + 40, window.y() + 80)
                controller.set_lyrics_window(lyrics)
                ctx['lyrics'] = lyrics
                window._quit_lyrics = lyrics
                tray = None
                if QSystemTrayIcon.isSystemTrayAvailable():
                    try:
                        tray = build_tray(bridge, window, lyrics, controller)
                        if not tray.show():
                            _startup_log('tray show returned false')
                        else:
                            _startup_log('tray ready')
                    except Exception as exc:
                        _startup_log('tray failed: %s' % exc)
                window._quit_tray = tray

            def _auto_check_update():
                if not controller.config_store.get('update.auto_check', True):
                    return
                url = str(controller.config_store.get('update.check_url', '') or '').strip()
                if url:
                    bridge.emit_action('check_update', silent=True)

            QTimer.singleShot(0, _init_lyrics_tray)
            QTimer.singleShot(4000, _auto_check_update)

        boot.done.connect(_wire_after_boot)
        threading.Thread(target=_bootstrap_thread, name='startup-bootstrap', daemon=True).start()

        return app.exec()
    except Exception as exc:
        _fatal_startup(app, '客户端启动失败', str(exc), exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
