"""参考人声 F0 曲线（离线提取，播放时按 T 查表；支持磁盘缓存）。"""

import logging
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

logger = logging.getLogger('rvc_client.pitchfix')


def f0_cache_path(wav_path) -> Path:
    return Path(wav_path).with_suffix('.f0.npz')


def _f0_cache_path(wav_path) -> Path:
    return f0_cache_path(wav_path)


class ReferenceF0Curve:
    def __init__(self, times: np.ndarray, f0: np.ndarray, sr: int):
        self.times = np.asarray(times, dtype=np.float64)
        self.f0 = np.asarray(f0, dtype=np.float32)
        self.sr = int(sr)

    @classmethod
    def from_wav(cls, path, sr=48000, fmin=50, fmax=1100, hop_length=512, analysis_sr=22050):
        path = Path(path)
        cache = _f0_cache_path(path)
        try:
            if cache.is_file() and cache.stat().st_mtime >= path.stat().st_mtime:
                data = np.load(cache)
                logger.info('reference F0 cache hit %s', cache.name)
                return cls(data['times'], data['f0'], int(data['sr']))
        except OSError:
            pass
        data, file_sr = sf.read(str(path), dtype='float32', always_2d=False)
        if getattr(data, 'ndim', 1) > 1:
            data = data.mean(axis=1)
        if file_sr != analysis_sr:
            data = librosa.resample(data, orig_sr=file_sr, target_sr=analysis_sr)
        f0, _, _ = librosa.pyin(data, fmin=fmin, fmax=fmax, sr=analysis_sr, hop_length=hop_length)
        times = librosa.times_like(f0, sr=analysis_sr, hop_length=hop_length)
        f0 = np.nan_to_num(f0, nan=0.0).astype(np.float32)
        try:
            np.savez(cache, times=times, f0=f0, sr=analysis_sr)
        except OSError:
            logger.warning('failed to write F0 cache: %s', cache)
        logger.info('reference F0 built %s frames=%s analysis_sr=%s', path.name, len(times), analysis_sr)
        return cls(times, f0, analysis_sr)

    def at_time(self, t: float) -> float:
        if self.times.size == 0:
            return 0.0
        t = max(0.0, float(t))
        if t >= self.times[-1]:
            return float(self.f0[-1])
        return float(np.interp(t, self.times, self.f0))
