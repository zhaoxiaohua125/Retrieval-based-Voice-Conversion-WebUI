"""Verify packaged client runtime before shipping."""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
PY = ROOT / 'python' / 'python.exe'
errors = []


def check(name, fn):
    try:
        fn()
        print('[OK]', name)
    except Exception as exc:
        errors.append('%s: %s' % (name, exc))
        print('[FAIL]', name, exc)


def main():
    print('Package:', ROOT)
    if not PY.is_file():
        errors.append('missing python/python.exe')
        print('[FAIL] missing python/python.exe')
        return 1
    for rel in ('i18n/locale/zh_CN.json', 'i18n/locale/en_US.json'):
        p = ROOT / rel
        if not p.is_file():
            errors.append('missing %s' % rel)
            print('[FAIL] missing', rel)
            continue
        try:
            json.loads(p.read_text(encoding='utf-8'))
            print('[OK]', rel)
        except json.JSONDecodeError as exc:
            errors.append('%s JSON: %s' % (rel, exc))
            print('[FAIL]', rel, exc)
    # torch/torchaudio must be tested inside bundled interpreter
    import subprocess
    code = r"""
import torch, torchaudio
from torchaudio.transforms import Resample
print('torch', torch.__version__)
print('torchaudio', torchaudio.__version__)
print('Resample OK')
"""
    r = subprocess.run([str(PY), '-c', code], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0:
        print('[OK] torch/torchaudio')
        print(r.stdout.strip())
    else:
        errors.append('torch/torchaudio: %s' % (r.stderr or r.stdout).strip())
        print('[FAIL] torch/torchaudio')
        print((r.stderr or r.stdout).strip())
    code2 = r"""
import sys
sys.path.insert(0, '.')
from infer.rtrvc import RVC
print('infer.rtrvc OK (no torchaudio import)')
"""
    r2 = subprocess.run([str(PY), '-c', code2], cwd=str(ROOT), capture_output=True, text=True)
    if r2.returncode == 0:
        print('[OK] infer.rtrvc import')
    else:
        errors.append('infer.rtrvc: %s' % (r2.stderr or r2.stdout).strip())
        print('[FAIL] infer.rtrvc import')
        print((r2.stderr or r2.stdout).strip())
    code3 = r"""
import sys
sys.path.insert(0, '.')
import app.integration
import app.ui
print('app package OK')
"""
    r3 = subprocess.run([str(PY), '-c', code3], cwd=str(ROOT), capture_output=True, text=True)
    if r3.returncode == 0:
        print('[OK] app import')
    else:
        errors.append('app import: %s' % (r3.stderr or r3.stdout).strip())
        print('[FAIL] app import')
        print((r3.stderr or r3.stdout).strip())
    if errors:
        print('\n=== FAILED (%d) ===' % len(errors))
        for e in errors:
            print(' -', e)
        return 1
    print('\n=== ALL CHECKS PASSED ===')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
