"""离线 WAV 播放（AI 唱歌）。"""

import logging
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger('rvc_client.playback')


class WavPlayer:
    def __init__(self):
        self._lock = threading.RLock()
        self._data = None
        self._sr = 48000
        self._pos = 0
        self._playing = False
        self._paused = False
        self._stream = None
        self._on_finish = None
        self._duration = 0.0
        self._path = ''

    @property
    def path(self):
        return self._path

    @property
    def duration(self):
        return self._duration

    @property
    def position(self):
        with self._lock:
            return self._pos / self._sr if self._sr else 0.0

    @property
    def is_playing(self):
        with self._lock:
            return self._playing and not self._paused

    @property
    def is_active(self):
        with self._lock:
            return self._playing

    def load(self, path: str):
        data, sr = sf.read(path, dtype='float32', always_2d=True)
        with self._lock:
            self.stop()
            self._data = data
            self._sr = int(sr)
            self._pos = 0
            self._duration = len(data) / sr if sr else 0.0
            self._path = path
        return self._duration

    def play(self, path: str | None = None, on_finish=None):
        if path:
            self.load(path)
        with self._lock:
            if self._data is None:
                return False
            self._on_finish = on_finish
            self._paused = False
            self._playing = True
            self._start_stream()
        return True

    def _start_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        def callback(outdata, frames, _time, status):
            del _time, status
            with self._lock:
                if self._paused or not self._playing or self._data is None:
                    outdata.fill(0)
                    return
                end = self._pos + frames
                chunk = self._data[self._pos:end]
                if len(chunk) < frames:
                    outdata[: len(chunk)] = chunk
                    outdata[len(chunk) :] = 0
                    self._playing = False
                    raise sd.CallbackStop()
                outdata[:] = chunk
                self._pos = end

        channels = self._data.shape[1]
        self._stream = sd.OutputStream(
            samplerate=self._sr,
            channels=channels,
            callback=callback,
            finished_callback=self._on_stream_finished,
        )
        self._stream.start()

    def _on_stream_finished(self):
        cb = None
        with self._lock:
            self._playing = False
            self._stream = None
            cb = self._on_finish
        if cb:
            try:
                cb()
            except Exception:
                logger.error('playback on_finish failed', exc_info=True)

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            if self._playing:
                self._paused = False

    def toggle_pause(self):
        with self._lock:
            if not self._playing:
                return False
            self._paused = not self._paused
            return not self._paused

    def seek_ratio(self, ratio: float):
        with self._lock:
            if self._data is None or self._duration <= 0:
                return
            ratio = max(0.0, min(1.0, float(ratio)))
            self._pos = int(ratio * self._duration * self._sr)

    def stop(self):
        with self._lock:
            self._playing = False
            self._paused = False
            stream = self._stream
            self._stream = None
            self._pos = 0
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
