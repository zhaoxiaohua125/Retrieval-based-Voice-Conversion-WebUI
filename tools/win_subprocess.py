"""Windows 子进程启动参数：避免 GUI 主程序 spawn 时闪 CMD。"""
import os
import subprocess
import sys

_PATCHED = False


def spawn_kwargs():
    if os.name != 'nt':
        return {}
    kw = {}
    flag = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if flag:
        kw['creationflags'] = flag
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    kw['startupinfo'] = si
    return kw


def patch_module():
    global _PATCHED
    if _PATCHED or sys.platform != 'win32':
        return
    flag = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if not flag:
        return
    _run = subprocess.run
    _OrigPopen = subprocess.Popen
    _si = spawn_kwargs().get('startupinfo')

    def _apply(kwargs):
        if kwargs.get('shell'):
            return
        cf = kwargs.get('creationflags')
        kwargs['creationflags'] = (cf | flag) if cf is not None else flag
        if _si is not None and kwargs.get('startupinfo') is None:
            kwargs['startupinfo'] = _si

    def run(*args, **kwargs):
        _apply(kwargs)
        return _run(*args, **kwargs)

    class _NoConsolePopen(_OrigPopen):
        def __init__(self, *args, **kwargs):
            _apply(kwargs)
            super().__init__(*args, **kwargs)

    subprocess.run = run
    subprocess.Popen = _NoConsolePopen
    _PATCHED = True
