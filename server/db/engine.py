"""SQLAlchemy QueuePool 连接池（成熟、广泛使用）。"""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config.settings import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    db = get_settings().db
    _engine = create_engine(
        db.sqlalchemy_url,
        poolclass=QueuePool,
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_pre_ping=True,
        pool_recycle=db.pool_recycle,
        future=True,
    )
    _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


@contextmanager
def session_scope():
    factory = _session_factory or sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_db() -> bool:
    ok, _ = ping_db_detail()
    return ok


def ping_db_detail() -> tuple[bool, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text('SELECT 1'))
        return True, ''
    except Exception as exc:
        return False, str(exc)


def close_db():
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
