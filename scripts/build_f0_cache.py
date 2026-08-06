"""为已有 converted_vocal.wav 批量生成 AI 跟唱 F0 缓存（无需重新做歌）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pitchfix.f0_curve import ReferenceF0Curve, f0_cache_path


def main():
    dirs = [ROOT / 'opt', ROOT / 'opt' / 'task4_offline']
    n = 0
    for folder in dirs:
        if not folder.is_dir():
            continue
        for wav in sorted(folder.glob('*_converted_vocal.wav')):
            cache = f0_cache_path(wav)
            if cache.is_file() and cache.stat().st_mtime >= wav.stat().st_mtime:
                print('skip (cached) %s' % wav.name)
                continue
            print('building %s ...' % wav.name)
            ReferenceF0Curve.from_wav(wav)
            print('  -> %s' % cache.name)
            n += 1
    print('done, built=%d' % n)


if __name__ == '__main__':
    main()
