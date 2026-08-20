"""WAV 读盘缓存，避免同一文件被 stream / pitchfix / 歌词 energy 重复解码。"""
import numpy as np
from pathlib import Path

_cache = {}


def load_mono_raw(path: str | Path) -> tuple[np.ndarray, int]:
    path = str(Path(path).resolve())
    key = (path, 'raw')
    hit = _cache.get(key)
    if hit is not None:
        return hit
    import soundfile as sf
    data, sr = sf.read(path, dtype='float32', always_2d=True)
    mono = np.asarray(data.mean(axis=1), dtype=np.float32)
    hit = (mono, int(sr))
    _cache[key] = hit
    return hit


def load_mono_resampled(path: str | Path, target_sr: int) -> np.ndarray:
    path = str(Path(path).resolve())
    key = (path, int(target_sr))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    mono, file_sr = load_mono_raw(path)
    if int(file_sr) != int(target_sr):
        import librosa
        mono = librosa.resample(mono, orig_sr=int(file_sr), target_sr=int(target_sr)).astype(np.float32, copy=False)
    hit = np.asarray(mono, dtype=np.float32)
    _cache[key] = hit
    return hit
