"""独立子进程入口：生成 F0 缓存，避免占用 UI 进程 GIL。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pitchfix.f0_curve import ReferenceF0Curve

if __name__ == '__main__':
    wav = sys.argv[1]
    fmin = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    fmax = float(sys.argv[3]) if len(sys.argv) > 3 else 1100.0
    ReferenceF0Curve.from_wav(wav, fmin=fmin, fmax=fmax)
