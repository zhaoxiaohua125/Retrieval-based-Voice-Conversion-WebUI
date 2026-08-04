import gzip
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


class _AppLogFormatter(logging.Formatter):
    LEVEL_MAP = {'DEBUG': 'DBG', 'INFO': 'INF', 'WARNING': 'WAR', 'ERROR': 'ERR', 'CRITICAL': 'CRI'}

    def format(self, record):
        original = record.levelname
        record.levelname = self.LEVEL_MAP.get(record.levelname, record.levelname[:3])
        try:
            return super().format(record)
        finally:
            record.levelname = original


def _rotate_logs(log_dir, max_log):
    try:
        files = sorted(
            [p for p in Path(log_dir).glob('*.log') if p.is_file()],
            key=lambda p: p.stat().st_mtime,
        )
    except OSError:
        return
    while len(files) > max_log:
        oldest = files.pop(0)
        gz = oldest.with_suffix('.log.gz')
        if gz.exists():
            oldest.unlink(missing_ok=True)
            continue
        try:
            with open(oldest, 'rb') as src, gzip.open(gz, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            oldest.unlink()
        except OSError:
            pass


def setup_app_logging(log_dir='logs/client', console_level=logging.INFO, enable_file=True, max_log=50, name='rvc_client'):
    logger = logging.getLogger(name)
    if getattr(logger, '_app_configured', False):
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr:
                handler.setLevel(console_level)
        return logger
    fmt = _AppLogFormatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt='%H:%M:%S')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(fmt)
    logger.addHandler(console)
    if enable_file:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path / 'client.log', mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        _rotate_logs(path, max_log)
    logger._app_configured = True
    return logger
