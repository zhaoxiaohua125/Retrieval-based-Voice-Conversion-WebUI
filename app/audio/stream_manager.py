"""sounddevice 流管理：采集/播放、环形缓冲、热插拔重连。"""

import logging
import threading
import time
import traceback
from dataclasses import dataclass

import numpy as np

from app.audio.devices import pick_voicemeeter_defaults
from app.audio.ring_buffer import RingBuffer

logger = logging.getLogger('rvc_client.audio')


@dataclass
class AudioStreamConfig:
    sample_rate: int = 48000
    block_ms: int = 200
    channels: int = 1
    dtype: str = 'float32'
    input_device: int | None = None
    output_device: int | None = None
    hostapi: str | None = None
    wasapi_exclusive: bool = False
    ring_ms: int = 500
    passthrough: bool = False
    passthrough_gain: float = 2.0

    def block_frames(self) -> int:
        ms = max(100, min(500, int(self.block_ms)))
        return max(1, int(self.sample_rate * ms / 1000))

    def ring_capacity(self) -> int:
        ms = max(self.block_ms, min(2000, int(self.ring_ms)))
        return max(self.block_frames() * 4, int(self.sample_rate * ms / 1000))


class AudioStreamManager:
    """独立线程音频流：输入写入 input_ring，播放从 output_ring 读取。"""

    def __init__(self, config: AudioStreamConfig | None = None):
        self.config = config or AudioStreamConfig()
        self.input_ring = RingBuffer(self.config.ring_capacity(), self.config.channels)
        self.output_ring = RingBuffer(self.config.ring_capacity(), self.config.channels)
        self._stream = None
        self._running = False
        self._lock = threading.RLock()
        self._last_out = np.zeros((1, self.config.channels), dtype=np.float32)
        self._fade = np.ones(1, dtype=np.float32)
        self._error = None
        self._reconnect = False
        self._watchdog = None
        self._stats = {'callbacks': 0, 'underruns': 0, 'input_overflow': 0, 'restarts': 0}

    @property
    def stats(self):
        return dict(self._stats)

    @property
    def running(self):
        return self._running

    @property
    def last_error(self):
        return self._error

    def resolve_devices(self):
        if self.config.input_device is not None and self.config.output_device is not None:
            return self.config.input_device, self.config.output_device
        return pick_voicemeeter_defaults()

    def start(self):
        with self._lock:
            if self._running:
                return self
            in_dev, out_dev = self.resolve_devices()
            if in_dev is None or out_dev is None:
                raise RuntimeError('未找到可用音频输入/输出设备')
            self.config.input_device = in_dev
            self.config.output_device = out_dev
            self._open_stream()
            self._running = True
            self._watchdog = threading.Thread(target=self._watch_loop, name='audio-watchdog', daemon=True)
            self._watchdog.start()
            logger.info('audio stream started in=%s out=%s sr=%s block=%s', in_dev, out_dev, self.config.sample_rate, self.config.block_frames())
            return self

    def stop(self):
        with self._lock:
            self._running = False
            self._close_stream()
            self.input_ring.clear()
            self.output_ring.clear()
            logger.info('audio stream stopped')
            return self

    def _extra_settings(self):
        import sounddevice as sd

        if self.config.wasapi_exclusive:
            try:
                return sd.WasapiSettings(exclusive=True)
            except Exception:
                logger.warning('WASAPI exclusive unavailable, fallback to shared mode')
        return None

    def _open_stream(self):
        import sounddevice as sd

        block = self.config.block_frames()
        extra = self._extra_settings()
        self._stream = sd.Stream(
            device=(self.config.input_device, self.config.output_device),
            samplerate=self.config.sample_rate,
            blocksize=block,
            channels=self.config.channels,
            dtype=self.config.dtype,
            callback=self._callback,
            extra_settings=extra,
        )
        self._stream.start()

    def _close_stream(self):
        if self._stream is None:
            return
        try:
            self._stream.abort()
            self._stream.close()
        except Exception:
            logger.debug('stream close: %s', traceback.format_exc())
        self._stream = None

    def _callback(self, indata, outdata, frames, time_info, status):
        import sounddevice as sd

        self._stats['callbacks'] += 1
        if status:
            if status.input_overflow:
                self._stats['input_overflow'] += 1
            if status.output_underflow:
                self._stats['underruns'] += 1
            self._reconnect = True
        try:
            mono_in = np.asarray(indata, dtype=np.float32)
            if mono_in.ndim == 2 and mono_in.shape[1] > 1:
                mono_in = mono_in.mean(axis=1, keepdims=True)
            elif mono_in.ndim == 1:
                mono_in = mono_in.reshape(-1, 1)
            self.input_ring.write(mono_in)
            if self.config.passthrough:
                gain = float(self.config.passthrough_gain or 1.0)
                boosted = np.clip(mono_in * gain, -1.0, 1.0)
                self.output_ring.write(boosted)
            need = outdata.shape[0]
            chunk = self.output_ring.read(need)
            filled = self._smooth_output(chunk, need)
            if outdata.ndim == 1:
                outdata[:] = filled[:, 0]
            else:
                outdata[:] = filled[:, : outdata.shape[1]]
        except Exception as exc:
            self._error = str(exc)
            self._reconnect = True
            outdata.fill(0)
            logger.error('audio callback error: %s', exc)

    def _smooth_output(self, chunk: np.ndarray, need: int) -> np.ndarray:
        channels = self.config.channels
        out = np.zeros((need, channels), dtype=np.float32)
        got = min(need, len(chunk))
        if got < need:
            self._stats['underruns'] += 1
        if got:
            out[:got] = chunk[:got]
            self._last_out = out[got - 1 : got].copy()
        if got < need:
            fade_len = min(64, need - got)
            tail = self._last_out[0]
            for i in range(need - got):
                gain = max(0.0, 1.0 - (i + 1) / max(1, fade_len))
                out[got + i] = tail * gain
        return out

    def _watch_loop(self):
        while self._running:
            time.sleep(0.5)
            if not self._reconnect:
                continue
            self._reconnect = False
            with self._lock:
                if not self._running:
                    break
                try:
                    self._close_stream()
                    self._open_stream()
                    self._stats['restarts'] += 1
                    self._error = None
                    logger.warning('audio stream restarted after device/error event')
                except Exception as exc:
                    self._error = str(exc)
                    self._reconnect = True
                    logger.error('audio reconnect failed: %s', exc)

    def push_output(self, frames: np.ndarray) -> int:
        return self.output_ring.write(frames)

    def read_input(self, frame_count: int) -> np.ndarray:
        return self.input_ring.read(frame_count)

    def peek_input(self, frame_count: int) -> np.ndarray:
        return self.input_ring.peek(frame_count)
