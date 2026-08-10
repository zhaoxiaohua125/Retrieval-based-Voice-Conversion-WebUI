import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_rotating_logging(
    log_dir='logs/client',
    console_level=logging.INFO,
    max_bytes=5 * 1024 * 1024,
    backup_count=10,
    name='rvc_client',
):
    logger = logging.getLogger(name)
    fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt='%H:%M:%S')
    if not getattr(logger, '_ops_rotating_configured', False):
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        if sys.stderr is not None:
            console = logging.StreamHandler(sys.stderr)
            console.setLevel(console_level)
            console.setFormatter(fmt)
            logger.addHandler(console)
        logger._ops_rotating_configured = True
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    log_path = path / 'client.log'
    for handler in logger.handlers[:]:
        if isinstance(handler, RotatingFileHandler):
            logger.removeHandler(handler)
            handler.close()
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger._ops_file_handler = file_handler
    return logger
