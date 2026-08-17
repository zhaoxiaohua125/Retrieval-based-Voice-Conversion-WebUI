import logging
import re
import sys
from datetime import datetime
from pathlib import Path

LOG_TS_FMT = '%Y-%m-%d %H:%M:%S'
LOG_DAY_FMT = '%Y-%m-%d'
_DAY_DIR_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_LOG_STEMS = ('client', 'startup', 'crash', 'stderr', 'stdout')


def log_day() -> str:
    return datetime.now().strftime(LOG_DAY_FMT)


def is_day_dir(name: str) -> bool:
    return bool(_DAY_DIR_RE.match(name or ''))


def daily_log_dir(base_log_dir='logs/client', day: str | None = None) -> Path:
    p = Path(base_log_dir) / (day or log_day())
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_file_path(base_log_dir, stem: str, day: str | None = None) -> Path:
    return daily_log_dir(base_log_dir, day) / ('%s.log' % stem)


def dated_log_path(base_log_dir, stem: str) -> Path:
    return log_file_path(base_log_dir, stem)


def append_dated_line(base_log_dir, stem: str, msg: str):
    path = log_file_path(base_log_dir, stem)
    with open(path, 'a', encoding='utf-8') as f:
        f.write('%s | %s\n' % (datetime.now().strftime(LOG_TS_FMT), msg))
        f.flush()


def iter_daily_log_dirs(base_log_dir) -> list[Path]:
    p = Path(base_log_dir)
    if not p.is_dir():
        return []
    return sorted([d for d in p.iterdir() if d.is_dir() and is_day_dir(d.name)], key=lambda x: x.name, reverse=True)


def iter_named_logs(base_log_dir, stem: str) -> list[Path]:
    out = []
    for day_dir in iter_daily_log_dirs(base_log_dir):
        f = day_dir / ('%s.log' % stem)
        if f.is_file():
            out.append(f)
    flat = Path(base_log_dir)
    if flat.is_dir():
        out.extend([x for x in flat.glob('%s-*.log' % stem) if x.is_file()])
        legacy = flat / ('%s.log' % stem)
        if legacy.is_file():
            out.append(legacy)
    return sorted(set(out), key=lambda x: (x.stat().st_mtime, str(x)), reverse=True)


def iter_client_logs(base_log_dir) -> list[Path]:
    return iter_named_logs(base_log_dir, 'client')


def iter_all_log_files(base_log_dir) -> list[Path]:
    out = []
    for stem in _LOG_STEMS:
        out.extend(iter_named_logs(base_log_dir, stem))
    return sorted(set(out), key=lambda x: (x.stat().st_mtime, str(x)), reverse=True)


class TimestampedLogWriter:
    """faulthandler 等直写文件的包装：Python write 时前缀时间戳；fileno 供 C 层直写。"""

    def __init__(self, path: Path):
        self._f = open(path, 'a', encoding='utf-8', buffering=1)

    def write(self, s):
        if not s:
            return
        ts = datetime.now().strftime(LOG_TS_FMT)
        self._f.write('%s\n%s' % (ts, s))
        if not s.endswith('\n'):
            self._f.write('\n')

    def flush(self):
        self._f.flush()

    def fileno(self):
        return self._f.fileno()

    def close(self):
        self._f.close()


def setup_rotating_logging(
    log_dir='logs/client',
    console_level=logging.INFO,
    max_bytes=5 * 1024 * 1024,
    backup_count=10,
    name='rvc_client',
):
    logger = logging.getLogger(name)
    fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt=LOG_TS_FMT)
    if not getattr(logger, '_ops_rotating_configured', False):
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        if sys.stderr is not None:
            console = logging.StreamHandler(sys.stderr)
            console.setLevel(console_level)
            console.setFormatter(fmt)
            logger.addHandler(console)
        logger._ops_rotating_configured = True
    log_path = log_file_path(log_dir, 'client')
    for handler in logger.handlers[:]:
        if getattr(handler, '_ops_daily_file', False):
            logger.removeHandler(handler)
            handler.close()
    file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
    file_handler._ops_daily_file = True
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger._ops_file_handler = file_handler
    return logger
