"""Task 6 acceptance: LRC parse, matcher, lyrics service, optional OSC mock."""
import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_LRC = """[ti:测试歌曲]
[ar:测试歌手]
[00:12.00]第一句歌词
[01:05.20]第二句歌词
[02:30.50]第三句歌词
"""


def test_parse(errors):
    from app.lyrics import parse_lrc_text

    doc = parse_lrc_text(SAMPLE_LRC)
    if doc.title != '测试歌曲' or len(doc.lines) != 3:
        errors.append('lrc parse line count/title mismatch')
    if abs(doc.lines[1].start_sec - 65.2) > 0.01:
        errors.append('lrc timestamp parse failed: %s' % doc.lines[1].start_sec)


def test_match(errors):
    from app.lyrics import LyricMatcher, parse_lrc_text

    matcher = LyricMatcher(parse_lrc_text(SAMPLE_LRC), offset_ms=0)
    hit = matcher.match(65.5)
    if hit.index != 1 or '第二句' not in hit.line.text:
        errors.append('matcher failed at t=65.5')
    hit2 = matcher.match(12.0)
    if hit2.index != 0:
        errors.append('matcher failed at line boundary')
    matcher.set_offset_ms(-200)
    hit3 = matcher.match(65.4)
    if hit3.index != 1:
        errors.append('offset_ms compensation failed')


def test_service_sim(errors):
    from app.events import SignalType
    from app.scheduler import AppScheduler
    from app.lyrics import LyricsService

    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.lrc', delete=False) as f:
        f.write(SAMPLE_LRC)
        lrc_path = f.name
    try:
        scheduler = AppScheduler.reset_for_test()
        scheduler = AppScheduler.instance().start()
        ticks = []
        scheduler.subscribe(SignalType.STATUS, lambda msg: ticks.append(msg.payload) if msg.payload.get('action') == 'lyric_tick' else None)
        svc = LyricsService(scheduler).attach_scheduler()
        svc.load_lrc(lrc_path)
        svc.config_store.set('lyrics.clock_source', 'sim')
        svc.start(source='sim')
        svc._clock.start(base=64.8)
        time.sleep(0.6)
        svc.stop()
        scheduler.shutdown()
        if not any(t.get('index') == 1 for t in ticks):
            errors.append('sim clock did not hit lyric index 1')
    finally:
        Path(lrc_path).unlink(missing_ok=True)


def test_osc_mock(errors, port: int):
    try:
        from pythonosc.udp_client import SimpleUDPClient
    except ImportError:
        print('osc mock skip: python-osc not installed')
        return
    from app.events import SignalType
    from app.scheduler import AppScheduler
    from app.lyrics import LyricsService

    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.lrc', delete=False) as f:
        f.write(SAMPLE_LRC)
        lrc_path = f.name
    try:
        scheduler = AppScheduler.reset_for_test()
        scheduler = AppScheduler.instance().start()
        ticks = []
        scheduler.subscribe(SignalType.STATUS, lambda msg: ticks.append(msg.payload) if msg.payload.get('action') == 'lyric_tick' else None)
        svc = LyricsService(scheduler)
        svc.config_store.set('lyrics.osc_port', port)
        svc.config_store.set('lyrics.clock_source', 'osc')
        svc.load_lrc(lrc_path)
        svc.start(source='osc')
        time.sleep(0.25)
        client = SimpleUDPClient('127.0.0.1', port)

        def _send():
            for t in (12.0, 65.3):
                client.send_message('/transport/time', float(t))
                time.sleep(0.25)

        threading.Thread(target=_send, daemon=True).start()
        time.sleep(1.0)
        svc.stop()
        scheduler.shutdown()
        if not any(t.get('index') == 1 for t in ticks):
            errors.append('osc mock did not hit lyric index 1')
    finally:
        Path(lrc_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='Task6 lyrics sync test')
    parser.add_argument('--osc-port', type=int, default=9100, help='mock OSC listen port')
    parser.add_argument('--osc', action='store_true', help='run OSC mock test')
    args = parser.parse_args()

    errors = []
    test_parse(errors)
    test_match(errors)
    test_service_sim(errors)
    if args.osc:
        test_osc_mock(errors, args.osc_port)

    if errors:
        print('TASK6 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK6 PASSED: lyrics sync module OK')
    if not args.osc:
        print('可选 OSC 验收: pip install python-osc && python scripts/test_task6_lyrics.py --osc')


if __name__ == '__main__':
    main()
