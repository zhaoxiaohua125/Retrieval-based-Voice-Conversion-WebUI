"""RVC 离线推理内核（客户端封装层）。"""

from app.rvc.offline_pipeline import OfflineSongPipeline
from app.rvc.types import OfflineCoverResult, RvcInferParams
from app.rvc.vc_context import create_vc, discover_first_model, load_voice_model, resolve_index_for_model

__all__ = [
    'OfflineCoverResult',
    'OfflineSongPipeline',
    'RvcInferParams',
    'create_vc',
    'discover_first_model',
    'load_voice_model',
    'resolve_index_for_model',
]
