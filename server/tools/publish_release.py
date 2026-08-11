#!/usr/bin/env python3
"""将 zip 更新包写入 server/data/releases 并刷新 version.json。"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
DATA = SERVER_ROOT / 'data'
RELEASES = DATA / 'releases'


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description='发布客户端更新包到本地更新服务器')
    parser.add_argument('zip_path', help='更新包 zip 路径')
    parser.add_argument('--version', required=True, help='新版本号，如 1.0.2')
    parser.add_argument('--desc', default='', help='更新说明')
    parser.add_argument('--base-url', default='http://127.0.0.1:8765', help='服务根 URL')
    parser.add_argument('--force', action='store_true', help='强制更新')
    parser.add_argument('--name', default='update.zip', help='releases 目录内文件名')
    parser.add_argument('--patch', default='', help='增量包路径（可选）')
    args = parser.parse_args()
    src = Path(args.zip_path)
    if not src.is_file():
        print('zip not found:', src, file=sys.stderr)
        return 1
    RELEASES.mkdir(parents=True, exist_ok=True)
    dest = RELEASES / args.name
    shutil.copy2(src, dest)
    md_full = file_md5(dest)
    base = args.base_url.rstrip('/')
    manifest = {
        'latest_version': args.version,
        'force_update': bool(args.force),
        'update_desc': args.desc,
        'full_package_url': '%s/releases/%s' % (base, dest.name),
        'patch_url': '',
        'md_full': md_full,
        'md_patch': '',
    }
    if args.patch:
        patch_src = Path(args.patch)
        if not patch_src.is_file():
            print('patch not found:', patch_src, file=sys.stderr)
            return 1
        patch_name = 'patch-%s.zip' % args.version
        patch_dest = RELEASES / patch_name
        shutil.copy2(patch_src, patch_dest)
        manifest['patch_url'] = '%s/releases/%s' % (base, patch_name)
        manifest['md_patch'] = file_md5(patch_dest)
    out = DATA / 'version.json'
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('published', args.version, '->', out)
    print('full:', manifest['full_package_url'], 'md5:', md_full)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
