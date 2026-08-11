"""打包客户端演示目录（嵌入式 Python / 源码 + 启动器方案）。"""

import argparse
import fnmatch
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'packaging' / 'manifest.json'
LAUNCHER_BAT = ROOT / 'packaging' / 'launcher' / '启动唱歌伴侣客户端.bat'


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def should_skip(rel: str, manifest: dict) -> bool:
    parts = Path(rel).parts
    for d in manifest.get('exclude_dirs', []):
        if d in parts:
            return True
    name = Path(rel).name
    for pattern in manifest.get('exclude_globs', []):
        if fnmatch.fnmatch(name, pattern):
            return True
        if fnmatch.fnmatch(rel.replace('\\', '/'), pattern):
            return True
    if rel.startswith('scripts/') and Path(rel).name not in (
        'run_ui_skeleton.py',
        'list_audio_devices.py',
        'resolve_launch_python.ps1',
        'repair_bundled_torch.ps1',
        'verify_client_package.py',
    ):
        return True
    return False


def is_client_release_path(rel: str, manifest: dict | None = None) -> bool:
    """是否属于客户端安装包内的可发布路径（与 copy_tree 规则一致）。"""
    manifest = manifest or load_manifest()
    rel = str(rel).replace('\\', '/').lstrip('./')
    if not rel or should_skip(rel, manifest):
        return False
    top = rel.split('/')[0]
    if top in manifest.get('include_dirs', []):
        return True
    inc = {str(x).replace('\\', '/') for x in manifest.get('include_files', [])}
    return rel in inc


def copy_tree(src: Path, dst: Path, manifest: dict, stats: dict):
    if not src.exists():
        return
    if src.is_file():
        rel = str(src.relative_to(ROOT)).replace('\\', '/')
        if should_skip(rel, manifest):
            stats['skipped'] += 1
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        stats['files'] += 1
        stats['bytes'] += dst.stat().st_size
        return
    for item in sorted(src.iterdir()):
        rel = str(item.relative_to(ROOT)).replace('\\', '/')
        if should_skip(rel, manifest):
            stats['skipped'] += 1
            continue
        target = dst / item.name
        if item.is_dir():
            copy_tree(item, target, manifest, stats)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            stats['files'] += 1
            stats['bytes'] += target.stat().st_size


def write_launcher(out_dir: Path):
    LAUNCHER_BAT.parent.mkdir(parents=True, exist_ok=True)
    resolve_ps1 = ROOT / 'scripts' / 'resolve_launch_python.ps1'
    if resolve_ps1.is_file():
        dst = out_dir / 'scripts' / 'resolve_launch_python.ps1'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolve_ps1, dst)
    for script_name in ('repair_bundled_torch.ps1', 'verify_client_package.py'):
        src = ROOT / 'scripts' / script_name
        if src.is_file():
            dst = out_dir / 'scripts' / script_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    bat = (
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'set "PATH=%~dp0tools\\ffmpeg;%PATH%"\r\n'
        'set "PY="\r\n'
        'set "PYW="\r\n'
        'if exist "python\\python.exe" set "PY=python\\python.exe"\r\n'
        'if not defined PY if exist "python\\Scripts\\python.exe" set "PY=python\\Scripts\\python.exe"\r\n'
        'if not defined PY for /f "delims=" %%i in (\'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\resolve_launch_python.ps1"\') do set "PY=%%i"\r\n'
        'if not defined PY (\r\n'
        '  echo [ERROR] No Python with PyTorch found.\r\n'
        '  echo Rebuild with: build_demo_package.bat  ^(includes CondaPack^)\r\n'
        '  echo Or install conda env rvc312. See DEMO_README.md\r\n'
        '  pause\r\n'
        '  exit /b 1\r\n'
        ')\r\n'
        'set "PYW=%PY:python.exe=pythonw.exe%"\r\n'
        'if not exist "%PYW%" (\r\n'
        '  echo [ERROR] pythonw.exe not found beside %PY%\r\n'
        '  pause\r\n'
        '  exit /b 1\r\n'
        ')\r\n'
        'start "" "%PYW%" scripts\\run_ui_skeleton.py\r\n'
        'exit /b 0\r\n'
    )
    debug_bat = (
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'set "PATH=%~dp0tools\\ffmpeg;%PATH%"\r\n'
        'set "PY="\r\n'
        'if exist "python\\python.exe" set "PY=python\\python.exe"\r\n'
        'if not defined PY for /f "delims=" %%i in (\'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\resolve_launch_python.ps1"\') do set "PY=%%i"\r\n'
        'if not defined PY (\r\n'
        '  echo [ERROR] No Python with PyTorch found.\r\n'
        '  echo Rebuild with: build_demo_package.bat\r\n'
        '  pause\r\n'
        '  exit /b 1\r\n'
        ')\r\n'
        'echo [Debug] Using %PY%\r\n'
        '"%PY%" scripts\\run_ui_skeleton.py\r\n'
        'echo Exit: %ERRORLEVEL%\r\n'
        'pause\r\n'
    )
    wrapper = (
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'set "PATH=%~dp0tools\\ffmpeg;%PATH%"\r\n'
        'if exist "python\\pythonw.exe" (\r\n'
        '  start "" "python\\pythonw.exe" scripts\\run_ui_skeleton.py\r\n'
        '  exit /b 0\r\n'
        ')\r\n'
        'call "%~dp0StartClient.bat"\r\n'
    )
    repair_bat = '@echo off\r\ncd /d "%~dp0"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\repair_bundled_torch.ps1" -PackageDir "%~dp0"\r\npause\r\n'
    verify_bat = '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" "%~dp0scripts\\verify_client_package.py" "%~dp0"\r\npause\r\n'
    for name, content in (
        ('StartClient.bat', bat),
        ('StartClient_Debug.bat', debug_bat),
        ('启动唱歌伴侣客户端.bat', wrapper),
        ('repair_bundled_torch.bat', repair_bat),
        ('verify_client_package.bat', verify_bat),
    ):
        (out_dir / name).write_bytes(content.encode('ascii'))


