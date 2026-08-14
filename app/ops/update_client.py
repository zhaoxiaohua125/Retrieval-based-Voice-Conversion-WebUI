"""客户端自动更新：检查 / 下载 / 退出后安全覆盖 / 跳过版本。"""

import logging
import os
import traceback
from pathlib import Path

from app.ops.install_root import get_install_root
from app.ops.safe_updater import launch_deferred_apply, staging_dir
from app.ops.updater import check_update, download_file
from app.ops.version import CLIENT_VERSION

logger = logging.getLogger('rvc_client.update')


class UpdateClient:
    def __init__(self, config_store, project_root=None):
        self.config_store = config_store
        self.root = get_install_root(project_root)

    def check_url(self) -> str:
        return str(self.config_store.get('update.check_url', '') or '').strip()

    def check(self) -> dict:
        url = self.check_url()
        if not url:
            return {'ok': False, 'error': '未配置 update.check_url'}
        try:
            info, need = check_update(CLIENT_VERSION, url)
            skip = str(self.config_store.get('update.skip_version', '') or '').strip()
            if need and skip and info.latest_version == skip:
                need = False
            return {
                'ok': True,
                'current_version': CLIENT_VERSION,
                'latest_version': info.latest_version,
                'need_update': need,
                'force_update': info.force_update,
                'update_desc': info.update_desc,
                'full_package_url': info.full_package_url,
                'patch_url': info.patch_url,
            }
        except Exception as exc:
            logger.error('update check failed:\n%s', traceback.format_exc())
            return {'ok': False, 'error': str(exc)}

    def skip_version(self, version: str):
        self.config_store.set('update.skip_version', str(version or '').strip())
        try:
            self.config_store.save()
        except OSError as exc:
            logger.warning('skip_version save failed: %s', exc)

    def apply(self, use_patch: bool = True, on_progress=None) -> dict:
        url = self.check_url()
        if not url:
            return {'ok': False, 'error': '未配置 update.check_url'}

        def _progress(ratio: float, msg: str = ''):
            if on_progress:
                on_progress(float(ratio or 0), msg or '下载更新包…')

        try:
            info, need = check_update(CLIENT_VERSION, url)
            if not need:
                return {'ok': True, 'updated': False, 'version': CLIENT_VERSION}
            pkg_url = info.patch_url if use_patch and info.patch_url else info.full_package_url
            expected_md5 = info.md_patch if use_patch and info.patch_url else info.md_full
            if not pkg_url:
                return {'ok': False, 'error': 'version.json 未提供更新包地址'}
            stage = staging_dir(self.root)
            package = stage / 'update.zip'
            if package.is_file():
                package.unlink(missing_ok=True)
            download_file(pkg_url, package, expected_md5 or None, on_progress=_progress)
            if on_progress:
                on_progress(0.96, '准备退出并安装更新…')
            backup_dir = self.root.parent / ('backup_prev_' + self.root.name)
            deferred = launch_deferred_apply(
                package, self.root, info.latest_version, wait_pid=os.getpid(), backup_dir=backup_dir,
            )
            self.config_store.set('update.backup_dir', deferred.get('backup_dir') or '')
            self.config_store.set('update.pending_version', info.latest_version)
            try:
                self.config_store.save()
            except OSError:
                pass
            return {
                'ok': True,
                'updated': True,
                'pending_apply': True,
                'version': info.latest_version,
                'backup_dir': deferred.get('backup_dir'),
                'install_dir': str(self.root),
                'staging_zip': str(package),
            }
        except Exception as exc:
            logger.error('update apply failed:\n%s', traceback.format_exc())
            return {'ok': False, 'error': str(exc)}
