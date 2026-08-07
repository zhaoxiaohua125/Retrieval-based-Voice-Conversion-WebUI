"""Task 9 MVP: reference F0 + pitch correction smoke tests."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pitchfix.corrector import correct_toward_target, estimate_f0
from app.pitchfix.detune import apply_detune_f0, detune_cents
from app.pitchfix.f0_curve import ReferenceF0Curve


def test_detune():
    base = 440.0
    a = apply_detune_f0(base, 'off', 1.0)
    b = apply_detune_f0(base, 'humanized', 0.25)
    assert a == base
    assert b != base
    assert detune_cents('humanized', 0.25) != 0
    print('detune ok off=%.1f humanized=%.1f cents=%.2f' % (a, b, detune_cents('humanized', 0.25)))


def test_corrector_math():
    sr = 48000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    block = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    out = correct_toward_target(block, sr, 440.0, 466.0, strength=1.0, max_semitone=4.0)
    assert out.shape == block.shape
    est = estimate_f0(out, sr)
    assert est > 0
    print('corrector ok est=%.1f' % est)


def test_f0_curve_lookup():
    curve = ReferenceF0Curve(np.array([0.0, 1.0, 2.0]), np.array([220.0, 220.0, 440.0]), 48000)
    assert abs(curve.at_time(0.5) - 220.0) < 1.0
    assert abs(curve.at_time(1.5) - 330.0) < 1.0
    print('f0 curve ok')


def main():
    test_detune()
    test_f0_curve_lookup()
    test_corrector_math()
    wav = ROOT / 'opt' / 'task4_offline'
    sample = next(wav.glob('*_converted_vocal.wav'), None) if wav.is_dir() else None
    if sample:
        curve = ReferenceF0Curve.from_wav(sample)
        print('loaded %s at_time(1)=%.1f' % (sample.name, curve.at_time(1.0)))
    print('task9 pitchfix smoke passed')


if __name__ == '__main__':
    main()
