"""AI 跟唱：伴奏 + 麦实时修音（参考 converted_vocal F0）。"""

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
from app.pitchfix.corrector import correct_toward_target, estimate_f0
from app.pitchfix.f0_curve import ReferenceF0Curve
from app.scheduler import AppScheduler

logger = logging.getLogger('rvc_client.pitchfix')


class PitchFollowService:
    def __init__(self, scheduler=None, config=None):
        self.scheduler = scheduler or AppScheduler.instance()
        self.config_store = config or ConfigStore().load()
        self._inst = None
        self._sr = 48000
        self._pos = 0
        self._pos_lock = threading.Lock()
        self._ref_f0 = None
        self._stream = None
        self._running = False
        self._worker = None
        self._in_ring = None
        self._vocal_ring = None
        self._duration = 0.0
        self._title = ''
        self._hook = False
        self._cfg = {}
        self._preparing = False

    @property
    def preparing(self):
        return self._preparing

    def _publish(self, action, **payload):
        self.scheduler.publish(BusMessage(SignalType.STATUS, ModuleId.RVC, {'action': action, **payload}))

    def _load_cfg(self):
        pf = self.config_store.get('pitchfix', {}) or {}
        audio = self.config_store.get('audio', {}) or {}
        return {
            'sr': int(audio.get('sample_rate', 48000)),
            'block_ms': int(pf.get('block_ms', audio.get('block_ms', 200))),
            'strength': float(pf.get('strength', 0.85)),
            'inst_gain': float(pf.get('inst_gain', 0.85)),
            'mic_gain': float(pf.get('mic_gain', 1.0)),
            'f0_min': float(pf.get('f0_min', 50)),
            'f0_max': float(pf.get('f0_max', 1100)),
            'max_semitone': float(pf.get('max_semitone', 2.0)),
            'input_device': audio.get('input_device'),
            'output_device': audio.get('output_device'),
        }

    @property
    def position(self):
        with self._pos_lock:
            return self._pos / self._sr if self._sr else 0.0

    @property
    def duration(self):
        return self._duration

    @property
    def running(self):
        return self._running

    def _load_inst(self, path, sr):
        data, file_sr = sf.read(path, dtype='float32', always_2d=True)
        if file_sr != sr:
            data = librosa.resample(data.T, orig_sr=file_sr, target_sr=sr).T
        if data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        return data

    def start(self, song: dict):
        if self._running:
            return self
        inst_path = song.get('instrumental_path') or ''
        ref_path = song.get('vocal_path') or song.get('converted_vocal_path') or ''
        if not inst_path or not Path(inst_path).is_file():
            raise FileNotFoundError('缺少伴奏 instrumental.wav，请先离线做歌')
        if not ref_path or not Path(ref_path).is_file():
            raise FileNotFoundError('缺少参考人声 converted_vocal.wav，请先离线做歌')
        self._cfg = self._load_cfg()
        sr = self._cfg['sr']
        self._sr = sr
        self._inst = self._load_inst(inst_path, sr)
        self._duration = len(self._inst) / sr
        self._title = song.get('title') or Path(inst_path).stem.replace('_instrumental', '')
        self._pos = 0
        self._ref_f0 = ReferenceF0Curve.from_wav(
            ref_path, sr=sr, fmin=self._cfg['f0_min'], fmax=self._cfg['f0_max']
        )
        block = max(1, int(sr * max(100, min(500, self._cfg['block_ms'])) / 1000))
        cap = block * 8
        self._in_ring = RingBuffer(cap, 1)
        self._vocal_ring = RingBuffer(cap, 1)
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
        self._worker = threading.Thread(target=self._worker_loop, name='pitchfix-worker', daemon=True)
        self.scheduler.register_thread('pitchfix-worker', self._worker)
        self._worker.start()
        if not self._hook:
            self.scheduler.add_shutdown_hook(self.stop)
            self._hook = True
        logger.info('pitch follow started title=%s duration=%.1fs', self._title, self._duration)
        return self

    def _inst_chunk(self, frames: int):
        with self._pos_lock:
            start = self._pos
            end = min(start + frames, len(self._inst))
            chunk = np.zeros((frames, 1), dtype=np.float32)
            if start < len(self._inst):
                got = end - start
                chunk[:got, 0] = self._inst[start:end, 0]
            self._pos = end
            finished = end >= len(self._inst)
        return chunk, finished

    def _callback(self, indata, outdata, frames, time_info, status):
        del time_info
        if status:
            logger.debug('pitchfix stream status: %s', status)
        try:
            mic = np.asarray(indata, dtype=np.float32).reshape(-1, 1)
            self._in_ring.write(mic)
            inst, finished = self._inst_chunk(frames)
            vocal = self._vocal_ring.read(frames)
            mix = inst * self._cfg['inst_gain'] + vocal * self._cfg['mic_gain']
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
        sr = self._sr
        block = self._stream.blocksize if self._stream else int(sr * 0.2)
        last_f0 = 0.0
        f0_counter = 0
        while self._running:
            try:
                if self._in_ring.available_frames() < block:
                    time.sleep(0.002)
                    continue
                backlog = self._in_ring.available_frames()
                mic = self._in_ring.read(block)[:, 0]
                if backlog >= block * 5:
                    self._vocal_ring.write(mic.reshape(-1, 1))
                    continue
                t = self.position
                target = self._ref_f0.at_time(t) if self._ref_f0 else 0.0
                if target <= 0:
                    out = mic
                else:
                    f0_counter = (f0_counter + 1) % 3
                    if f0_counter == 0:
                        last_f0 = estimate_f0(mic, sr, self._cfg['f0_min'], self._cfg['f0_max'])
                    out = correct_toward_target(
                        mic, sr, last_f0, target,
                        strength=self._cfg['strength'],
                        max_semitone=self._cfg['max_semitone'],
                    )
                self._vocal_ring.write(out.reshape(-1, 1))
            except Exception:
                logger.error('pitchfix worker error:\n%s', traceback.format_exc())
                time.sleep(0.02)

    def stop(self):
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._worker = None
        self.scheduler.unregister_thread('pitchfix-worker')
        self._in_ring = None
        self._vocal_ring = None
        self._inst = None
        self._ref_f0 = None
        self._pos = 0
        logger.info('pitch follow stopped')
