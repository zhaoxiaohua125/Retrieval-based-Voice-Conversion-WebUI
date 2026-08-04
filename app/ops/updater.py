import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen


@dataclass(frozen=True)
class VersionInfo:
    latest_version: str
    force_update: bool
    update_desc: str
    full_package_url: str
    patch_url: str
    md_full: str
    md_patch: str


def parse_version_json(data: dict[str, Any]) -> VersionInfo:
    return VersionInfo(
        latest_version=str(data.get('latest_version', '')),
        force_update=bool(data.get('force_update', False)),
        update_desc=str(data.get('update_desc', '')),
        full_package_url=str(data.get('full_package_url', '')),
        patch_url=str(data.get('patch_url', '')),
        md_full=str(data.get('md_full', '')),
        md_patch=str(data.get('md_patch', '')),
    )


def load_version_info(source):
    if isinstance(source, (str, Path)) and Path(source).is_file():
        data = json.loads(Path(source).read_text(encoding='utf-8'))
    elif isinstance(source, str):
        with urlopen(source, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError('unsupported version source: %r' % type(source))
    return parse_version_json(data)


def compare_version(left: str, right: str) -> int:
    def parts(value):
        return [int(x) for x in re.findall(r'\d+', value)]
    lp, rp = parts(left), parts(right)
    length = max(len(lp), len(rp))
    lp.extend([0] * (length - len(lp)))
    rp.extend([0] * (length - len(rp)))
    if lp < rp:
        return -1
    if lp > rp:
        return 1
    return 0


def file_md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_md5(path, expected_md5):
    if not expected_md5:
        return True
    return file_md5(path).lower() == str(expected_md5).lower()


def download_file(url, dest_path, expected_md5=None):
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as resp, open(dest, 'wb') as out:
        shutil.copyfileobj(resp, out)
    if expected_md5 and not verify_md5(dest, expected_md5):
        dest.unlink(missing_ok=True)
        raise ValueError('md5 mismatch for %s' % dest)
    return str(dest.resolve())


def apply_zip_update(zip_path, install_dir, backup_dir=None):
    install = Path(install_dir)
    install.mkdir(parents=True, exist_ok=True)
    backup = Path(backup_dir) if backup_dir else install.parent / 'backup_prev'
    if backup.exists():
        shutil.rmtree(backup)
    if install.exists() and any(install.iterdir()):
        shutil.copytree(install, backup)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(install)
    return str(backup.resolve()) if backup.exists() else ''


def rollback_update(backup_dir, install_dir):
    backup = Path(backup_dir)
    install = Path(install_dir)
    if not backup.is_dir():
        raise FileNotFoundError('backup dir missing: %s' % backup_dir)
    if install.exists():
        shutil.rmtree(install)
    shutil.copytree(backup, install)
    return str(install.resolve())


def check_update(current_version, version_source):
    info = load_version_info(version_source)
    need_update = compare_version(current_version, info.latest_version) < 0
    return info, need_update


def run_update_flow(current_version, version_source, install_dir, use_patch=True):
    info, need_update = check_update(current_version, version_source)
    if not need_update:
        return {'updated': False, 'version': current_version, 'info': info}
    url = info.patch_url if use_patch and info.patch_url else info.full_package_url
    expected_md5 = info.md_patch if use_patch and info.patch_url else info.md_full
    if not url:
        raise ValueError('no update package url in version.json')
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / 'update.zip'
        download_file(url, package, expected_md5)
        backup_dir = apply_zip_update(package, install_dir)
    return {'updated': True, 'version': info.latest_version, 'backup_dir': backup_dir, 'info': info}
