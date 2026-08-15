"""sounddevice 流管理：采集/播放、环形缓冲、热插拔重连。"""

import logging
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.audio.devices import resolve_io_devices
from app.audio.follow_vad import follow_vad_tick, smooth_follow_gate
from app.audio.ring_buffer import RingBuffer

logger = logging.getLogger('rvc_client.audio')

PLAYBACK_MODES = ('normal_talk', 'reverb_talk', 'ai_sing', 'ai_follow')


@dataclass
class AudioStreamConfig:
    sample_rate: int = 48000
    block_ms: int = 200
    channels: int = 1
    dtype: str = 'float32'
    input_device: int | str | None = None
    output_device: int | str | None = None
    hostapi: str | None = None
    wasapi_exclusive: bool = False
    ring_ms: int = 500
    passthrough: bool = False
    passthrough_gain: float = 2.0
    passthrough_reverb: bool = False
    reverb_mix: float = 0.35
    reverb_decay: float = 0.72
    inst_gain: float = 0.77
    playback_mode: str = ''
    mic_gain: float = 0.77
    ref_vocal_gain: float = 0.0
    follow_threshold: float = 75.0
    follow_attenuation: float = 0.1

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
        self._rev_bufs = None
        self._rev_pos = None
        self._rev_delays = None
        self._inst_data = None
        self._inst_pos = 0
        self._inst_duration = 0.0
        self._inst_paused = False
        self._inst_finished = False
        self._inst_path = ''
        self._ref_vocal_data = None
        self._ref_vocal_path = ''
        self._voice_gate = 0.0
        self._voice_gate_smooth = 0.0
        self._voice_on_at = None
        self._gate_lock = threading.Lock()
        self._vad_stop = threading.Event()
        self._vad_thread = None
        self._voice_off_at = None
        self._vad_above = 0
        self._vad_below = 0
        self._clock_origin_mono = 0.0
        self._out_latency = 0.05
        self._clock_active = False
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
        return resolve_io_devices(
            self.config.input_device,
            self.config.output_device,
            hostapi=self.config.hostapi,
        )

    @property
    def inst_position(self) -> float:
        with self._lock:
            sr = int(self.config.sample_rate or 48000)
            if not sr:
                return 0.0
            written = self._inst_pos / sr
            if self._inst_paused or not self._clock_active or not self._running:
                return written
            elapsed = time.monotonic() - self._clock_origin_mono
            est = self._clock_origin_frame / sr + elapsed - self._out_latency
            hi = min(self._inst_duration, written + 0.4)
            return max(0.0, min(est, hi))

    @property
    def inst_duration(self) -> float:
        return float(self._inst_duration)

    @property
    def inst_playing(self) -> bool:
        with self._lock:
            return self._inst_data is not None and not self._inst_finished

    @property
    def inst_paused(self) -> bool:
        return bool(self._inst_paused)

    @property
    def inst_finished(self) -> bool:
        return bool(self._inst_finished)

    def _reset_clock_locked(self, frame: int | None = None, active: bool = False):
        fr = self._inst_pos if frame is None else int(frame)
        self._clock_origin_frame = fr
        self._clock_origin_mono = time.monotonic()
        self._clock_active = bool(active)

    def replay_instrumental(self):
        with self._lock:
            if self._inst_data is None:
                return
            self._inst_pos = 0
            self._inst_finished = False
            self._inst_paused = False
            self._reset_clock_locked(0, active=self._running and not self._inst_paused)

    def load_instrumental(self, path: str, seek_sec: float = 0.0):
        import soundfile as sf

        data, sr = sf.read(str(path), dtype='float32', always_2d=True)
        if data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        target_sr = int(self.config.sample_rate)
        if int(sr) != target_sr:
            import librosa

            data = librosa.resample(data.T, orig_sr=int(sr), target_sr=target_sr).T.reshape(-1, 1)
        with self._lock:
            self._inst_data = np.asarray(data[:, 0], dtype=np.float32)
            self._inst_pos = max(0, int(float(seek_sec) * target_sr))
            self._inst_duration = len(self._inst_data) / target_sr if target_sr else 0.0
            self._inst_paused = False
            self._inst_finished = False
            self._inst_path = str(Path(path).resolve())
            self._reset_clock_locked(self._inst_pos, active=self._running)

    def load_ref_vocal(self, path: str):
        import soundfile as sf

        data, sr = sf.read(str(path), dtype='float32', always_2d=True)
        if data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        target_sr = int(self.config.sample_rate)
        if int(sr) != target_sr:
            import librosa

            data = librosa.resample(data.T, orig_sr=int(sr), target_sr=target_sr).T.reshape(-1, 1)
        with self._lock:
            self._ref_vocal_data = np.asarray(data[:, 0], dtype=np.float32)
            self._ref_vocal_path = str(Path(path).resolve())

    def clear_instrumental(self):
        with self._lock:
            self._inst_data = None
            self._inst_pos = 0
            self._inst_duration = 0.0
            self._inst_paused = False
            self._inst_finished = False
            self._inst_path = ''
            self._reset_clock_locked(0, active=False)

    def clear_ref_vocal(self):
        with self._lock:
            self._ref_vocal_data = None
            self._ref_vocal_path = ''

    def seek_instrumental(self, seconds: float):
        with self._lock:
            if self._inst_data is None:
                return
            sr = int(self.config.sample_rate)
            self._inst_pos = max(0, min(len(self._inst_data), int(float(seconds) * sr)))
            self._inst_finished = False
            self._reset_clock_locked(self._inst_pos, active=self._running and not self._inst_paused)

    def toggle_inst_pause(self) -> bool:
        with self._lock:
            if self._inst_data is None:
                return False
            self._inst_paused = not self._inst_paused
            if self._inst_paused:
                self._clock_active = False
            else:
                self._reset_clock_locked(self._inst_pos, active=self._running)
            return not self._inst_paused

    def _read_song_frames(self, frames: int) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            inst = np.zeros(frames, dtype=np.float32)
            ref = np.zeros(frames, dtype=np.float32)
            if self._inst_data is None or self._inst_paused:
                return inst, ref
            start = self._inst_pos
            end = min(start + frames, len(self._inst_data))
            got = max(0, end - start)
            if got:
                inst[:got] = self._inst_data[start:end]
                if self._ref_vocal_data is not None:
                    ref_end = min(end, len(self._ref_vocal_data))
                    ref_got = max(0, ref_end - start)
                    if ref_got > 0:
                        ref[:ref_got] = self._ref_vocal_data[start:ref_end]
                self._inst_pos = end
                self._clock_origin_frame = start
                self._clock_origin_mono = time.monotonic()
                self._clock_active = True
            if end >= len(self._inst_data):
                self._inst_finished = True
            return inst, ref

    def set_playback_mode(self, cfg: AudioStreamConfig, inst_path: str | None = None, vocal_path: str | None = None, seek_sec: float = 0.0):
        prev_mode = self.config.playback_mode
        prev_reverb = self.config.passthrough_reverb
        self.config.playback_mode = cfg.playback_mode
        self.config.passthrough = cfg.passthrough
        self.config.passthrough_reverb = cfg.passthrough_reverb
        self.config.passthrough_gain = cfg.passthrough_gain
        self.config.reverb_mix = cfg.reverb_mix
        self.config.reverb_decay = cfg.reverb_decay
        self.config.inst_gain = cfg.inst_gain
        self.config.mic_gain = cfg.mic_gain
        self.config.ref_vocal_gain = cfg.ref_vocal_gain
        self.config.follow_threshold = cfg.follow_threshold
        self.config.follow_attenuation = cfg.follow_attenuation
        self.config.block_ms = cfg.block_ms
        if cfg.playback_mode == 'reverb_talk' and (prev_mode != 'reverb_talk' or not prev_reverb):
            self._init_reverb()
        elif cfg.playback_mode != 'reverb_talk' and prev_mode == 'reverb_talk':
            self._rev_bufs = self._rev_pos = self._rev_delays = None
        if inst_path:
            resolved = str(Path(inst_path).resolve())
            if self._inst_path == resolved:
                if seek_sec is not None:
                    tgt = float(seek_sec)
                    cur = self.inst_position
                    if tgt > cur + 0.12:
                        self.seek_instrumental(tgt)
            else:
                self.load_instrumental(inst_path, float(seek_sec or 0))
        if vocal_path and cfg.playback_mode in ('ai_sing', 'ai_follow'):
            resolved = str(Path(vocal_path).resolve())
            if self._ref_vocal_path != resolved:
                self.load_ref_vocal(vocal_path)
        if cfg.playback_mode == 'ai_follow':
            self._start_vad_worker()
        else:
            self._stop_vad_worker()
            with self._gate_lock:
                self._voice_gate = 1.0 if cfg.playback_mode == 'ai_sing' else 0.0
        return self

    def _smooth_follow_gate(self) -> float:
        att = min(0.2, max(0.1, float(self.config.follow_attenuation or 0.1)))
        with self._gate_lock:
            tgt = self._voice_gate
            g = self._voice_gate_smooth
        g = smooth_follow_gate(tgt, g, att)
        with self._gate_lock:
            self._voice_gate_smooth = g
            return g

    def _start_vad_worker(self):
        if self._vad_thread is not None and self._vad_thread.is_alive():
            return
        self._vad_stop.clear()
        self._voice_off_at = None
        self._voice_on_at = None
        self._vad_above = 0
        self._vad_below = 0
        with self._gate_lock:
            self._voice_gate = 0.0
            self._voice_gate_smooth = 0.0
        self._vad_thread = threading.Thread(target=self._vad_loop, name='stream-vad', daemon=True)
        self._vad_thread.start()

    def _stop_vad_worker(self):
        self._vad_stop.set()
        th = self._vad_thread
        self._vad_thread = None
        if th is not None and th.is_alive() and threading.current_thread() is not th:
            th.join(timeout=0.05)
        self._voice_off_at = None
        self._voice_on_at = None
        self._vad_above = 0
        self._vad_below = 0

    def _vad_loop(self):
        block = self.config.block_frames()
        while self._running and not self._vad_stop.is_set():
            try:
                if self.config.playback_mode != 'ai_follow':
                    break
                if self.input_ring.available_frames() < block:
                    time.sleep(0.002)
                    continue
                mic = self.input_ring.read(block)[:, 0]
                thr = float(self.config.follow_threshold or 75)
                open_gate = max(0.001, (thr / 100.0) * 0.006)
                close_gate = open_gate * 0.22
                att = float(self.config.follow_attenuation or 0.1)
                mic_rms = float(np.sqrt(np.mean(mic * mic))) if mic.size else 0.0
                now = time.monotonic()
                with self._gate_lock:
                    was_open = self._voice_gate >= 0.5
                active, self._vad_above, self._vad_below, self._voice_off_at, self._voice_on_at = follow_vad_tick(
                    mic_rms,
                    open_gate,
                    close_gate,
                    att,
                    was_open,
                    self._vad_above,
                    self._vad_below,
                    self._voice_off_at,
                    self._voice_on_at,
                    now,
                )
                with self._gate_lock:
                    self._voice_gate = 1.0 if active else 0.0
            except Exception:
                logger.error('stream vad error:\n%s', traceback.format_exc())
                time.sleep(0.02)

    def start(self):
        with self._lock:
            if self._running:
                return self
            in_dev, out_dev = self.resolve_devices()
            if in_dev is None or out_dev is None:
                raise RuntimeError('未找到可用音频输入/输出设备')
            self.config.input_device = in_dev
            self.config.output_device = out_dev
            if self.config.playback_mode == 'reverb_talk':
                self._init_reverb()
            self._open_stream()
            self._running = True
            if self.config.playback_mode == 'ai_follow':
                self._start_vad_worker()
            self._watchdog = threading.Thread(target=self._watch_loop, name='audio-watchdog', daemon=True)
            self._watchdog.start()
            logger.info('audio stream started in=%s out=%s sr=%s block=%s mode=%s', in_dev, out_dev, self.config.sample_rate, self.config.block_frames(), self.config.playback_mode)
            return self

    def stop(self):
        self._stop_vad_worker()
        with self._lock:
            self._running = False
            stream = self._stream
            self._stream = None
            self.input_ring.clear()
            self.output_ring.clear()
            self.clear_instrumental()
            self.clear_ref_vocal()
            self.config.playback_mode = ''
            self._reset_clock_locked(0, active=False)
        self._close_stream(stream)
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

    def _init_reverb(self):
        if not self.config.passthrough_reverb:
            self._rev_bufs = self._rev_pos = self._rev_delays = None
            return
        sr = int(self.config.sample_rate)
        self._rev_delays = [max(1, int(d * sr / 48000)) for d in (1557, 1617, 1491, 1422)]
        self._rev_bufs = [np.zeros(d, dtype=np.float32) for d in self._rev_delays]
        self._rev_pos = [0] * len(self._rev_delays)

    def _reverb_mono(self, mono: np.ndarray) -> np.ndarray:
        if not self.config.passthrough_reverb or self._rev_bufs is None:
            return mono[:, 0]
        mix = float(self.config.reverb_mix or 0.35)
        decay = float(self.config.reverb_decay or 0.72)
        dry = mono[:, 0]
        wet = np.zeros(len(dry), dtype=np.float32)
        for i, buf in enumerate(self._rev_bufs):
            delay = self._rev_delays[i]
            pos = self._rev_pos[i]
            for j, sample in enumerate(dry):
                tap = buf[pos]
                wet[j] += tap
                buf[pos] = sample + tap * decay
                pos = (pos + 1) % delay
            self._rev_pos[i] = pos
        wet *= 0.25
        return np.clip(dry * (1.0 - mix) + wet * mix, -1.0, 1.0)

    def _mix_output(self, frames: int, mono_in: np.ndarray) -> np.ndarray:
        mode = self.config.playback_mode or ('reverb_talk' if self.config.passthrough_reverb else 'normal_talk' if self.config.passthrough else '')
        inst, ref = self._read_song_frames(frames)
        ig = float(self.config.inst_gain or 0.77)
        if mode in ('normal_talk', 'reverb_talk'):
            gain = float(self.config.passthrough_gain or 1.0)
            boosted = np.clip(mono_in * gain, -1.0, 1.0)
            if mode == 'reverb_talk':
                boosted[:, 0] = self._reverb_mono(boosted)
            if self._inst_data is not None:
                return np.clip(boosted + inst.reshape(-1, 1) * ig, -1.0, 1.0)
            return boosted
        if mode == 'ai_sing':
            mg = float(self.config.mic_gain or 0.77)
            mix = inst.reshape(-1, 1) * ig + ref.reshape(-1, 1) * mg
        elif mode == 'ai_follow':
            gate = self._smooth_follow_gate()
            mg = float(self.config.mic_gain or 0.77)
            rg = float(self.config.ref_vocal_gain or 0.0)
            vocal = ref.reshape(-1, 1)
            mix = inst.reshape(-1, 1) * ig + vocal * gate * mg + vocal * rg
        else:
            return np.zeros((frames, 1), dtype=np.float32)
        peak = float(np.max(np.abs(mix))) if mix.size else 0.0
        if peak > 1.0:
            mix = mix / peak
        return mix.astype(np.float32)

    def _close_stream(self, stream=None):
        if stream is None:
            with self._lock:
                stream = self._stream
                self._stream = None
        if stream is None:
            return
        try:
            stream.abort()
            stream.close()
        except Exception:
            logger.debug('stream close: %s', traceback.format_exc())

    def _callback(self, indata, outdata, frames, time_info, status):
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
            lat = None
            try:
                if time_info is not None:
                    lat = float(time_info.outputBufferDacTime) - float(time_info.currentTime)
            except Exception:
                lat = None
            if lat is not None and lat == lat and 0.005 <= float(lat) <= 0.22:
                self._out_latency = 0.65 * self._out_latency + 0.35 * float(lat)
            mode = self.config.playback_mode
            if mode in PLAYBACK_MODES or self.config.passthrough:
                self.output_ring.write(self._mix_output(frames, mono_in))
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
                old = self._stream
                self._stream = None
            try:
                self._close_stream(old)
                with self._lock:
                    if not self._running:
                        break
                    self._open_stream()
                    self._stats['restarts'] += 1
                    self._error = None
                logger.warning('audio stream restarted after device/error event')
            except Exception as exc:
                with self._lock:
                    self._error = str(exc)
                self._reconnect = True
                logger.error('audio reconnect failed: %s', exc)

    def push_output(self, frames: np.ndarray) -> int:
        return self.output_ring.write(frames)

    def read_input(self, frame_count: int) -> np.ndarray:
        return self.input_ring.read(frame_count)

    def peek_input(self, frame_count: int) -> np.ndarray:
        return self.input_ring.peek(frame_count)
