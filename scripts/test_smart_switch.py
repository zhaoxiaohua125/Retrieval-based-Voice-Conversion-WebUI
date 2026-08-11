"""智能切：converted_vocal 能量判定烟测。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from app.playback.waveform_peaks import is_vocal_energy_region, silence_threshold


def test_energy_region():
    peaks = np.array([0.02, 0.03, 0.05, 0.9, 0.85, 0.04, 0.03, 0.02], dtype=np.float32)
    dur = 80.0
    th = silence_threshold(peaks)
    assert not is_vocal_energy_region(5.0, peaks, dur, th)
    assert is_vocal_energy_region(40.0, peaks, dur, th)
    assert not is_vocal_energy_region(70.0, peaks, dur, th)
    assert is_vocal_energy_region(5.0, None, dur)
    print('smart_switch energy smoke passed')


if __name__ == '__main__':
    test_energy_region()
