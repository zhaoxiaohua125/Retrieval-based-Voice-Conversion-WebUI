"""安全更新：进程内只下载；退出后由独立脚本覆盖文件并重启（避开 .pyd 占用）。"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.ops.install_root import find_launcher, get_install_root

_APPLY_SCRIPT = r'''# -*- coding: utf-8 -*-
import os, shutil, subprocess, sys, time, zipfile
from pathlib import Path

def wait_pid(pid, timeout=180):
    pid = int(pid)
    if pid <= 0:
        return
    deadline = time.time() + timeout
    if sys.platform == 'win32':
        import ctypes
        SYNCHRONIZE = 0x00100000
        h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if h:
            ctypes.windll.kernel32.WaitForSingleObject(h, int(max(1, deadline - time.time()) * 1000))
            ctypes.windll.kernel32.CloseHandle(h)
            time.sleep(1.0)
            return
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            time.sleep(1.0)
            return
        time.sleep(0.4)
    time.sleep(1.0)

def apply_zip(zip_path, install_dir, backup_dir):
    install = Path(install_dir)
    backup = Path(backup_dir)
    install.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    if install.exists() and any(install.iterdir()):
        shutil.copytree(install, backup)
    last = None
    for i in range(10):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(install)
            return
        except (PermissionError, OSError) as exc:
            last = exc
            time.sleep(0.4 * (i + 1))
    raise last

def relaunch(install_dir):
    root = Path(install_dir)
    for name in ('启动声迹客户端.bat', '启动来趣文化.bat', '启动来取文化.bat'):
        bat = root / name
        if bat.is_file():
            subprocess.Popen('start "" "%s"' % bat, shell=True, cwd=str(root))
            return
    for bat in sorted(root.glob('*.bat')):
        if '启动' in bat.name:
            subprocess.Popen('start "" "%s"' % bat, shell=True, cwd=str(root))
            return
    script = root / 'scripts' / 'run_ui_skeleton.py'
    if script.is_file():
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen([sys.executable, str(script)], cwd=str(root), creationflags=flags)
        return
    raise FileNotFoundError('launcher missing')

def main():
    if len(sys.argv) < 6:
        raise SystemExit('usage: apply_update.py pid zip install backup version')
    pid, zip_path, install_dir, backup_dir, version = sys.argv[1:6]
    staging = Path(zip_path).parent
    err_file = staging / 'update_error.txt'
    try:
        wait_pid(pid)
        apply_zip(zip_path, install_dir, backup_dir)
        ver = Path(install_dir) / 'VERSION'
        ver.write_text(str(version).strip() + '\n', encoding='utf-8')
        if err_file.is_file():
            err_file.unlink(missing_ok=True)
    except Exception as exc:
        err_file.write_text(str(exc), encoding='utf-8')
    try:
        relaunch(install_dir)
    except Exception as exc:
        err_file.write_text((err_file.read_text(encoding='utf-8') if err_file.is_file() else '') + '\nrelaunch: ' + str(exc), encoding='utf-8')

if __name__ == '__main__':
    main()
'''


def staging_dir(project_root=None) -> Path:
    root = get_install_root(project_root)
    path = Path(tempfile.gettempdir()) / ('rvc-client-update-' + root.name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def launch_deferred_apply(zip_path, install_dir, version, wait_pid=None, backup_dir=None) -> dict:
    """启动独立进程：等待本进程退出后覆盖安装目录并重启。"""
    install = Path(install_dir).resolve()
    zip_path = Path(zip_path).resolve()
    staging = zip_path.parent
    script = staging / 'apply_update.py'
    script.write_text(_APPLY_SCRIPT, encoding='utf-8')
    backup = Path(backup_dir) if backup_dir else install.parent / ('backup_prev_' + install.name)
    pid = int(wait_pid if wait_pid is not None else os.getpid())
    cmd = [sys.executable, str(script), str(pid), str(zip_path), str(install), str(backup), str(version)]
    flags = 0
    if sys.platform == 'win32':
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(
        cmd,
        cwd=str(staging),
        creationflags=flags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    launcher = ''
    try:
        launcher = find_launcher(install)
    except FileNotFoundError:
        pass
    return {
        'script': str(script),
        'zip_path': str(zip_path),
        'backup_dir': str(backup),
        'wait_pid': pid,
        'launcher': launcher,
    }
