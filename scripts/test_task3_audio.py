"""Task 3 acceptance: audio IO (devices, ring buffer, stream manager)."""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ring_buffer(errors):
    import numpy as np
    from app.audio import RingBuffer

    buf = RingBuffer(8, channels=1)
    buf.write(np.array([[0.1], [0.2], [0.3]], dtype=np.float32))
    if buf.available_frames() != 3:
        errors.append('ring buffer write count mismatch')
    out = buf.read(2)
    if out.shape != (2, 1) or abs(float(out[0, 0]) - 0.1) > 1e-6:
        errors.append('ring buffer read order mismatch')
    buf.write(np.ones((10, 1), dtype=np.float32))
    if buf.available_frames() > buf.capacity:
        errors.append('ring buffer overflow capacity')


def test_devices(errors):
    try:
        import sounddevice  # noqa: F401
    except ImportError:
        errors.append('sounddevice 未安装')
        return
    from app.audio import device_summary, list_devices, list_hostapis

    hostapis = list_hostapis()
    if not hostapis:
        errors.append('hostapis empty')
    devices = list_devices()
    if not isinstance(devices, list):
        errors.append('list_devices must return list')
    summary = device_summary(devices)
    for key in ('total', 'tagged', 'voicemeeter', 'hostapis'):
        if key not in summary:
            errors.append('device_summary missing: %s' % key)
    print('devices=%s hostapis=%s voicemeeter=%s' % (summary['total'], len(hostapis), summary['voicemeeter']))


def test_service(errors):
    from app.events import BusMessage, ModuleId, SignalType
    from app.scheduler import AppScheduler
    from app.audio import AudioService

    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    events = []
    scheduler.subscribe(SignalType.STATUS, lambda msg: events.append(msg.payload.get('action')))
    svc = AudioService(scheduler).attach_scheduler()
    svc.list_devices()
    if 'devices_listed' not in events:
        errors.append('AudioService did not publish devices_listed')
    scheduler.shutdown()


def test_live_stream(errors, seconds: float):
    try:
        import sounddevice as sd
    except ImportError:
        errors.append('sounddevice 未安装，无法 live 测试')
        return
    from app.audio import AudioStreamConfig, AudioStreamManager, list_devices, pick_voicemeeter_defaults

    devices = list_devices()
    in_dev, out_dev = pick_voicemeeter_defaults(devices)
    if in_dev is None or out_dev is None:
        print('live skip: no input/output device')
        return
    cfg = AudioStreamConfig(
        input_device=in_dev,
        output_device=out_dev,
        block_ms=200,
        passthrough=True,
        wasapi_exclusive=False,
    )
    mgr = AudioStreamManager(cfg)
    try:
        mgr.start()
        time.sleep(max(0.5, seconds))
        stats = mgr.stats
        if stats['callbacks'] < 1:
            errors.append('live stream produced no callbacks')
        print('live stats: %s' % stats)
    finally:
        mgr.stop()
    sd._terminate()


def main():
    parser = argparse.ArgumentParser(description='Task3 audio IO test')
    parser.add_argument('--live', type=float, default=0, help='run passthrough stream for N seconds')
    args = parser.parse_args()

    errors = []
    test_ring_buffer(errors)
    test_devices(errors)
    test_service(errors)
    if args.live and args.live > 0:
        test_live_stream(errors, args.live)

    if errors:
        print('TASK3 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK3 PASSED: audio IO module OK')
    if not args.live:
        print('可选 live 验收: python scripts/test_task3_audio.py --live 3')


if __name__ == '__main__':
    main()
