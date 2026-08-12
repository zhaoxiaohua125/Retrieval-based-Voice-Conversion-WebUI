"""离线 WAV 播放（AI 唱歌）。"""

import logging
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger('rvc_client')


class WavPlayer:
    def __init__(self, output_device=None, target_sr: int | None = 48000):
        self._lock = threading.RLock()
        self._output_device = output_device
        self._target_sr = int(target_sr) if target_sr else None
        self._data = None
        self._sr = 48000
        self._pos = 0
        self._playing = False
        self._paused = False
        self._stream = None
        self._stream_gen = 0
        self._on_finish = None
        self._duration = 0.0
        self._path = ''
        self._clock_origin_frame = 0
        self._clock_origin_mono = 0.0
        self._out_latency = 0.05
        self._clock_active = False

    @property
    def path(self):
        return self._path

    @property
    def duration(self):
        return self._duration

    @property
    def position(self):
        """墙钟外推可听位置，与跟唱共用同一套歌词时钟思路。"""
        with self._lock:
            if not self._sr:
                return 0.0
            written = self._pos / self._sr
            if not self._playing or self._paused or not self._clock_active:
                return written
            elapsed = time.monotonic() - self._clock_origin_mono
            est = self._clock_origin_frame / self._sr + elapsed - self._out_latency
            hi = min(self._duration, written + 0.4)
            return max(0.0, min(est, hi))

    @property
    def is_playing(self):
        with self._lock:
            return self._playing and not self._paused

    @property
    def is_active(self):
        with self._lock:
            return self._playing

    def set_output_device(self, device):
        with self._lock:
            self._output_device = device

    def set_target_sr(self, sr: int | None):
        with self._lock:
            self._target_sr = int(sr) if sr else None

    def _playback_sr(self, file_sr: int) -> int:
        if self._output_device is not None:
            try:
                return int(sd.query_devices(self._output_device).get('default_samplerate') or file_sr)
            except Exception:
                pass
        if self._target_sr:
            return self._target_sr
        return int(file_sr)

    def _reset_clock_locked(self, frame: int | None = None, active: bool = False):
        fr = self._pos if frame is None else int(frame)
        self._clock_origin_frame = fr
        self._clock_origin_mono = time.monotonic()
        self._clock_active = bool(active)

    @staticmethod
    def _close_stream(stream):
        if stream is None:
            return
        try:
            stream.abort()
            stream.close()
        except Exception:
            pass

    def _take_stream_locked(self):
        stream = self._stream
        self._stream = None
        return stream

    def load(self, path: str):
        path = str(path)
        with self._lock:
            if path == self._path and self._data is not None:
                return self._duration
            need_stop = self._playing
        if need_stop:
            self.stop()
        data, sr = sf.read(path, dtype='float32', always_2d=True)
        sr = int(sr)
        out_sr = self._playback_sr(sr)
        if out_sr != sr:
            import librosa

            data = librosa.resample(data.T, orig_sr=sr, target_sr=out_sr).T
            sr = out_sr
        with self._lock:
            self._data = data
            self._sr = sr
            self._pos = 0
            self._duration = len(data) / sr if sr else 0.0
            self._path = path
            self._reset_clock_locked(0, active=False)
        return self._duration

    def play(self, path: str | None = None, on_finish=None):
        if path:
            self.load(path)
        with self._lock:
            if self._data is None:
                logger.warning('wav play skipped: no data')
                return False
            if self._pos >= len(self._data):
                logger.warning('wav play at eof pos=%s len=%s, rewind', self._pos, len(self._data))
                self._pos = 0
            self._on_finish = on_finish
            self._paused = False
            self._playing = True
            self._reset_clock_locked(self._pos, active=False)
        try:
            gen = self._start_stream()
        except Exception:
            with self._lock:
                self._playing = False
                self._on_finish = None
                self._clock_active = False
            raise
        logger.info('wav play started gen=%s dev=%s pos=%.2fs dur=%.2fs', gen, self._output_device, self.position, self.duration)
        return True

    def _start_stream(self):
        with self._lock:
            self._stream_gen += 1
            gen = self._stream_gen
            old = self._take_stream_locked()
            channels = self._data.shape[1]
            sr = self._sr
            out_dev = self._output_device

            def callback(outdata, frames, time_info, status):
                _ = status
                lat = None
                try:
                    if time_info is not None:
                        lat = float(time_info.outputBufferDacTime) - float(time_info.currentTime)
                except Exception:
                    lat = None
                with self._lock:
                    if self._stream_gen != gen or self._paused or not self._playing or self._data is None:
                        outdata.fill(0)
                        return
                    start = self._pos
                    end = start + frames
                    chunk = self._data[start:end]
                    if len(chunk) < frames:
                        outdata[: len(chunk)] = chunk
                        outdata[len(chunk) :] = 0
                        self._pos = start + len(chunk)
                        self._reset_clock_locked(self._pos, active=False)
                        self._playing = False
                        raise sd.CallbackStop()
                    outdata[:] = chunk
                    self._pos = end
                    self._clock_origin_frame = start
                    self._clock_origin_mono = time.monotonic()
                    if lat is not None and lat == lat and 0.005 <= float(lat) <= 0.22:
                        self._out_latency = 0.65 * self._out_latency + 0.35 * float(lat)
                    self._clock_active = True

            def finished_callback():
                self._on_stream_finished(gen)

            kwargs = dict(
                samplerate=sr,
                channels=channels,
                callback=callback,
                finished_callback=finished_callback,
                blocksize=0,
            )
            if out_dev is not None:
                kwargs['device'] = out_dev
            stream = sd.OutputStream(**kwargs)
            self._stream = stream
        self._close_stream(old)
        stream.start()
        return gen

    def _on_stream_finished(self, gen: int):
        cb = None
        with self._lock:
            if gen != self._stream_gen:
                logger.info('ignore stale stream finished gen=%s current=%s', gen, self._stream_gen)
                return
            self._playing = False
            self._clock_active = False
            self._stream = None
            cb = self._on_finish
            self._on_finish = None
        if cb:
            try:
                cb()
            except Exception:
                logger.error('playback on_finish failed', exc_info=True)

    def pause(self):
        with self._lock:
            self._paused = True
            self._clock_active = False

    def resume(self):
        with self._lock:
            if self._playing:
                self._paused = False
                self._reset_clock_locked(self._pos, active=True)

    def toggle_pause(self):
        with self._lock:
            if not self._playing:
                return False
            self._paused = not self._paused
            if self._paused:
                self._clock_active = False
            else:
                self._reset_clock_locked(self._pos, active=True)
            return not self._paused

    def seek_ratio(self, ratio: float):
        with self._lock:
            if self._data is None or self._duration <= 0:
                return
            ratio = max(0.0, min(1.0, float(ratio)))
            self._pos = int(ratio * self._duration * self._sr)
            self._pos = min(self._pos, max(0, len(self._data) - 1))
            self._reset_clock_locked(self._pos, active=self._playing and not self._paused)

    def stop(self):
        with self._lock:
            self._stream_gen += 1
            self._playing = False
            self._paused = False
            self._on_finish = None
            self._clock_active = False
            stream = self._take_stream_locked()
        self._close_stream(stream)

    def stop_reset(self):
        self.stop()
        with self._lock:
            self._pos = 0
            self._reset_clock_locked(0, active=False)
