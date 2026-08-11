#!/usr/bin/env python3
"""烟测：本地更新 manifest + 下载/解压链路（无需启动 UI）。"""

import json
import sys
import tempfile
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ops.updater import apply_zip_update, check_update, download_file
from app.ops.version import CLIENT_VERSION


def _make_zip(path: Path, files: dict):
    with zipfile.ZipFile(path, 'w') as zf:
        for name, text in files.items():
            zf.writestr(name, text)


def main():
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        serve_root = tmp / 'srv'
        serve_root.mkdir()
        releases = serve_root / 'releases'
        releases.mkdir()
        pkg = releases / 'patch.zip'
        _make_zip(pkg, {'VERSION': '9.9.9-test\n', 'patch.txt': 'ok\n'})
        manifest = {
            'latest_version': '9.9.9-test',
            'force_update': False,
            'update_desc': 'smoke test',
            'full_package_url': 'http://127.0.0.1:18765/releases/patch.zip',
            'patch_url': '',
            'md_full': '',
            'md_patch': '',
        }
        (serve_root / 'version.json').write_text(json.dumps(manifest), encoding='utf-8')
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(serve_root), **kwargs)

        httpd = ThreadingHTTPServer(('127.0.0.1', 18765), Handler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        url = 'http://127.0.0.1:18765/version.json'
        info, need = check_update('0.0.1', url)
        if not need:
            errors.append('expected need_update')
        install = tmp / 'install'
        install.mkdir()
        (install / 'old.txt').write_text('keep\n', encoding='utf-8')
        downloaded = tmp / 'dl.zip'
        download_file(manifest['full_package_url'], downloaded)
        backup = apply_zip_update(downloaded, install)
        if not (install / 'patch.txt').is_file():
            errors.append('patch.txt missing after apply')
        if not backup:
            errors.append('backup missing')
        httpd.shutdown()
    if errors:
        print('FAIL:', errors)
        return 1
    print('OK update flow current=%s checked=%s' % (CLIENT_VERSION, info.latest_version))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
