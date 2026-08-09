"""AI 跟唱：伴奏 + 预渲染 AI 人声（converted_vocal）按时间轴播放，麦克风 VAD 门控开关。"""

import logging
import threading
import time
import traceback
from pathlib import Path

import librosa
import numpy as np
import sounddevice as sd
import soundfile as sf

from app.audio.devices import pick_voicemeeter_defaults
from app.audio.ring_buffer import RingBuffer
from app.config_store import ConfigStore
from app.events import BusMessage, ModuleId, SignalType
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client.pitchfix')


class PitchFollowService:
    """Phase 1：VAD 门控 AI 人声（对标声迹）。Phase 2 可选接入麦实时修音，见 开发大纲 §任务9。"""

    def __init__(self, scheduler=None, config=None):
        self.scheduler = scheduler or AppScheduler.instance()
        self.config_store = config or ConfigStore().load()
        self._inst = None
        self._sr = 48000
        self._pos = 0
        self._pos_lock = threading.Lock()
        self._stream = None
        self._running = False
        self._worker = None
        self._in_ring = None
        self._duration = 0.0
        self._title = ''
        self._ref_vocal = None
        self._voice_off_at = None
        self._gate_lock = threading.Lock()
        self._voice_gate = 0.0
        self._hook = False
        self._cfg = {}
        self._cache_key = ''
        self._vad_above = 0
        self._clock_origin_frame = 0
        self._clock_origin_mono = 0.0
        self._out_latency = 0.05
        self._clock_active = False

    def _publish(self, action, **payload):
        self.scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.RVC, {'action': action, **payload}))

    def _load_cfg(self):
        pf = self.config_store.get('pitchfix', {}) or {}
        audio = self.config_store.get('audio', {}) or {}
        return {
            'sr': int(audio.get('sample_rate', 48000)),
            'block_ms': int(pf.get('block_ms', audio.get('block_ms', 100))),
            'inst_gain': float(pf.get('inst_gain', 0.77)),
            'mic_gain': float(pf.get('mic_gain', 0.77)),
            'ref_vocal_gain': float(pf.get('ref_vocal_gain', 0.0)),
            'follow_threshold': float(pf.get('follow_threshold', 75)),
            'follow_attenuation': min(0.2, max(0.1, float(pf.get('follow_attenuation', 0.1)))),
            'input_device': audio.get('input_device'),
            'output_device': audio.get('output_device'),
        }

    def apply_settings(self, **kwargs):
        if not self._cfg:
            return self
        for key in ('inst_gain', 'mic_gain', 'ref_vocal_gain', 'follow_threshold', 'follow_attenuation'):
            if key in kwargs and kwargs[key] is not None:
                val = float(kwargs[key])
                if key == 'follow_attenuation':
                    val = min(0.2, max(0.1, val))
                self._cfg[key] = val
        return self

    @property
    def position(self):
        """墙钟外推当前可听位置；允许略超过已写样本，避免回调抖动时歌词/进度卡死。"""
        with self._pos_lock:
            if not self._sr:
                return 0.0
            written = self._pos / self._sr
            if not self._running or not self._clock_active:
                return written
            elapsed = time.monotonic() - self._clock_origin_mono
            est = self._clock_origin_frame / self._sr + elapsed - self._out_latency
            hi = min(self._duration, written + 0.4)
            return max(0.0, min(est, hi))

    @property
    def duration(self):
        return self._duration

    @property
    def running(self):
        return self._running

    def seek(self, seconds: float):
        with self._pos_lock:
            if self._inst is None or not self._sr:
                return self
            sec = max(0.0, min(float(seconds), self._duration))
            self._pos = int(sec * self._sr)
            self._clock_origin_frame = self._pos
            self._clock_origin_mono = time.monotonic()
            self._clock_active = bool(self._running)
        return self

    def _load_wav_mono(self, path, sr):
        data, file_sr = sf.read(path, dtype='float32', always_2d=True)
        if file_sr != sr:
            data = librosa.resample(data.T, orig_sr=file_sr, target_sr=sr).T
        if data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        return data

    def preload(self, song: dict):
        inst_path = song.get('instrumental_path') or ''
        ref_path = song.get('vocal_path') or song.get('converted_vocal_path') or ''
        if not inst_path or not ref_path or not Path(inst_path).is_file() or not Path(ref_path).is_file():
            return self
        key = '%s|%s' % (inst_path, ref_path)
        if key == self._cache_key and self._inst is not None:
            return self
        cfg = self._load_cfg()
        sr = cfg['sr']
        self._cfg = cfg
        self._sr = sr
        self._inst = self._load_wav_mono(inst_path, sr)
        self._ref_vocal = self._load_wav_mono(ref_path, sr)
        self._duration = len(self._inst) / sr
        self._title = song.get('title') or Path(inst_path).stem.replace('_instrumental', '')
        self._cache_key = key
        return self

    def assets_ready(self, song: dict) -> bool:
        inst_path = song.get('instrumental_path') or ''
        ref_path = song.get('vocal_path') or song.get('converted_vocal_path') or ''
        key = '%s|%s' % (inst_path, ref_path)
        return bool(inst_path and ref_path and key == self._cache_key and self._inst is not None)

    def start(self, song: dict, seek_sec: float = 0.0):
        if self._running:
            if seek_sec > 0:
                self.seek(seek_sec)
            return self
        inst_path = song.get('instrumental_path') or ''
        ref_path = song.get('vocal_path') or song.get('converted_vocal_path') or ''
        if not inst_path or not Path(inst_path).is_file():
            raise FileNotFoundError('缺少伴奏 instrumental.wav，请先离线做歌')
        if not ref_path or not Path(ref_path).is_file():
            raise FileNotFoundError('缺少 AI 人声 converted_vocal.wav，请先离线做歌')
        key = '%s|%s' % (inst_path, ref_path)
        self._cfg = self._load_cfg()
        sr = self._cfg['sr']
        self._sr = sr
        self._voice_off_at = None
        with self._gate_lock:
            self._voice_gate = 0.0
        self._vad_above = 0
        if key != self._cache_key or self._inst is None:
            self._inst = self._load_wav_mono(inst_path, sr)
            self._ref_vocal = self._load_wav_mono(ref_path, sr)
            self._duration = len(self._inst) / sr
            self._title = song.get('title') or Path(inst_path).stem.replace('_instrumental', '')
            self._cache_key = key
        self._pos = 0
        if seek_sec > 0:
            self.seek(seek_sec)
        else:
            with self._pos_lock:
                self._clock_origin_frame = 0
                self._clock_origin_mono = time.monotonic()
                self._clock_active = False
        block = max(1, int(sr * max(50, min(500, self._cfg['block_ms'])) / 1000))
        cap = block * 8
        self._in_ring = RingBuffer(cap, 1)
        in_dev = self._cfg['input_device']
        out_dev = self._cfg['output_device']
        if in_dev is None or out_dev is None:
            in_dev, out_dev = pick_voicemeeter_defaults()
        if in_dev is None or out_dev is None:
            raise RuntimeError('未找到音频输入/输出设备')
        self._running = True
        self._stream = sd.Stream(
            device=(in_dev, out_dev),
            samplerate=sr,
            blocksize=block,
            channels=1,
            dtype='float32',
            callback=self._callback,
        )
        self._stream.start()
        self._worker = threading.Thread(target=self._worker_loop, name='pitchfix-vad', daemon=True)
        self.scheduler.register_thread('pitchfix-vad', self._worker)
        self._worker.start()
        if not self._hook:
            self.scheduler.add_shutdown_hook(self.stop)
            self._hook = True
        logger.info('ai follow vad started title=%s duration=%.1fs pos=%.2fs', self._title, self._duration, self.position)
        return self

    def _playback_chunks(self, frames: int, out_latency: float | None = None):
        now = time.monotonic()
        with self._pos_lock:
            start = self._pos
            end = min(start + frames, len(self._inst))
            got = max(0, end - start)
            self._pos = end
            finished = end >= len(self._inst)
            self._clock_origin_frame = start
            self._clock_origin_mono = now
            if out_latency is not None and out_latency == out_latency:
                lat = float(out_latency)
                # WASAPI/Voicemeeter 偶发离谱 latency，会把播放头按死在块尾
                if 0.005 <= lat <= 0.22:
                    self._out_latency = 0.65 * self._out_latency + 0.35 * lat
            self._clock_active = True
        inst = np.zeros((frames, 1), dtype=np.float32)
        ref = np.zeros((frames, 1), dtype=np.float32)
        if got > 0:
            inst[:got, 0] = self._inst[start:end, 0]
            if self._ref_vocal is not None and start < len(self._ref_vocal):
                ref_end = min(end, len(self._ref_vocal))
                ref_got = max(0, ref_end - start)
                if ref_got > 0:
                    ref[:ref_got, 0] = self._ref_vocal[start:ref_end, 0]
        return inst, ref, finished

    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            logger.debug('pitchfix stream status: %s', status)
        lat = None
        try:
            if time_info is not None:
                lat = float(time_info.outputBufferDacTime) - float(time_info.currentTime)
        except Exception:
            lat = None
        try:
            mic = np.asarray(indata, dtype=np.float32).reshape(-1, 1)
            self._in_ring.write(mic)
            inst, ref, finished = self._playback_chunks(frames, out_latency=lat)
            with self._gate_lock:
                gate = self._voice_gate
            cfg = self._cfg
            ai_vocal = ref * gate * cfg['mic_gain']
            monitor = ref * cfg.get('ref_vocal_gain', 0.0)
            mix = inst * cfg['inst_gain'] + ai_vocal + monitor
            peak = float(np.max(np.abs(mix))) if mix.size else 0.0
            if peak > 1.0:
                mix = mix / peak
            outdata[:] = mix
            if finished and self._running:
                self._running = False
                raise sd.CallbackStop()
        except sd.CallbackStop:
            raise
        except Exception:
            logger.error('pitchfix callback error:\n%s', traceback.format_exc())
            outdata.fill(0)

    def _worker_loop(self):
        block = self._stream.blocksize if self._stream else int(self._sr * 0.2)
        while self._running:
            try:
                if self._in_ring.available_frames() < block:
                    time.sleep(0.002)
                    continue
                mic = self._in_ring.read(block)[:, 0]
                thr = float(self._cfg.get('follow_threshold', 75))
                open_gate = max(0.001, (thr / 100.0) * 0.006)
                close_gate = open_gate * 0.35
                att = min(0.2, max(0.1, float(self._cfg.get('follow_attenuation', 0.1))))
                hangover = max(0.25, att * 2.5)
                mic_rms = float(np.sqrt(np.mean(mic * mic))) if mic.size else 0.0
                now = time.monotonic()
                if mic_rms >= open_gate:
                    self._vad_above = min(3, self._vad_above + 1)
                else:
                    self._vad_above = max(0, self._vad_above - 1)
                with self._gate_lock:
                    was_open = self._voice_gate >= 0.5
                in_grace = self._voice_off_at is not None and (now - self._voice_off_at) < hangover
                if was_open:
                    if mic_rms >= close_gate:
                        self._voice_off_at = None
                        active = True
                    else:
                        if self._voice_off_at is None:
                            self._voice_off_at = now
                        active = in_grace
                elif self._vad_above >= 2 or (in_grace and self._vad_above >= 1 and mic_rms >= open_gate):
                    self._voice_off_at = None
                    active = True
                else:
                    active = False
                    if not in_grace:
                        self._voice_off_at = None
                with self._gate_lock:
                    self._voice_gate = 1.0 if active else 0.0
            except Exception:
                logger.error('pitchfix vad worker error:\n%s', traceback.format_exc())
                time.sleep(0.02)

    def stop(self, keep_cache: bool = False, fast: bool = False):
        self._running = False
        with self._pos_lock:
            self._clock_active = False
        with self._gate_lock:
            self._voice_gate = 0.0
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=0.05 if fast else 2.0)
        self._worker = None
        try:
            self.scheduler.unregister_thread('pitchfix-vad')
        except Exception:
            pass
        try:
            self.scheduler.unregister_thread('pitchfix-worker')
        except Exception:
            pass
        self._in_ring = None
        self._vad_above = 0
        if not keep_cache:
            self._inst = None
            self._ref_vocal = None
            self._cache_key = ''
        self._pos = 0
        logger.info('ai follow stopped')
