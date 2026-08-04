"""RVC 推理内核（离线 + 实时）。"""

from app.rvc.types import OfflineCoverResult, RvcInferParams

__all__ = [
    'OfflineCoverResult',
    'OfflineSongPipeline',
    'RealtimeModelPool',
    'RealtimeRvcConfig',
    'RealtimeRvcEngine',
    'RealtimeRvcService',
    'RvcInferParams',
    'create_vc',
    'discover_first_model',
    'load_voice_model',
    'resolve_index_for_model',
]

_LAZY = {
    'OfflineSongPipeline': ('app.rvc.offline_pipeline', 'OfflineSongPipeline'),
    'RealtimeRvcConfig': ('app.rvc.realtime_config', 'RealtimeRvcConfig'),
    'RealtimeRvcEngine': ('app.rvc.realtime_engine', 'RealtimeRvcEngine'),
    'RealtimeModelPool': ('app.rvc.realtime_engine', 'RealtimeModelPool'),
    'RealtimeRvcService': ('app.rvc.realtime_service', 'RealtimeRvcService'),
    'create_vc': ('app.rvc.vc_context', 'create_vc'),
    'discover_first_model': ('app.rvc.vc_context', 'discover_first_model'),
    'load_voice_model': ('app.rvc.vc_context', 'load_voice_model'),
    'resolve_index_for_model': ('app.rvc.vc_context', 'resolve_index_for_model'),
}


def __getattr__(name):
    if name not in _LAZY:
        raise AttributeError('module %r has no attribute %r' % (__name__, name))
    import importlib
    module_name, attr = _LAZY[name]
    return getattr(importlib.import_module(module_name), attr)
