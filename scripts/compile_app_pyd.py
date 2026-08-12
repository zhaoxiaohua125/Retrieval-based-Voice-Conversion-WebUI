#!/usr/bin/env python3
"""将 app/ 业务层与 scripts/ 编译为 .pyd；app/ui/ 编译为 .pyc（PyQt 不可用 pyd）。"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 与 build_client_package.should_skip 中打入客户端包的 scripts 一致
SCRIPTS_SHIP = frozenset(
    {
        'run_ui_skeleton.py',
        'list_audio_devices.py',
        'verify_client_package.py',
    }
)

# PyQt6 页面编译为 pyd 会信号槽崩溃；输出目录内改为 .pyc 字节码
APP_PYD_SKIP_DIRS = frozenset({'ui'})


def _app_py_files(root: Path) -> list[Path]:
    return [
        p
        for p in sorted(root.rglob('*.py'))
        if not (p.relative_to(root).parts and p.relative_to(root).parts[0] in APP_PYD_SKIP_DIRS)
    ]


def _write_setup_script(work: Path):
    setup = textwrap.dedent(
        '''\
        from pathlib import Path
        from setuptools import Extension, setup
        from Cython.Build import cythonize

        work = Path(__file__).resolve().parent
        skip_ui = %r
        exts = []
        for pkg in ('app', 'scripts'):
            root = work / pkg
            if not root.is_dir():
                continue
            for py in sorted(root.rglob('*.py')):
                rel = py.relative_to(root)
                if pkg == 'app' and rel.parts and rel.parts[0] in skip_ui:
                    continue
                mod = '.'.join(py.relative_to(work).with_suffix('').parts)
                exts.append(Extension(mod, [str(py)]))

        setup(
            ext_modules=cythonize(
                exts,
                compiler_directives={'language_level': '3', 'binding': True},
                nthreads=0,
            ),
        )
        '''
    ) % (sorted(APP_PYD_SKIP_DIRS),)
    (work / 'setup_client_pyd.py').write_text(setup, encoding='utf-8')

LAUNCH_UI = textwrap.dedent(
    '''\
    """客户端入口（保留 .py，逻辑在 run_ui_skeleton.pyd）。"""
    import os
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from scripts.run_ui_skeleton import main

    if __name__ == '__main__':
        raise SystemExit(main())
    '''
)

LAUNCH_DEVICES = textwrap.dedent(
    '''\
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.list_audio_devices import main

    if __name__ == '__main__':
        raise SystemExit(main())
    '''
)

LAUNCH_VERIFY = textwrap.dedent(
    '''\
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.verify_client_package import main

    if __name__ == '__main__':
        raise SystemExit(main())
    '''
)


def _ensure_cython(python: str):
    try:
        subprocess.run([python, '-c', 'import Cython'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print('Installing Cython + setuptools...')
        subprocess.run([python, '-m', 'pip', 'install', 'cython', 'setuptools'], check=True)


def _cleanup_compiled(tree: Path):
    for pattern in ('*.py', '*.c', '*.obj', '*.lib', '*.exp', '*.pdb'):
        for p in tree.rglob(pattern):
            try:
                p.unlink()
            except OSError:
                pass


def _copy_scripts_ship(src_scripts: Path, dst_scripts: Path):
    dst_scripts.mkdir(parents=True, exist_ok=True)
    (dst_scripts / '__init__.py').write_text('', encoding='utf-8')
    for name in SCRIPTS_SHIP:
        src = src_scripts / name
        if src.is_file():
            shutil.copy2(src, dst_scripts / name)


def _write_launchers(scripts_dir: Path):
    (scripts_dir / '_launch_ui.py').write_text(LAUNCH_UI, encoding='utf-8')
    (scripts_dir / '_launch_devices.py').write_text(LAUNCH_DEVICES, encoding='utf-8')
    (scripts_dir / '_launch_verify.py').write_text(LAUNCH_VERIFY, encoding='utf-8')
    for name in SCRIPTS_SHIP:
        (scripts_dir / name).unlink(missing_ok=True)


def _copy_scripts_extra(out_scripts: Path):
    src_scripts = ROOT / 'scripts'
    for name in ('resolve_launch_python.ps1', 'repair_bundled_torch.ps1'):
        src = src_scripts / name
        if src.is_file():
            shutil.copy2(src, out_scripts / name)


def _copy_app_ui_source(src_app: Path, dst_app: Path):
    ui_src = src_app / 'ui'
    ui_dst = dst_app / 'ui'
    if ui_dst.exists():
        shutil.rmtree(ui_dst)
    shutil.copytree(ui_src, ui_dst)


def _compile_ui_pyc(ui_dir: Path, python: str) -> int:
    ui_dir = Path(ui_dir)
    py_files = list(ui_dir.rglob('*.py'))
    if not py_files:
        return 0
    proc = subprocess.run(
        [python, '-m', 'compileall', '-b', '-q', str(ui_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or '').strip()
        raise RuntimeError('compileall app/ui failed (exit %s): %s' % (proc.returncode, msg))
    for py in py_files:
        pyc = py.with_suffix('.pyc')
        if not pyc.is_file():
            raise RuntimeError('missing pyc for %s' % py.relative_to(ui_dir))
        py.unlink()
    for cache in ui_dir.rglob('__pycache__'):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
    return len(py_files)


def build_client_pyd(out_dir: Path, python: str | None = None, ui_pyc: bool = True) -> dict:
    python = str(python or sys.executable)
    out_dir = Path(out_dir).resolve()
    src_app = ROOT / 'app'
    if not src_app.is_dir():
        raise FileNotFoundError('app/ missing')
    _ensure_cython(python)
    out_app = out_dir / 'app'
    out_scripts = out_dir / 'scripts'
    for p in (out_app, out_scripts):
        if p.exists():
            shutil.rmtree(p)
    py_count = len(_app_py_files(src_app)) + len(SCRIPTS_SHIP)
    ui_py_count = len(list((src_app / 'ui').rglob('*.py')))
    (ROOT / 'dist').mkdir(parents=True, exist_ok=True)
    tmp_root = Path(tempfile.gettempdir()) / 'rvc-pyd'
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='w', dir=str(tmp_root)) as tmp:
        work = Path(tmp)
        shutil.copytree(src_app, work / 'app')
        _copy_scripts_ship(ROOT / 'scripts', work / 'scripts')
        _write_setup_script(work)
        if ui_pyc:
            print('Cython compile app/(no ui) + scripts/ (%s pyd, ui %s x .pyc, binding=True)...' % (py_count, ui_py_count))
        else:
            print('Cython compile app/(no ui) + scripts/ (%s pyd, ui %s x .py, binding=True)...' % (py_count, ui_py_count))
        proc = subprocess.run(
            [python, 'setup_client_pyd.py', 'build_ext', '--inplace'],
            cwd=work,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            raise RuntimeError('Cython build failed (exit %s). Need MSVC Build Tools.' % proc.returncode)
        for pkg in ('app', 'scripts'):
            built = work / pkg
            _cleanup_compiled(built)
            pyd_files = list(built.rglob('*.pyd'))
            expected = len(_app_py_files(ROOT / pkg)) if pkg == 'app' else len(SCRIPTS_SHIP)
            if pkg == 'scripts':
                expected = len(SCRIPTS_SHIP)
            if len(pyd_files) < expected:
                raise RuntimeError('%s pyd count %s < expected %s' % (pkg, len(pyd_files), expected))
            shutil.copytree(built, out_dir / pkg)
        _copy_app_ui_source(src_app, out_app)
        ui_pyc_count = _compile_ui_pyc(out_app / 'ui', python) if ui_pyc else 0
        _write_launchers(out_scripts)
        _copy_scripts_extra(out_scripts)
    total_pyd = len(list(out_app.rglob('*.pyd'))) + len(list(out_scripts.rglob('*.pyd')))
    total_pyc = len(list((out_app / 'ui').rglob('*.pyc'))) if ui_pyc else 0
    total_bytes = sum(p.stat().st_size for p in out_dir.rglob('*') if p.is_file())
    return {'pyd_files': total_pyd, 'ui_pyc_files': total_pyc, 'ui_pyc': ui_pyc, 'bytes': total_bytes}


def build_app_pyd(src_app: Path, dst_app: Path, python: str | None = None) -> dict:
    """兼容旧接口：仅编译 app/。"""
    dst_app = Path(dst_app).resolve()
    out_dir = dst_app.parent
    stats = build_client_pyd(out_dir, python)
    return {'pyd_files': len(list(dst_app.rglob('*.pyd'))), 'bytes': stats['bytes'], 'path': str(dst_app)}


def main():
    parser = argparse.ArgumentParser(description='Compile app core + scripts to .pyd, app/ui to .pyc')
    parser.add_argument('--output', required=True, help='Package root (含 app/ scripts/ 子目录)')
    parser.add_argument('--python', default='')
    parser.add_argument('--keep-ui-py', action='store_true', help='ui/ 保留 .py，不转 .pyc（调试）')
    args = parser.parse_args()
    stats = build_client_pyd(Path(args.output), args.python or None, ui_pyc=not args.keep_ui_py)
    if stats.get('ui_pyc'):
        print('OK: %s pyd + %s ui pyc (%.1f MB)' % (stats['pyd_files'], stats['ui_pyc_files'], stats['bytes'] / 1048576))
    else:
        print('OK: %s pyd + ui .py (%.1f MB)' % (stats['pyd_files'], stats['bytes'] / 1048576))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
