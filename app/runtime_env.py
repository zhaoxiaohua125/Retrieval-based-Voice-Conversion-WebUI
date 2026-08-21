"""客户端运行时环境：内置 FFmpeg 等，免用户配置 PATH。"""

import os
import sys
from pathlib import Path

from tools.win_subprocess import patch_module as _patch_subprocess_no_console
def _prepend_path_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    text = str(path.resolve())
    parts = os.environ.get('PATH', '').split(os.pathsep)
    if parts and parts[0].lower() == text.lower():
        return True
    os.environ['PATH'] = text + os.pathsep + os.environ.get('PATH', '')
    return True


def bootstrap_runtime(project_root=None) -> dict:
    """启动最早调用：把 tools/ffmpeg 加入 PATH，供 subprocess / ffmpeg-python 使用。"""
    _patch_subprocess_no_console()
    # 国内环境下载 Whisper 模型常用镜像（已设置则不覆盖）
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    root = Path(project_root or Path.cwd()).resolve()
    ffmpeg_dir = root / 'tools' / 'ffmpeg'
    ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
    ffprobe_exe = ffmpeg_dir / 'ffprobe.exe'
    info = {'ffmpeg_dir': str(ffmpeg_dir), 'ffmpeg': None, 'ffprobe': None, 'path_updated': False}

    if ffmpeg_exe.is_file():
        info['ffmpeg'] = str(ffmpeg_exe)
        os.environ.setdefault('FFMPEG_BINARY', str(ffmpeg_exe))
        if ffprobe_exe.is_file():
            info['ffprobe'] = str(ffprobe_exe)
            os.environ.setdefault('FFPROBE_BINARY', str(ffprobe_exe))
        info['path_updated'] = _prepend_path_dir(ffmpeg_dir)
    elif (root / 'ffmpeg.exe').is_file():
        legacy = root / 'ffmpeg.exe'
        info['ffmpeg'] = str(legacy)
        os.environ.setdefault('FFMPEG_BINARY', str(legacy))
        info['path_updated'] = _prepend_path_dir(root)

    if info['path_updated'] and hasattr(os, 'add_dll_directory') and ffmpeg_dir.is_dir():
        try:
            os.add_dll_directory(str(ffmpeg_dir))
        except OSError:
            pass
    return info


def ensure_ffmpeg(project_root=None) -> str:
    """返回可用 ffmpeg 可执行文件路径；找不到则返回 'ffmpeg'（依赖系统 PATH）。"""
    root = Path(project_root or Path.cwd()).resolve()
    for candidate in (root / 'tools' / 'ffmpeg' / 'ffmpeg.exe', root / 'ffmpeg.exe'):
        if candidate.is_file():
            return str(candidate)
    return 'ffmpeg'
