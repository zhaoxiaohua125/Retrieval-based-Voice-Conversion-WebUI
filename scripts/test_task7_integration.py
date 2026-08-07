"""Task 7 acceptance: integration controller routing and lifecycle."""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_controller_basics(errors):
    from app.events import BusMessage, ModuleId, SignalType
    from app.integration import ClientController
    from app.scheduler import AppScheduler

    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    events = []
    scheduler.subscribe(SignalType.STATUS, lambda m: events.append(m.payload))
    scheduler.subscribe(SignalType.ERROR, lambda m: events.append(m.payload))
    ctrl = ClientController(scheduler, project_root=ROOT)
    ctrl.start()
    scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': 'offline_cover', 'input': '', 'model': ''}))
    time.sleep(0.05)
    if not any(isinstance(e, dict) and e.get('action') == 'client_error' for e in events):
        errors.append('offline_cover with empty input should publish client_error')
    ctrl.shutdown()
    scheduler.shutdown()


def test_lyrics_route(errors):
    from app.events import BusMessage, ModuleId, SignalType
    from app.integration import ClientController
    from app.scheduler import AppScheduler

    sample = """[ti:集成测试]
[00:01.00]测试行
"""
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.lrc', delete=False) as f:
        f.write(sample)
        lrc_path = f.name
    try:
        scheduler = AppScheduler.reset_for_test()
        scheduler = AppScheduler.instance().start()
        loaded = []
        scheduler.subscribe(
            SignalType.STATUS,
            lambda m: loaded.append(m.payload) if m.payload.get('action') == 'lyrics_loaded' else None,
        )
        ctrl = ClientController(scheduler, project_root=ROOT)
        ctrl.start()
        scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': 'lyrics_load', 'path': lrc_path}))
        time.sleep(0.05)
        ctrl.shutdown()
        scheduler.shutdown()
        if not loaded:
            errors.append('lyrics_load route failed')
        if not ctrl.state.loaded_lyrics:
            errors.append('controller state loaded_lyrics not set')
    finally:
        Path(lrc_path).unlink(missing_ok=True)


def test_shutdown_idle(errors):
    from app.integration import ClientController
    from app.scheduler import AppScheduler

    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    ctrl = ClientController(scheduler, project_root=ROOT)
    ctrl.start()
    ctrl.shutdown()
    if ctrl.state.realtime_running or ctrl.state.offline_running or ctrl.state.playback_running or ctrl.state.passthrough_running:
        errors.append('shutdown should clear running flags')
    scheduler.shutdown()


def test_normal_talk_route(errors):
    from app.events import BusMessage, ModuleId, SignalType
    from app.integration import ClientController
    from app.scheduler import AppScheduler

    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    events = []
    scheduler.subscribe(SignalType.STATUS, lambda m: events.append(m.payload))
    ctrl = ClientController(scheduler, project_root=ROOT)
    ctrl.start()
    scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': 'playback_normal_talk'}))
    time.sleep(0.15)
    started = any(isinstance(e, dict) and e.get('action') == 'passthrough_started' for e in events)
    if started:
        if ctrl.state.mode != 'normal_talk' or not ctrl.state.passthrough_running:
            errors.append('normal talk should enable passthrough state')
        scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'action': 'playback_normal_talk'}))
        time.sleep(0.05)
        if ctrl.state.passthrough_running:
            errors.append('normal talk toggle off should stop passthrough')
    ctrl.shutdown()
    scheduler.shutdown()


def test_playback_library(errors):
    from app.playback import scan_song_library

    songs = scan_song_library(ROOT)
    if not isinstance(songs, list):
        errors.append('scan_song_library should return list')
    for song in songs:
        if not song.get('play_path'):
            errors.append('song missing play_path: %s' % song)
            break


def test_ai_sing_route(errors):
    from app.events import BusMessage, ModuleId, SignalType
    from app.integration import ClientController
    from app.playback import scan_song_library
    from app.scheduler import AppScheduler

    songs = scan_song_library(ROOT)
    if not songs:
        return
    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    events = []
    scheduler.subscribe(SignalType.STATUS, lambda m: events.append(m.payload))
    scheduler.subscribe(SignalType.ERROR, lambda m: events.append(m.payload))
    ctrl = ClientController(scheduler, project_root=ROOT)
    ctrl.start()
    scheduler.publish(
        BusMessage(
            SignalType.STATUS,
            ModuleId.UI,
            {'action': 'playback_ai_sing', 'song': songs[0]},
        )
    )
    import time
    time.sleep(0.3)
    ctrl._stop_playback()
    ctrl.shutdown()
    scheduler.shutdown()
    if not any(isinstance(e, dict) and e.get('action') == 'playback_started' for e in events):
        errors.append('playback_ai_sing should publish playback_started when song exists')


def main():
    errors = []
    test_controller_basics(errors)
    test_lyrics_route(errors)
    test_shutdown_idle(errors)
    test_normal_talk_route(errors)
    test_playback_library(errors)
    test_ai_sing_route(errors)
    if errors:
        print('TASK7 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK7 PASSED: integration controller OK')
    print('完整 UI 验收: python scripts/run_ui_skeleton.py')


if __name__ == '__main__':
    main()
