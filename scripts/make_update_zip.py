#!/usr/bin/env python3
"""按 Git 提交范围自动生成客户端增量更新 zip（可选发布到 server）。"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from build_client_package import is_client_release_path, load_manifest  # noqa: E402

UPDATE_SKIP_PREFIXES = (
    'server/',
    'manage/',
    '.git/',
    '.github/',
    'dist/',
    'logs/',
    'TEMP/',
    'agent-transcripts/',
    '.cursor/',
)


def _run_git(*args: str, cwd: Path | None = None) -> str:
    cmd = ['git', '-C', str(cwd or ROOT), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip()
        raise RuntimeError('git %s 失败: %s' % (' '.join(args), err or proc.returncode))
    return proc.stdout


def resolve_ref(ref: str) -> str:
    ref = str(ref or '').strip()
    if not ref:
        raise ValueError('空的 git 引用')
    return _run_git('rev-parse', '--verify', '%s^{commit}' % ref).strip()


def changed_files(since: str, to: str = 'HEAD', include_worktree: bool = False) -> list[str]:
    since_sha = resolve_ref(since)
    to_sha = resolve_ref(to)
    out = _run_git('diff', '--name-only', '--diff-filter=ACMRT', '%s..%s' % (since_sha, to_sha))
    files = [ln.strip().replace('\\', '/') for ln in out.splitlines() if ln.strip()]
    if include_worktree:
        wt = _run_git('diff', '--name-only', '--diff-filter=ACMRT', to_sha)
        files.extend(ln.strip().replace('\\', '/') for ln in wt.splitlines() if ln.strip())
    dedup = []
    seen = set()
    for rel in files:
        if rel not in seen:
            seen.add(rel)
            dedup.append(rel)
    return dedup


def deleted_files(since: str, to: str = 'HEAD') -> list[str]:
    since_sha = resolve_ref(since)
    to_sha = resolve_ref(to)
    out = _run_git('diff', '--name-only', '--diff-filter=D', '%s..%s' % (since_sha, to_sha))
    return [ln.strip().replace('\\', '/') for ln in out.splitlines() if ln.strip()]


def filter_release_files(paths: list[str]) -> tuple[list[str], list[str]]:
    manifest = load_manifest()
    picked, skipped = [], []
    for rel in paths:
        if any(rel.startswith(p) for p in UPDATE_SKIP_PREFIXES):
            skipped.append(rel)
            continue
        if not is_client_release_path(rel, manifest):
            skipped.append(rel)
            continue
        src = ROOT / rel
        if not src.is_file():
            skipped.append(rel)
            continue
        picked.append(rel)
    return picked, skipped


def git_oneline_log(since: str, to: str = 'HEAD', limit: int = 20) -> str:
    since_sha = resolve_ref(since)
    to_sha = resolve_ref(to)
    out = _run_git('log', '--oneline', '--no-decorate', '%s..%s' % (since_sha, to_sha))
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return '增量更新'
    if len(lines) > limit:
        lines = lines[:limit] + ['…共 %s 条提交' % len(lines)]
    return '\n'.join(lines)


def build_zip(files: list[str], output: Path, version: str = '') -> dict:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    stats = {'files': 0, 'bytes': 0}
    with tempfile.TemporaryDirectory(prefix='rvc-update-staging-') as tmp:
        stage = Path(tmp)
        for rel in files:
            src = ROOT / rel
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            stats['files'] += 1
            stats['bytes'] += src.stat().st_size
        if version:
            (stage / 'VERSION').write_text(version.strip() + '\n', encoding='utf-8')
            stats['files'] += 1
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    zf.write(path, path.relative_to(stage).as_posix())
    stats['zip'] = str(output.resolve())
    stats['size'] = output.stat().st_size
    return stats


def publish_zip(zip_path: Path, version: str, desc: str, base_url: str, patch: str = ''):
    cmd = [
        sys.executable,
        str(ROOT / 'server' / 'tools' / 'publish_release.py'),
        str(zip_path),
        '--version',
        version,
        '--desc',
        desc,
        '--base-url',
        base_url,
    ]
    if patch:
        cmd.extend(['--patch', patch])
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError('publish_release 失败，退出码 %s' % proc.returncode)


def main():
    parser = argparse.ArgumentParser(
        description='根据 git 版本/标签差异，打包客户端增量更新 zip',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例:\n'
            '  python scripts/make_update_zip.py --since v0.1.0-demo --version 0.1.1\n'
            '  python scripts/make_update_zip.py --since abc1234 --to HEAD --output dist/patch.zip\n'
            '  python scripts/make_update_zip.py --since v0.1.0-demo --version 0.1.1 --publish\n'
        ),
    )
    parser.add_argument('--since', required=True, help='起始 git 引用：tag / commit / branch')
    parser.add_argument('--to', default='HEAD', help='结束引用，默认 HEAD')
    parser.add_argument('--include-worktree', action='store_true', help='额外包含相对 --to 未提交的改动')
    parser.add_argument('--version', default='', help='写入 zip 内 VERSION 文件的版本号（建议与 manifest 一致）')
    parser.add_argument('--output', default='', help='输出 zip 路径，默认 dist/update-<version>.zip')
    parser.add_argument('--desc', default='', help='更新说明；默认取 git log 摘要')
    parser.add_argument('--publish', action='store_true', help='打包后调用 server/tools/publish_release.py')
    parser.add_argument('--base-url', default='http://127.0.0.1:8765', help='发布时的更新服务根 URL')
    parser.add_argument('--list-only', action='store_true', help='只列出将打入 zip 的文件，不打包')
    args = parser.parse_args()

    since_sha = resolve_ref(args.since)
    to_sha = resolve_ref(args.to)
    raw = changed_files(args.since, args.to, include_worktree=args.include_worktree)
    picked, skipped = filter_release_files(raw)
    deleted = filter_release_files(deleted_files(args.since, args.to))[0]

    print('Git 范围: %s .. %s' % (since_sha[:8], to_sha[:8]))
    print('变更文件: %s，纳入更新包: %s，跳过: %s' % (len(raw), len(picked), len(skipped)))
    if deleted:
        print('注意: 以下 %s 个文件在 git 中已删除，增量 zip 无法自动删除安装目录内对应文件:' % len(deleted))
        for rel in deleted[:15]:
            print('  - %s' % rel)
        if len(deleted) > 15:
            print('  …')

    if not picked:
        print('没有可打入客户端更新包的文件，退出。')
        if skipped:
            print('已跳过示例:', ', '.join(skipped[:8]))
        return 1

    if args.list_only:
        for rel in picked:
            print(rel)
        return 0

    version = str(args.version or '').strip()
    out = Path(args.output) if args.output else ROOT / 'dist' / ('update-%s.zip' % (version or ('%s-%s' % (since_sha[:8], to_sha[:8]))))
    stats = build_zip(picked, out, version=version)
    print('ZIP: %s (%s 文件, %s bytes)' % (stats['zip'], stats['files'], stats['size']))
    for rel in picked:
        print('  + %s' % rel)

    manifest_path = ROOT / 'dist' / ('update-%s.manifest.json' % (version or 'latest'))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                'since': args.since,
                'since_sha': since_sha,
                'to': args.to,
                'to_sha': to_sha,
                'version': version,
                'files': picked,
                'skipped': skipped,
                'deleted_in_git': deleted,
            },
            ensure_ascii=False,
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    print('清单: %s' % manifest_path)

    if args.publish:
        if not version:
            print('发布需要 --version', file=sys.stderr)
            return 1
        desc = args.desc.strip() or git_oneline_log(args.since, args.to)
        publish_zip(out, version, desc, args.base_url)
        print('已发布到 server/data/version.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
