from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2]
_VERSION_FILE = _PKG_ROOT / 'VERSION'


def get_client_version() -> str:
    if _VERSION_FILE.is_file():
        return _VERSION_FILE.read_text(encoding='utf-8').strip() or '0.1.0-dev'
    return '0.1.0-dev'


CLIENT_VERSION = get_client_version()
