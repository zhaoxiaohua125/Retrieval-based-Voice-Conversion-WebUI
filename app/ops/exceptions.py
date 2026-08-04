import functools
import logging
import traceback
from typing import Callable, TypeVar


F = TypeVar('F', bound=Callable)
logger = logging.getLogger('rvc_client')


def safe_call(func: F = None, *, reraise=False, publish=None) -> F:
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                detail = traceback.format_exc()
                kind = classify_exception(exc)
                if reraise:
                    logger.exception('safe_call caught %s (%s): %s', type(exc).__name__, kind, exc)
                else:
                    logger.warning('safe_call caught %s (%s): %s', type(exc).__name__, kind, exc)
                if publish is not None:
                    try:
                        publish(exc, detail)
                    except Exception:
                        logger.exception('safe_call publish failed')
                if reraise:
                    raise
                return None
        return wrapper
    if func is not None:
        return decorator(func)
    return decorator


def classify_exception(exc: BaseException) -> str:
    name = type(exc).__name__
    module = type(exc).__module__ or ''
    text = str(exc).lower()
    if module.startswith('torch') or 'cuda' in name.lower() or 'cuda' in text:
        return 'cuda'
    if 'sounddevice' in module or 'portaudio' in text or 'audio' in text:
        return 'audio'
    return 'python'