def build(version: str, output_root: Path, lite: bool, cuda_variant: str = '') -> Path:
    manifest = load_manifest()
    if version:
        manifest['version'] = version
    ver = manifest['version']
    out_dir = output_root / ('RVC-Client-%s' % ver)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    stats = {'files': 0, 'bytes': 0, 'skipped': 0}

    for name in manifest.get('include_dirs', []):
        if lite and name == 'assets':
            (out_dir / 'assets' / 'weights').mkdir(parents=True, exist_ok=True)
            (out_dir / 'assets' / 'indices').mkdir(parents=True, exist_ok=True)
            (out_dir / 'assets' / 'pymss_weights').mkdir(parents=True, exist_ok=True)
            for sub, hint in (
                ('weights', '放置 .pth 模型'),
                ('indices', '放置 .index'),
                ('pymss_weights', 'MSST 权重（完整包从开发机复制）'),
            ):
                gitignore = out_dir / 'assets' / sub / '.gitignore'
                gitignore.write_text('*\n!.gitignore\n!README.txt\n', encoding='utf-8')
                (out_dir / 'assets' / sub / 'README.txt').write_text(hint + '\n', encoding='utf-8')
            stats['skipped'] += 1
            continue
        copy_tree(ROOT / name, out_dir / name, manifest, stats)

    for rel in manifest.get('include_files', []):
        src = ROOT / rel
        if not src.is_file():
            continue
        name = 'DEMO_README.md' if rel.endswith('DEMO_README.md') else Path(rel).name
        dst = out_dir / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        stats['files'] += 1

    (out_dir / 'VERSION').write_text(ver + '\n', encoding='utf-8')
    write_launcher(out_dir)
    (out_dir / 'config' / 'client.json').parent.mkdir(parents=True, exist_ok=True)
    meta = {
        'product': manifest.get('product', 'RVC Client'),
        'version': ver,
        'built_from': str(ROOT),
        'stats': stats,
        'lite': lite,
        'cuda_variant': cuda_variant or None,
    }
    (out_dir / 'packaging' / 'build-info.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print('BUILD OK: %s' % out_dir)
    print('  files=%s  size=%.1f MB  skipped=%s' % (stats['files'], stats['bytes'] / 1048576, stats['skipped']))
    if not (out_dir / 'python' / 'python.exe').is_file():
        print('')
        print('WARNING: 包内无 python/ 运行时，客户机需自备带 PyTorch 的环境。')
        print('  演示发客户请执行: build_demo_package.bat  （含 -CondaPack）')
    return out_dir


def main():
    parser = argparse.ArgumentParser(description='Build RVC client demo package')
    parser.add_argument('--version', default='')
    parser.add_argument('--output', default=str(ROOT / 'dist'))
    parser.add_argument('--lite', action='store_true', help='不复制 assets 大文件，仅目录占位')
    parser.add_argument('--zip', action='store_true')
    parser.add_argument('--cuda-variant', default='', choices=('', 'cu118', 'cu128'))
    args = parser.parse_args()
    manifest = load_manifest()
    ver = args.version or manifest.get('version', '0.1.0-demo')
    out_dir = build(ver, Path(args.output), args.lite, args.cuda_variant)
    if args.zip:
        zip_path = out_dir.parent / ('%s.zip' % out_dir.name)
        if zip_path.exists():
            zip_path.unlink()
        shutil.make_archive(str(out_dir), 'zip', root_dir=out_dir.parent, base_dir=out_dir.name)
        final = out_dir.parent / (out_dir.name + '.zip')
        print('ZIP: %s' % final)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
