"""Task 4B acceptance: realtime RVC streaming engine."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require_rvc_env():
    missing = []
    for name in ('torch', 'numpy', 'soundfile'):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print('TASK4B FAILED: 缺少依赖 %s，请先 conda activate rvc312' % ', '.join(missing))
        raise SystemExit(1)


def test_imports(errors):
    from app.rvc.realtime_config import RealtimeRvcConfig
    cfg = RealtimeRvcConfig(block_time=0.25)
    if cfg.f0_method != 'rmvpe':
        errors.append('RealtimeRvcConfig default mismatch')


def test_engine_imports(errors):
    from app.rvc.realtime_engine import RealtimeModelPool, RealtimeRvcEngine
    from app.rvc.realtime_service import RealtimeRvcService
    if RealtimeRvcEngine is None:
        errors.append('RealtimeRvcEngine import failed')


def test_block_infer(errors, model_sid):
    import numpy as np
    from app.rvc.realtime_config import RealtimeRvcConfig
    from app.rvc.realtime_engine import RealtimeRvcEngine
    from app.rvc.vc_context import discover_first_model

    sid = model_sid or discover_first_model()
    if not sid:
        print('block infer skip: no model in assets/weights')
        return
    engine = RealtimeRvcEngine(RealtimeRvcConfig(model_sid=sid), project_root=ROOT)
    engine.load_model(sid)
    engine.start()
    block = engine.block_frame
    sr = engine.samplerate
    t = np.arange(block, dtype=np.float32) / sr
    probe = (0.05 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    outputs = [engine.process_block(probe), engine.process_block(probe)]
    engine.stop()
    if len(outputs) != 2:
        errors.append('expected 2 output blocks')
        return
    if outputs[0].shape[0] != block:
        errors.append('output block length mismatch: %s vs engine.block_frame=%s (sr=%s)' % (outputs[0].shape[0], block, sr))
    if float(np.max(np.abs(outputs[0]))) <= 0:
        errors.append('output block is silent')
    print('block infer ok model=%s sr=%s block=%s last_ms=%.1f' % (sid, sr, block, engine.stats['last_ms']))


def test_model_switch(errors, model_sid):
    from app.rvc import RealtimeModelPool, discover_first_model

    sid = model_sid or discover_first_model()
    if not sid:
        return
    pool = RealtimeModelPool(project_root=ROOT)
    pool.preload(sid)
    pool.switch(sid)
    if pool.active_sid != sid:
        errors.append('model switch failed')
    if sid not in pool.list_loaded():
        errors.append('model not in pool')


def test_live(errors, seconds: float, model_sid):
    import time
    from app.rvc import RealtimeRvcService, discover_first_model
    from app.scheduler import AppScheduler

    sid = model_sid or discover_first_model()
    if not sid:
        errors.append('live requires model in assets/weights')
        return
    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    svc = RealtimeRvcService(scheduler, project_root=ROOT).attach_scheduler()
    try:
        svc.start(model_sid=sid, use_audio=True)
        time.sleep(max(1.0, seconds))
        stats = svc.stats()
        if stats.get('engine', {}).get('blocks', 0) < 1:
            errors.append('live produced no inference blocks')
        print('live stats: %s' % stats)
    finally:
        svc.stop()
        scheduler.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Task4B realtime RVC test')
    parser.add_argument('--model', default='', help='model filename in assets/weights')
    parser.add_argument('--live', type=float, default=0, help='run mic stream + RVC for N seconds')
    args = parser.parse_args()

    errors = []
    test_imports(errors)
    if errors:
        print('TASK4B FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    require_rvc_env()
    test_engine_imports(errors)
    test_model_switch(errors, args.model or None)
    test_block_infer(errors, args.model or None)
    if args.live and args.live > 0:
        test_live(errors, args.live, args.model or None)

    if errors:
        print('TASK4B FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK4B PASSED: realtime RVC module OK')
    if not args.live:
        print('可选 live 验收: python scripts/test_task4_realtime.py --live 5')


if __name__ == '__main__':
    main()
