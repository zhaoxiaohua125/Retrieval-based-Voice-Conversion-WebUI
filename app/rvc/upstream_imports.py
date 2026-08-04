"""上游 tools 模块的按需导入（导入前清理 sys.argv，避免 Config 解析 CLI 冲突）。"""

import sys


def _with_clean_argv(callback):
    argv_backup = sys.argv[:]
    try:
        sys.argv = [argv_backup[0]]
        return callback()
    finally:
        sys.argv = argv_backup


def song_cover_tools():
    """返回 song_cover 中的 GPU 释放与混音工具函数。"""

    def _import():
        from tools.song_cover import (
            _release_vc_gpu,
            _restore_vc_gpu,
            _to_float_audio,
            mix_vocal_instrumental,
        )
        return _release_vc_gpu, _restore_vc_gpu, _to_float_audio, mix_vocal_instrumental

    return _with_clean_argv(_import)


def pymss_write_audio():
    """返回 pymss_webui._write_audio。"""

    def _import():
        from tools.pymss_webui import _write_audio
        return _write_audio

    return _with_clean_argv(_import)
