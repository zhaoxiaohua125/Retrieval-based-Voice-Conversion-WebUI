"""崩溃/异常退出日志打包与自动上报。"""

import logging
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from app.ops.hardware import collect_environment_info
from app.ops.log_bundle import bundle_log_files
from app.ops.log_reporter import upload_log_bundle
from app.ops.version import CLIENT_VERSION

logger = logging.getLogger('rvc_client.crash')
_CLEAN_MARKER = '.last_exit_clean'


def resolve_log_upload_url(config) -> str:
    explicit = str(_cfg_get(config, 'logs.upload_url', '') or '').strip()
    if explicit:
        return explicit
    check = str(_cfg_get(config, 'update.check_url', '') or '').strip()
    if not check:
        return ''
    parsed = urlparse(check)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return urljoin('%s://%s/' % (parsed.scheme, parsed.netloc), 'api/logs/upload')


def _cfg_get(config, key, default=None):
    if hasattr(config, 'get'):
        return config.get(key, default)
    if isinstance(config, dict):
        node = config
        for part in str(key).split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node
    return default


def _log_dir(project_root, config) -> Path:
    rel = str(_cfg_get(config, 'paths.log_dir', 'logs/client') or 'logs/client').strip()
    return (Path(project_root) / rel).resolve()


def _extra_log_files(log_dir: Path) -> list:
    return [str(log_dir / n) for n in ('crash.log', 'stderr.log', 'stdout.log', 'startup.log') if (log_dir / n).is_file()]


def _has_log_content(log_dir: Path) -> bool:
    for name in ('crash.log', 'stderr.log', 'startup.log'):
        p = log_dir / name
        if p.is_file() and p.stat().st_size > 0:
            return True
    for p in log_dir.glob('client.log*'):
        if p.is_file() and p.stat().st_size > 0:
            return True
    return False


def mark_clean_exit(project_root, config):
    log_dir = _log_dir(project_root, config)
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / _CLEAN_MARKER).write_text(datetime.now().isoformat() + '\n', encoding='utf-8')


def upload_crash_logs(project_root, config, reason: str = 'crash', detail: str = '', sync: bool = False):
    if not bool(_cfg_get(config, 'logs.auto_upload_crash', True)):
        return
    url = resolve_log_upload_url(config)
    if not url:
        return

    def _work():
        try:
            log_dir = _log_dir(project_root, config)
            env = collect_environment_info()
            env['report_reason'] = reason
            env['report_time'] = datetime.now().isoformat()
            if detail:
                env['report_detail'] = detail[:8000]
            with tempfile.TemporaryDirectory(prefix='rvc-crash-') as tmp:
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                ver = str(env.get('client_version') or CLIENT_VERSION).replace('/', '_')
                zip_path = Path(tmp) / ('crash-%s-%s.zip' % (ver, stamp))
                bundle_log_files(log_dir, zip_path, extra_files=_extra_log_files(log_dir), env_info=env)
                upload_log_bundle(url, zip_path, env_info=env)
            logger.info('crash log uploaded (%s) -> %s', reason, url)
        except Exception:
            logger.warning('crash log upload failed:\n%s', traceback.format_exc())

    if sync:
        _work()
    else:
        threading.Thread(target=_work, name='crash-log-upload', daemon=True).start()


def startup_crash_check(project_root, config):
    log_dir = _log_dir(project_root, config)
    dirty = not (log_dir / _CLEAN_MARKER).is_file()
    (log_dir / _CLEAN_MARKER).unlink(missing_ok=True)
    if dirty and _has_log_content(log_dir):
        upload_crash_logs(project_root, config, reason='abnormal_exit')


def install_crash_hooks(project_root, config):
    import sys

    _orig_sys = sys.excepthook
    _orig_thread = threading.excepthook

    def _sys_hook(exc_type, exc, tb):
        detail = ''.join(traceback.format_exception(exc_type, exc, tb))
        logging.getLogger('rvc_client').error('uncaught exception:\n%s', detail)
        upload_crash_logs(project_root, config, reason='uncaught_exception', detail=detail, sync=True)
        if callable(_orig_sys) and _orig_sys is not _sys_hook:
            _orig_sys(exc_type, exc, tb)
        else:
            sys.__excepthook__(exc_type, exc, tb)

    def _thread_hook(args):
        detail = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        logging.getLogger('rvc_client').error('uncaught thread exception in %s:\n%s', args.thread, detail)
        upload_crash_logs(project_root, config, reason='thread_exception', detail=detail)
        if callable(_orig_thread):
            _orig_thread(args)

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
