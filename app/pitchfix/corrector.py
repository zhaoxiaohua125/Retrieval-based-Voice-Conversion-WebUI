"""块级音高估计与向参考 F0 靠拢（修音核心，轻量实现避免 GIL 卡顿）。"""

import numpy as np
from scipy.signal import resample


def estimate_f0(block: np.ndarray, sr: int, fmin=50, fmax=1100) -> float:
    x = np.asarray(block, dtype=np.float32).reshape(-1)
    if x.size < 256:
        return 0.0
    step = max(1, int(sr / 4000))
    x = x[::step]
    sr_eff = max(1, sr // step)
    x = x - float(np.mean(x))
    rms = float(np.sqrt(np.mean(x * x)))
    if rms < 1e-4:
        return 0.0
    corr = np.correlate(x, x, mode='full')
    corr = corr[len(corr) // 2 :]
    min_lag = max(1, int(sr_eff / fmax))
    max_lag = min(int(sr_eff / fmin), len(corr) - 1)
    if max_lag <= min_lag:
        return 0.0
    seg = corr[min_lag : max_lag + 1]
    lag = min_lag + int(np.argmax(seg))
    if corr[lag] < corr[0] * 0.3:
        return 0.0
    return float(sr_eff / lag)


def correct_toward_target(block, sr, mic_f0, target_f0, strength=0.85, max_semitone=2.0):
    x = np.asarray(block, dtype=np.float32).reshape(-1)
    if mic_f0 <= 0 or target_f0 <= 0 or x.size == 0:
        return x
    n_steps = 12.0 * np.log2(target_f0 / mic_f0) * float(strength)
    n_steps = float(np.clip(n_steps, -max_semitone, max_semitone))
    if abs(n_steps) < 0.05:
        return x
    rate = 2.0 ** (n_steps / 12.0)
    n = x.size
    mid = max(8, int(round(n / rate)))
    y = resample(x, mid)
    return np.asarray(resample(y, n), dtype=np.float32)
