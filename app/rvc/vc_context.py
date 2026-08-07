"""RVC 推理上下文加载（按需导入上游 infer/vc，避免 argv 冲突）。"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_rvc_runtime_env(project_root=None):
    """初始化 RVC WebUI 依赖的环境变量（与 webui.py 默认值一致）。"""
    root = Path(project_root or PROJECT_ROOT)
    temp_dir = root / 'TEMP'
    temp_dir.mkdir(parents=True, exist_ok=True)
    defaults = {
        'OPENBLAS_NUM_THREADS': '1',
        'weight_root': str(root / 'assets' / 'weights'),
        'weight_pymss_root': str(root / 'assets' / 'pymss_weights'),
        'index_root': str(root / 'logs'),
        'outside_index_root': str(root / 'assets' / 'indices'),
        'rmvpe_root': str(root / 'assets' / 'rmvpe'),
        'TEMP': str(temp_dir),
        'RVC_CUDA_GRAPH': os.environ.get('RVC_CUDA_GRAPH', '0'),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    return defaults


@contextmanager
def upstream_import_context(project_root=None):
    """导入 tools/infer 上游模块前：env + 项目根 cwd + 清理 argv（i18n 等依赖 ./ 相对路径）。"""
    root = Path(project_root or PROJECT_ROOT)
    ensure_rvc_runtime_env(root)
    argv_backup = sys.argv[:]
    cwd_backup = os.getcwd()
    try:
        sys.argv = [argv_backup[0]]
        os.chdir(root)
        yield root
    finally:
        os.chdir(cwd_backup)
        sys.argv = argv_backup


def _with_clean_argv(func):
    """临时清空 sys.argv，避免 Config() 解析客户端 CLI 参数。"""

    def wrapper(*args, **kwargs):
        with upstream_import_context(kwargs.get('project_root')):
            return func(*args, **kwargs)

    return wrapper


@_with_clean_argv
def create_vc(project_root=None):
    """创建 VC 实例（尚未加载具体 .pth 模型）。"""
    ensure_rvc_runtime_env(project_root)
    from configs.config import Config
    from infer.vc.modules import VC

    config = Config()
    return VC(config), config


@_with_clean_argv
def load_voice_model(vc, model_sid, project_root=None):
    """加载 RVC 模型；model_sid 为 weights 目录下的文件名（如 xxx.pth）。"""
    env = ensure_rvc_runtime_env(project_root)
    if not model_sid:
        raise ValueError('model_sid is required')
    model_path = Path(env['weight_root']) / model_sid
    if not model_path.is_file():
        raise FileNotFoundError('RVC 模型不存在: %s' % model_path)
    vc.get_vc(model_sid)
    if vc.net_g is None:
        raise RuntimeError('failed to load rvc model: %s' % model_sid)
    return vc


def discover_first_model(weight_root=None, project_root=None):
    """在 assets/weights 中查找第一个 .pth 模型文件名。"""
    env = ensure_rvc_runtime_env(project_root)
    root = Path(weight_root) if weight_root else Path(env['weight_root'])
    if not root.is_dir():
        return None
    for path in sorted(root.glob('*.pth')):
        return path.name
    return None


def resolve_index_for_model(model_sid, project_root=None):
    """按 RVC 规则搜索 index 文件（轻量实现，不导入 torch/hubert）。"""
    from app.rvc.index_lookup import find_index_for_model_project
    ensure_rvc_runtime_env(project_root)
    return find_index_for_model_project(model_sid, project_root=project_root) or ''
