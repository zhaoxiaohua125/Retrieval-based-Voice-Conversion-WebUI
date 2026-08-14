#!/usr/bin/env python3
"""烟测：安全更新（退出后覆盖）脚本链路。"""
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ops.safe_updater import launch_deferred_apply
from app.ops.updater import apply_zip_update


def main():
    errors = []
    tmp = Path(tempfile.mkdtemp(prefix='rvc-safe-upd-'))
    try:
        inst = tmp / 'install'
        inst.mkdir()
        (inst / 'a.txt').write_text('old', encoding='utf-8')
        z = tmp / 'u.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('a.txt', 'new')
        bak = apply_zip_update(z, inst, tmp / 'bak')
        if (inst / 'a.txt').read_text(encoding='utf-8') != 'new':
            errors.append('apply_zip overwrite failed')
        if not bak:
            errors.append('backup missing')

        stage = tmp / 'stage'
        stage.mkdir()
        pkg = stage / 'update.zip'
        with zipfile.ZipFile(pkg, 'w') as zf:
            zf.writestr('b.txt', 'x')
        marker = tmp / 'alive'
        marker.write_text('1', encoding='utf-8')
        child_py = tmp / 'child.py'
        child_py.write_text(
            "import time, pathlib\n"
            "p=pathlib.Path(r'''%s''')\n"
            "time.sleep(0.6)\n"
            "p.unlink(missing_ok=True)\n"
            "time.sleep(0.2)\n" % marker,
            encoding='utf-8',
        )
        import subprocess
        proc = subprocess.Popen([sys.executable, str(child_py)])
        launch_deferred_apply(pkg, inst, '9.9.9', wait_pid=proc.pid, backup_dir=tmp / 'bak2')
        proc.wait(timeout=10)
        ok = False
        for _ in range(60):
            if (inst / 'b.txt').is_file() and (inst / 'VERSION').is_file():
                ok = True
                break
            time.sleep(0.2)
        if not ok:
            err = stage / 'update_error.txt'
            detail = err.read_text(encoding='utf-8') if err.is_file() else 'timeout'
            # relaunch 失败可忽略（测试目录无启动脚本）；有 b.txt+VERSION 即覆盖成功
            if (inst / 'b.txt').is_file() and (inst / 'VERSION').is_file():
                ok = True
            else:
                errors.append('deferred apply failed: %s' % detail)
        if ok and (inst / 'VERSION').read_text(encoding='utf-8').strip() != '9.9.9':
            errors.append('VERSION mismatch')
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    if errors:
        print('FAIL:', errors)
        return 1
    print('OK safe update smoke')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
