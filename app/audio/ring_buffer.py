"""线程安全 float32 环形缓冲（帧为单位）。"""

import threading

import numpy as np


class RingBuffer:
    """固定容量环形缓冲，供音频回调与业务线程交换 PCM。"""

    def __init__(self, capacity_frames: int, channels: int = 1, dtype=np.float32):
        self._lock = threading.Lock()
        self._channels = max(1, int(channels))
        self._capacity = max(1, int(capacity_frames))
        self._data = np.zeros((self._capacity, self._channels), dtype=dtype)
        self._write = 0
        self._available = 0

    @property
    def capacity(self):
        return self._capacity

    @property
    def channels(self):
        return self._channels

    def clear(self):
        with self._lock:
            self._write = 0
            self._available = 0
            self._data.fill(0)

    def available_frames(self):
        with self._lock:
            return self._available

    def write(self, frames: np.ndarray) -> int:
        if frames is None or len(frames) == 0:
            return 0
        arr = np.asarray(frames, dtype=self._data.dtype)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        if arr.shape[1] != self._channels:
            arr = arr[:, : self._channels] if arr.shape[1] > self._channels else np.pad(
                arr, ((0, 0), (0, self._channels - arr.shape[1]))
            )
        count = min(len(arr), self._capacity)
        with self._lock:
            for i in range(count):
                self._data[self._write] = arr[i]
                self._write = (self._write + 1) % self._capacity
                if self._available < self._capacity:
                    self._available += 1
                else:
                    pass
        return count

    def read(self, frame_count: int) -> np.ndarray:
        need = max(0, int(frame_count))
        out = np.zeros((need, self._channels), dtype=self._data.dtype)
        with self._lock:
            got = min(need, self._available)
            start = (self._write - self._available) % self._capacity
            for i in range(got):
                out[i] = self._data[(start + i) % self._capacity]
            self._available -= got
        return out

    def peek(self, frame_count: int) -> np.ndarray:
        need = max(0, int(frame_count))
        out = np.zeros((need, self._channels), dtype=self._data.dtype)
        with self._lock:
            got = min(need, self._available)
            start = (self._write - self._available) % self._capacity
            for i in range(got):
                out[i] = self._data[(start + i) % self._capacity]
        return out
