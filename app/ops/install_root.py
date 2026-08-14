"""客户端安装根目录与重启。"""

import subprocess
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2]


def get_install_root(project_root=None) -> Path:
    root = Path(project_root or _PKG_ROOT).resolve()
    return root


def is_packaged_install(root: Path | None = None) -> bool:
    root = get_install_root(root)
    return (root / 'VERSION').is_file()


def find_launcher(project_root=None) -> str:
    root = get_install_root(project_root)
    for name in ('启动声迹客户端.bat', '启动来趣文化.bat', '启动来取文化.bat'):
        p = root / name
        if p.is_file():
            return str(p)
    for p in sorted(root.glob('*.bat')):
        if '启动' in p.name:
            return str(p)
    script = root / 'scripts' / 'run_ui_skeleton.py'
    if script.is_file():
        return str(script)
    raise FileNotFoundError('未找到启动脚本: %s' % root)


def relaunch_client(project_root=None):
    root = get_install_root(project_root)
    launcher = find_launcher(root)
    path = Path(launcher)
    if path.suffix.lower() == '.bat':
        subprocess.Popen(f'start "" "{path}"', shell=True, cwd=str(root))
        return str(path)
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen([sys.executable, str(path)], cwd=str(root), creationflags=flags)
    return str(path)
