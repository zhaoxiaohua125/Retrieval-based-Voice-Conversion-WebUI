"""上游 tools 模块的按需导入（导入前切换项目根 cwd，避免 i18n 相对路径失败）。"""

from app.rvc.vc_context import upstream_import_context


def song_cover_tools():
    """返回 song_cover 中的 GPU 释放与混音工具函数。"""

    with upstream_import_context():
        from tools.song_cover import (
            _release_vc_gpu,
            _restore_vc_gpu,
            _to_float_audio,
            mix_vocal_instrumental,
        )
        return _release_vc_gpu, _restore_vc_gpu, _to_float_audio, mix_vocal_instrumental


def pymss_write_audio():
    """返回 pymss_webui._write_audio。"""

    with upstream_import_context():
        from tools.pymss_webui import _write_audio
        return _write_audio
