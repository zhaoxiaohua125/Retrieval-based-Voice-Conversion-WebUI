"""Task 1 acceptance: ops module (logging, hardware, exceptions, update, log bundle)."""
import json
import logging
import sys
import tempfile
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ops import (
    CLIENT_VERSION,
    apply_zip_update,
    bundle_log_files,
    check_update,
    classify_exception,
    collect_environment_info,
    compare_version,
    download_file,
    file_md5,
    rollback_update,
    run_update_flow,
    safe_call,
    setup_rotating_logging,
    upload_log_bundle,
    verify_md5,
)


class _UploadHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        self.__class__.received.append({'path': self.path, 'ok': True})
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):
        return


def main():
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_dir = tmp_path / 'logs'
        install_dir = tmp_path / 'install'
        backup_dir = tmp_path / 'backup'
        logger = setup_rotating_logging(log_dir=str(log_dir), max_bytes=512, backup_count=3)
        logger.info('task1 test begin')
        for handler in logger.handlers[:]:
            if hasattr(handler, 'flush'):
                handler.flush()

        env = collect_environment_info()
        for key in ('platform', 'python', 'cuda', 'audio_devices', 'windows'):
            if key not in env:
                errors.append('hardware missing key: %s' % key)

        captured = []

        @safe_call(reraise=False, publish=lambda exc, detail: captured.append((type(exc).__name__, detail)))
        def boom():
            raise RuntimeError('task1 simulated failure')

        if boom() is not None or not captured:
            errors.append('safe_call did not swallow simulated exception')
        if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
            errors.append('rotating file handler missing')

        zip_path = tmp_path / 'report.zip'
        bundle_log_files(log_dir, zip_path, env_info=env)
        if not zip_path.is_file():
            errors.append('log bundle not created')

        version_json = tmp_path / 'version.json'
        package_path = tmp_path / 'patch.zip'
        install_dir.mkdir(parents=True, exist_ok=True)
        (install_dir / 'app.txt').write_text('v1', encoding='utf-8')
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr('app.txt', 'v2')
        md5 = file_md5(package_path)
        version_json.write_text(json.dumps({
            'latest_version': '0.2.0',
            'force_update': False,
            'update_desc': 'task1 test patch',
            'full_package_url': package_path.as_uri(),
            'patch_url': package_path.as_uri(),
            'md_full': md5,
            'md_patch': md5,
        }), encoding='utf-8')

        if compare_version(CLIENT_VERSION, '0.2.0') >= 0:
            errors.append('compare_version should detect older client')
        info, need = check_update(CLIENT_VERSION, version_json)
        if not need:
            errors.append('check_update should require update')

        downloaded = Path(download_file(package_path.as_uri(), tmp_path / 'dl.zip', md5))
        if not verify_md5(downloaded, md5):
            errors.append('md5 verify failed')

        backup = apply_zip_update(downloaded, install_dir, backup_dir=str(backup_dir))
        if (install_dir / 'app.txt').read_text(encoding='utf-8') != 'v2':
            errors.append('apply_zip_update failed')
        rollback_update(backup, install_dir)
        if (install_dir / 'app.txt').read_text(encoding='utf-8') != 'v1':
            errors.append('rollback_update failed')

        result = run_update_flow(CLIENT_VERSION, version_json, install_dir, use_patch=True)
        if not result.get('updated'):
            errors.append('run_update_flow should update')

        if classify_exception(RuntimeError('CUDA error: out of memory')) != 'cuda':
            errors.append('classify_exception cuda failed')

        server = HTTPServer(('127.0.0.1', 0), _UploadHandler)
        port = server.server_address[1]
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            upload_log_bundle('http://127.0.0.1:%s/upload' % port, zip_path, env_info=env)
            if not _UploadHandler.received:
                errors.append('upload_log_bundle failed')
        finally:
            server.shutdown()
            thread.join(timeout=2)

        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        logger._ops_rotating_configured = False

    if errors:
        print('TASK1 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK1 PASSED: ops logging, hardware, exceptions, updater, log upload OK')


if __name__ == '__main__':
    main()
