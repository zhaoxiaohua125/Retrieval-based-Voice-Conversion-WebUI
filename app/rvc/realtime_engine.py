"""实时 RVC 推理引擎（封装 infer.rtrvc.RVC + SOLA，逻辑来自 realtime_gui.py）。"""

import logging
import sys
import traceback
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torchaudio.transforms as tat

from app.rvc.realtime_config import RealtimeRvcConfig
from app.rvc.vc_context import ensure_rvc_runtime_env, resolve_index_for_model

logger = logging.getLogger('rvc_client.rvc.realtime')

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _create_upstream_config(project_root=None):
    ensure_rvc_runtime_env(project_root)
    argv_backup = sys.argv[:]
    try:
        sys.argv = [argv_backup[0]]
        from configs.config import Config
        return Config()
    finally:
        sys.argv = argv_backup


def _load_rvc_class():
    argv_backup = sys.argv[:]
    try:
        sys.argv = [argv_backup[0]]
        from infer import rtrvc
        return rtrvc.RVC
    finally:
        sys.argv = argv_backup


class RealtimeRvcEngine:
    """单模型实时推理：process_block 输入/输出均为 float32 单声道 PCM。"""

    def __init__(self, cfg: RealtimeRvcConfig | None = None, project_root=None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.cfg = cfg or RealtimeRvcConfig()
        self.config = _create_upstream_config(self.project_root)
        self.RVC = _load_rvc_class()
        self.rvc = None
        self.block_frame = 0
        self.block_frame_16k = 0
        self.samplerate = self.cfg.sample_rate
        self.zc = 0
        self._ready = False
        self._stats = {'blocks': 0, 'errors': 0, 'last_ms': 0.0}

    @property
    def stats(self):
        return dict(self._stats)

    @property
    def ready(self):
        return self._ready and self.rvc is not None

    def _model_paths(self, model_sid: str, index_path: str | None = None):
        env = ensure_rvc_runtime_env(self.project_root)
        pth = Path(env['weight_root']) / model_sid
        if not pth.is_file():
            raise FileNotFoundError('RVC 模型不存在: %s' % pth)
        idx = index_path if index_path is not None else self.cfg.index_path
        if not idx:
            idx = resolve_index_for_model(model_sid, self.project_root) or ''
        return str(pth), idx

    def load_model(self, model_sid: str, index_path: str | None = None, last_engine: 'RealtimeRvcEngine | None' = None):
        """加载或热切换模型（复用 HuBERT/RMVPE 权重）。"""
        pth_path, idx_path = self._model_paths(model_sid, index_path)
        last_rvc = last_engine.rvc if last_engine and last_engine.rvc is not None else None
        if last_engine is not None and last_engine is not self and last_rvc is not None:
            last_rvc = last_rvc
        elif hasattr(self, 'rvc') and self.rvc is not None:
            last_rvc = self.rvc
        self.rvc = self.RVC(
            self.cfg.pitch,
            self.cfg.formant,
            pth_path,
            idx_path,
            self.cfg.index_rate,
            self.config,
            last_rvc,
        )
        self.cfg.model_sid = model_sid
        self.cfg.index_path = idx_path
        return self

    def start(self, sample_rate: int | None = None):
        """按 realtime_gui.start_vc 初始化缓冲与 resampler。"""
        if self.rvc is None:
            raise RuntimeError('请先 load_model')
        import time as _time

        t0 = _time.perf_counter()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.samplerate = int(
            self.rvc.tgt_sr if self.cfg.sr_type == 'sr_model' else (sample_rate or self.cfg.sample_rate)
        )
        self.cfg.sample_rate = self.samplerate
        self.zc = self.samplerate // 100
        self.block_frame = int(np.round(self.cfg.block_time * self.samplerate / self.zc)) * self.zc
        self.block_frame_16k = 160 * self.block_frame // self.zc
        crossfade_frame = int(np.round(self.cfg.crossfade_time * self.samplerate / self.zc)) * self.zc
        self.sola_buffer_frame = min(crossfade_frame, 4 * self.zc)
        self.sola_search_frame = self.zc
        extra_frame = int(np.round(self.cfg.extra_time * self.samplerate / self.zc)) * self.zc
        dev = self.config.device
        self.input_wav = torch.zeros(
            extra_frame + crossfade_frame + self.sola_search_frame + self.block_frame,
            device=dev,
            dtype=torch.float32,
        )
        self.input_wav_res = torch.zeros(160 * self.input_wav.shape[0] // self.zc, device=dev, dtype=torch.float32)
        self.sola_buffer = torch.zeros(self.sola_buffer_frame, device=dev, dtype=torch.float32)
        self.sola_den_kernel = torch.ones(1, 1, self.sola_buffer_frame, device=dev, dtype=torch.float32)
        self.skip_head = extra_frame // self.zc
        self.return_length = (self.block_frame + self.sola_buffer_frame + self.sola_search_frame) // self.zc
        self.fade_in_window = (
            torch.sin(
                0.5 * np.pi * torch.linspace(0.0, 1.0, steps=self.sola_buffer_frame, device=dev, dtype=torch.float32)
            )
            ** 2
        )
        self.fade_out_window = 1 - self.fade_in_window
        self.resampler = tat.Resample(orig_freq=self.samplerate, new_freq=16000, dtype=torch.float32).to(dev)
        if self.rvc.tgt_sr != self.samplerate:
            self.resampler2 = tat.Resample(
                orig_freq=self.rvc.tgt_sr, new_freq=self.samplerate, dtype=torch.float32
            ).to(dev)
        else:
            self.resampler2 = None
        self._ready = True
        self._stats['last_ms'] = (_time.perf_counter() - t0) * 1000
        logger.info(
            'realtime engine ready model=%s sr=%s block=%s',
            self.cfg.model_sid,
            self.samplerate,
            self.block_frame,
        )
        return self

    def stop(self):
        self._ready = False
        return self

    def update_params(self, pitch: int | None = None, formant: float | None = None, index_rate: float | None = None):
        if self.rvc is None:
            return
        if pitch is not None:
            self.cfg.pitch = pitch
            self.rvc.change_key(pitch)
        if formant is not None:
            self.cfg.formant = formant
            self.rvc.change_formant(formant)
        if index_rate is not None:
            self.cfg.index_rate = index_rate
            self.rvc.change_index_rate(index_rate)

    def process_block(self, indata: np.ndarray) -> np.ndarray:
        """处理一块输入 PCM，返回等长输出（float32 mono）。"""
        import time as _time

        if not self.ready:
            raise RuntimeError('engine not started')
        t0 = _time.perf_counter()
        try:
            mono = np.asarray(indata, dtype=np.float32)
            if mono.ndim == 2:
                mono = mono.mean(axis=1)
            if len(mono) < self.block_frame:
                mono = np.pad(mono, (0, self.block_frame - len(mono)))
            else:
                mono = mono[: self.block_frame]
            self.input_wav[: -self.block_frame] = self.input_wav[self.block_frame :].clone()
            self.input_wav[-len(mono) :] = torch.from_numpy(mono).to(self.config.device)
            resample_input = self.input_wav[-len(mono) - 2 * self.zc :]
            resampled = self.resampler(resample_input)
            self.input_wav_res[-160 * (len(mono) // self.zc + 1) :] = resampled[160:]
            infer_wav = self.rvc.infer(
                self.input_wav_res,
                self.block_frame_16k,
                self.skip_head,
                self.return_length,
                self.cfg.f0_method,
            )
            if self.resampler2 is not None:
                infer_wav = self.resampler2(infer_wav)
            conv_input = infer_wav[None, None, : self.sola_buffer_frame + self.sola_search_frame]
            cor_nom = F.conv1d(conv_input, self.sola_buffer[None, None, :])
            cor_den = torch.sqrt(F.conv1d(conv_input**2, self.sola_den_kernel) + 1e-8)
            if sys.platform == 'darwin':
                _, sola_offset = torch.max(cor_nom[0, 0] / cor_den[0, 0])
                sola_offset = sola_offset.item()
            else:
                sola_offset = torch.argmax(cor_nom[0, 0] / cor_den[0, 0])
            infer_wav = infer_wav[sola_offset:]
            infer_wav[: self.sola_buffer_frame] *= self.fade_in_window
            infer_wav[: self.sola_buffer_frame] += self.sola_buffer * self.fade_out_window
            self.sola_buffer[:] = infer_wav[self.block_frame : self.block_frame + self.sola_buffer_frame]
            out = infer_wav[: self.block_frame].detach().cpu().numpy().astype(np.float32)
            self._stats['blocks'] += 1
            self._stats['last_ms'] = (_time.perf_counter() - t0) * 1000
            return out
        except Exception:
            self._stats['errors'] += 1
            logger.error('process_block failed:\n%s', traceback.format_exc())
            raise


class RealtimeModelPool:
    """多模型预加载与无断音热切换（共享 HuBERT）。"""

    def __init__(self, cfg: RealtimeRvcConfig | None = None, project_root=None):
        self.cfg = cfg or RealtimeRvcConfig()
        self.project_root = Path(project_root or PROJECT_ROOT)
        self._engines: dict[str, RealtimeRvcEngine] = {}
        self._active_sid: str | None = None

    @property
    def active_sid(self):
        return self._active_sid

    @property
    def active_engine(self) -> RealtimeRvcEngine | None:
        if not self._active_sid:
            return None
        return self._engines.get(self._active_sid)

    def preload(self, model_sid: str, index_path: str | None = None) -> RealtimeRvcEngine:
        if model_sid in self._engines:
            return self._engines[model_sid]
        last = self.active_engine
        engine = RealtimeRvcEngine(self.cfg, self.project_root)
        engine.load_model(model_sid, index_path=index_path, last_engine=last)
        self._engines[model_sid] = engine
        if self._active_sid is None:
            self._active_sid = model_sid
        return engine

    def switch(self, model_sid: str, index_path: str | None = None) -> RealtimeRvcEngine:
        last = self.active_engine
        if model_sid not in self._engines:
            self.preload(model_sid, index_path=index_path)
        engine = self._engines[model_sid]
        if last is not None and last is not engine and last.ready:
            if not engine.ready:
                engine.start(sample_rate=last.samplerate)
        elif not engine.ready:
            engine.start(sample_rate=self.cfg.sample_rate)
        self._active_sid = model_sid
        return engine

    def list_loaded(self):
        return list(self._engines.keys())
