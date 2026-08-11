"""人声音轨能量 peaks（波形 / 智能切共用，无 UI 依赖）。"""

from pathlib import Path

import numpy as np
import soundfile as sf


def load_waveform_peaks(path, points=1200):
    path = str(path or '')
    if not path or not Path(path).is_file():
        return None, 0.0
    info = sf.info(path)
    duration = float(info.duration or 0.0)
    frames = int(info.frames or 0)
    if frames <= 0 or duration <= 0:
        return None, duration
    points = max(96, min(int(points), frames))
    block = max(1, frames // points)
    peaks = []
    with sf.SoundFile(path) as f:
        while True:
            data = f.read(block, dtype='float32', always_2d=True)
            if len(data) == 0:
                break
            mono = data.mean(axis=1)
            peaks.append(float(np.max(np.abs(mono))) if len(mono) else 0.0)
    if not peaks:
        return None, duration
    arr = np.asarray(peaks, dtype=np.float32)
    peak = float(arr.max()) or 1.0
    return arr / peak, duration


def silence_threshold(peaks, floor=0.06):
    if peaks is None or len(peaks) == 0:
        return 0.12
    med = float(np.median(peaks))
    p90 = float(np.percentile(peaks, 90)) if len(peaks) > 4 else float(np.max(peaks))
    return max(floor, min(0.2, med * 0.45, p90 * 0.18))


def is_vocal_energy_region(time_sec, peaks, duration, threshold=None) -> bool:
    """True=有人声能量（唱段）；False=伴奏/静音段。"""
    if peaks is None or len(peaks) == 0 or duration <= 0:
        return True
    thresh = threshold if threshold is not None else silence_threshold(peaks)
    n = len(peaks)
    t = max(0.0, min(float(time_sec), float(duration)))
    idx = int(t / duration * (n - 1))
    i0 = max(0, idx - 1)
    i1 = min(n, idx + 2)
    return float(np.max(peaks[i0:i1])) >= thresh
