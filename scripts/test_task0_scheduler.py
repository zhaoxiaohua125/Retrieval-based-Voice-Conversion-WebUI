"""Task 0 acceptance: scheduler + config + logging + bus signals."""
import logging
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config_store import ConfigStore, DEFAULT_CONFIG
from app.events import BusMessage, ModuleId, SignalType
from app.log_setup import setup_app_logging
from app.scheduler import AppScheduler


def main():
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_dir = tmp_path / 'logs'
        cfg_path = tmp_path / 'client.json'
        app_logger = setup_app_logging(log_dir=str(log_dir), console_level=logging.INFO, enable_file=True)
        app_logger.info('task0 test begin')

        store = ConfigStore(path=cfg_path)
        store.load()
        if store.get('version') != DEFAULT_CONFIG['version']:
            errors.append('default config version mismatch')
        store.set('rvc.f0_up_key', 2)
        store.save()
        store2 = ConfigStore(path=cfg_path).load()
        if store2.get('rvc.f0_up_key') != 2:
            errors.append('config save/load failed')
        if not cfg_path.is_file():
            errors.append('config file not created')

        AppScheduler.reset_for_test()
        bus = AppScheduler.instance()
        received = []
        hook_called = []

        def on_status(msg: BusMessage):
            received.append(msg)

        def on_shutdown():
            hook_called.append(True)

        bus.subscribe(SignalType.STATUS, on_status)
        bus.add_shutdown_hook(on_shutdown)
        bus.start()
        bus.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'state': 'mock_ready'}))

        worker = threading.Thread(target=lambda: None, name='mock-worker', daemon=True)
        worker.start()
        bus.register_thread('mock-worker', worker)
        if 'mock-worker' not in bus.thread_names():
            errors.append('thread register failed')
        if len(received) < 2:
            errors.append('expected >=2 status messages, got %s' % len(received))

        bus.shutdown()
        if not hook_called:
            errors.append('shutdown hook not called')
        if bus.running:
            errors.append('scheduler still running after shutdown')

        log_file = log_dir / 'client.log'
        if not log_file.is_file():
            errors.append('log file not created')
        for handler in app_logger.handlers[:]:
            handler.close()
            app_logger.removeHandler(handler)
        app_logger._app_configured = False

    if errors:
        print('TASK0 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK0 PASSED: scheduler, config, logging, bus signals OK')


if __name__ == '__main__':
    main()
