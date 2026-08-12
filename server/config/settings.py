"""服务配置：优先读 config/db.json，其次环境变量。"""

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
DB_JSON = ROOT / 'config' / 'db.json'
DB_JSON_EXAMPLE = ROOT / 'config' / 'db.json.example'


def _resolve_db_json() -> Path | None:
    if DB_JSON.is_file():
        return DB_JSON
    if DB_JSON_EXAMPLE.is_file():
        return DB_JSON_EXAMPLE
    return None


@dataclass(frozen=True)
class DbSettings:
    host: str = '127.0.0.1'
    port: int = 13306
    user: str = 'root'
    password: str = '2020@Wkrj+-'
    database: str = 'aisound'
    charset: str = 'utf8mb4'
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 3600

    @property
    def sqlalchemy_url(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f'mysql+pymysql://{user}:{password}@{self.host}:{self.port}/{self.database}'
            f'?charset={self.charset}'
        )


@dataclass(frozen=True)
class AppSettings:
    db: DbSettings
    auth_token_ttl_sec: int = 86400


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_db_settings() -> DbSettings:
    data = {}
    cfg = _resolve_db_json()
    if cfg is not None:
        try:
            data = json.loads(cfg.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            data = {}
    host = str(data.get('host') or os.environ.get('MYSQL_HOST') or '127.0.0.1')
    if host.lower() == 'localhost':
        host = '127.0.0.1'
    return DbSettings(
        host=host,
        port=int(data.get('port') or _env_int('MYSQL_PORT', 13306)),
        user=str(data.get('user') or os.environ.get('MYSQL_USER') or 'root'),
        password=str(data.get('password') or os.environ.get('MYSQL_PASSWORD') or '2020@Wkrj+-'),
        database=str(data.get('database') or os.environ.get('MYSQL_DATABASE') or 'aisound'),
        charset=str(data.get('charset') or os.environ.get('MYSQL_CHARSET') or 'utf8mb4'),
        pool_size=int(data.get('pool_size') or _env_int('MYSQL_POOL_SIZE', 5)),
        max_overflow=int(data.get('max_overflow') or _env_int('MYSQL_MAX_OVERFLOW', 10)),
        pool_recycle=int(data.get('pool_recycle') or _env_int('MYSQL_POOL_RECYCLE', 3600)),
    )


@lru_cache
def load_settings() -> AppSettings:
    return AppSettings(db=_load_db_settings())


def get_settings() -> AppSettings:
    return load_settings()
