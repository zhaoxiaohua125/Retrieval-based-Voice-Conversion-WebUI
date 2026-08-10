"""离线 AI 翻唱流水线：MSST 多阶段分离 + RVC 转换 + 可选混音。

复用上游 ``tools/song_cover.py`` 的 GPU 释放/混音逻辑，复用 ``app/msst`` 分离流水线。
不修改上游模块源码。
"""

import logging
import os
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf

from app.msst.pipeline import MsstSongSeparator
from app.rvc.types import OfflineCoverResult, RvcInferParams
from app.rvc.upstream_imports import pymss_write_audio, song_cover_tools


logger = logging.getLogger('rvc_client')

VC_CHUNK_SEC = 45


def _audio_duration_sec(path):
    try:
        return float(sf.info(path).duration)
    except Exception:
        return 0.0


def _vc_infer(vc, vocal_path, params, cancel_check=None):
    """长音频分段 RVC，避免 RMVPE/F0 整段推理 OOM。"""
    if cancel_check and cancel_check():
        return '用户取消', (None, None)
    duration = _audio_duration_sec(vocal_path)
    if duration <= VC_CHUNK_SEC:
        return vc.vc_single(
            int(params.speaker_id),
            vocal_path,
            int(params.f0_up_key),
            params.f0_method,
            params.file_index,
            float(params.index_rate),
            int(params.resample_sr),
            float(params.rms_mix_rate),
            float(params.protect),
        )

    data, sr = sf.read(vocal_path, dtype='float32', always_2d=False)
    if getattr(data, 'ndim', 1) > 1:
        data = data.mean(axis=1)
    chunk_n = int(VC_CHUNK_SEC * sr)
    temp_root = Path(os.environ.get('TEMP', 'TEMP'))
    temp_root.mkdir(parents=True, exist_ok=True)
    outputs = []
    tgt_sr = None
    last_info = ''
    total = max(1, (len(data) + chunk_n - 1) // chunk_n)
    for i in range(total):
        if cancel_check and cancel_check():
            return '用户取消', (None, None)
        start = i * chunk_n
        end = min(start + chunk_n, len(data))
        chunk_path = temp_root / ('offline_rvc_%s_%d.wav' % (Path(vocal_path).stem, i))
        sf.write(str(chunk_path), data[start:end], sr)
        try:
            _clear_cuda_cache()
            info, opt = vc.vc_single(
                int(params.speaker_id),
                str(chunk_path),
                int(params.f0_up_key),
                params.f0_method,
                params.file_index,
                float(params.index_rate),
                int(params.resample_sr),
                float(params.rms_mix_rate),
                float(params.protect),
            )
            last_info = str(info)
            if not opt or opt[0] is None or opt[1] is None:
                return info, (None, None)
            cs, audio = opt
            tgt_sr = cs
            outputs.append(np.asarray(audio, dtype=np.float32))
        finally:
            try:
                chunk_path.unlink(missing_ok=True)
            except OSError:
                pass
    if not outputs:
        return last_info, (None, None)
    return last_info, (tgt_sr, np.concatenate(outputs))


def _clear_cuda_cache():
    """MSST 分离前尽量释放主进程 CUDA 缓存。"""
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, 'ipc_collect'):
                torch.cuda.ipc_collect()
    except Exception:
        logger.debug('cuda cache clear skipped', exc_info=True)


class OfflineSongPipeline:
    """离线做歌：普通/强力 MSST 预设 → RVC 干声转换 → 四轨 + 成品。"""

    def __init__(self, work_root=None, msst_keep_work=False):
        self.msst = MsstSongSeparator(work_root=work_root, keep_work=msst_keep_work)
        self._cancel_requested = False
        self._f0_proc = {}

    def cancel(self):
        """取消 MSST 分离与 RVC 分段推理。"""
        self._cancel_requested = True
        proc = self._f0_proc.get('proc')
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                logger.debug('f0 proc terminate failed', exc_info=True)
        return self.msst.cancel()

    def _is_cancelled(self):
        return self._cancel_requested or self.msst._cancel_requested

    def run(
        self,
        model_sid,
        input_audio_path,
        vc=None,
        preset_id='normal',
        output_dir='opt',
        rvc_params=None,
        mix_cover=True,
        vocal_gain=1.0,
        inst_gain=1.0,
        output_format='wav',
        event_callback=None,
    ):
        """执行完整离线翻唱。

        Args:
            model_sid: 模型文件名（weights 目录下 .pth）。
            input_audio_path: 整曲输入路径。
            vc: 可选，已创建的 VC 实例；默认 None 表示 MSST 完成后再加载（推荐，省显存）。
            preset_id: ``normal`` / ``powerful``。
            output_dir: 输出目录（持久化，非临时目录）。
            rvc_params: RVC 推理参数。
            mix_cover: 是否合成 ``{stem}_cover.*`` 成品。
            event_callback: 进度事件回调。
        """
        params = rvc_params or RvcInferParams()
        input_audio_path = str(input_audio_path or '').strip()
        output_dir = str(output_dir or 'opt').strip() or 'opt'
        model_sid = str(model_sid or '').strip()
        output_format = (output_format or 'wav').lower()
        if output_format not in {'wav', 'flac', 'mp3', 'm4a'}:
            output_format = 'wav'
        lines = []
        moved = []
        restore_vc_gpu = None
        vc_owned = vc is None

        def emit(event):
            if event_callback is not None:
                event_callback(event)

        if not model_sid:
            yield {'event': 'failed', 'message': '请指定 RVC 模型 model_sid'}
            return
        if not input_audio_path or not os.path.isfile(input_audio_path):
            yield {'event': 'failed', 'message': '输入音频不存在'}
            return

        stem = Path(input_audio_path).stem
        os.makedirs(output_dir, exist_ok=True)
        self._cancel_requested = False
        self.msst._cancel_requested = False
        separation_result = None
        release_vc_gpu, restore_vc_gpu, to_float_audio, mix_vocal_instrumental = song_cover_tools()

        try:
            emit({'event': 'phase', 'phase': 'msst', 'percent': 5, 'message': '正在 MSST 多阶段分离…'})
            logger.info('offline msst start preset=%s input=%s', preset_id, input_audio_path)
            lines.append('MSST 预设：%s' % preset_id)
            if vc is not None and vc.net_g is not None:
                moved = release_vc_gpu(vc)
            else:
                _clear_cuda_cache()

            def on_msst(event):
                event = dict(event or {})
                if event.get('event') == 'stage_start':
                    idx = int(event.get('stage_index') or 1)
                    total = int(event.get('stage_total') or 1)
                    percent = 5.0 + (idx - 1) / max(total, 1) * 65.0
                    emit({'event': 'progress', 'phase': 'msst', 'percent': percent, 'payload': event})
                elif event.get('event') == 'progress':
                    emit({'event': 'progress', 'phase': 'msst', 'percent': 50.0, 'payload': event})
                else:
                    emit({'event': 'msst', 'payload': event})

            for event in self.msst.run(
                input_audio_path,
                preset_id=preset_id,
                output_dir=output_dir,
                event_callback=on_msst,
            ):
                if event.get('event') == 'result':
                    separation_result = event['result']
                elif event.get('event') in {'failed', 'cancelled'}:
                    yield event
                    return

            if separation_result is None:
                yield {'event': 'failed', 'message': 'MSST 分离未返回结果'}
                return
            logger.info('offline msst done vocals=%s', separation_result.vocals_noreverb_path)

            lines.append('原唱人声：%s' % separation_result.vocals_path)
            lines.append('伴奏：%s' % separation_result.instrumental_path)
            lines.append('去混响干声：%s' % separation_result.vocals_noreverb_path)
            if separation_result.harmony_path:
                lines.append('和声：%s' % separation_result.harmony_path)

            if self._is_cancelled():
                yield {'event': 'cancelled', 'message': '用户已取消制作'}
                return

            emit({'event': 'phase', 'phase': 'rvc', 'percent': 78, 'message': '正在进行 RVC 音色转换…'})
            logger.info('offline rvc start model=%s', model_sid)
            _clear_cuda_cache()
            vocal_dur = _audio_duration_sec(separation_result.vocals_noreverb_path)
            if vocal_dur > VC_CHUNK_SEC:
                emit({'event': 'progress', 'phase': 'rvc', 'message': '长歌曲（%.0fs）将分段推理…' % vocal_dur})
                lines.append('长歌曲分段推理：%.1fs / %ds 每段' % (vocal_dur, VC_CHUNK_SEC))
            if vc is None or vc.net_g is None:
                from app.rvc.vc_context import create_vc, load_voice_model
                vc, _ = create_vc()
                load_voice_model(vc, model_sid)
                vc_owned = True
            elif moved:
                restore_vc_gpu(vc, moved)
                moved = []

            info, opt = _vc_infer(vc, separation_result.vocals_noreverb_path, params, cancel_check=self._is_cancelled)
            if self._is_cancelled():
                yield {'event': 'cancelled', 'message': '用户已取消制作'}
                return
            if not opt or opt[0] is None or opt[1] is None:
                detail = str(info)
                if vocal_dur > VC_CHUNK_SEC and 'CUDA out of memory' not in detail:
                    detail = '%s\n（歌曲时长 %.0fs，若仍失败可尝试降低 index_rate 或换 pm 算法）' % (detail, vocal_dur)
                logger.error('RVC failed: %s', detail)
                yield {'event': 'failed', 'message': 'RVC 转换失败', 'detail': detail}
                return

            tgt_sr, vocal_audio = opt
            converted_vocal_path = os.path.join(output_dir, '%s_converted_vocal.wav' % stem)
            sf.write(converted_vocal_path, to_float_audio(vocal_audio), tgt_sr)
            lines.append(str(info))
            lines.append('AI 人声：%s' % converted_vocal_path)
            logger.info('offline rvc done vocal=%s', converted_vocal_path)

            cover_path = None
            if mix_cover:
                if self._is_cancelled():
                    yield {'event': 'cancelled', 'message': '用户已取消制作'}
                    return
                emit({'event': 'phase', 'phase': 'mix', 'percent': 92, 'message': '正在合并人声与伴奏…'})
                write_audio = pymss_write_audio()

                mix_sr, mixed = mix_vocal_instrumental(
                    vocal_audio,
                    tgt_sr,
                    separation_result.instrumental_path,
                    vocal_gain=vocal_gain,
                    inst_gain=inst_gain,
                )
                cover_path = os.path.join(output_dir, '%s_cover.%s' % (stem, output_format))
                write_audio(cover_path, mixed, mix_sr, output_format)
                lines.append('成品：%s' % cover_path)

            if self._is_cancelled():
                yield {'event': 'cancelled', 'message': '用户已取消制作'}
                return
            # Phase 1 AI 跟唱为 VAD 门控，不依赖 F0 缓存；Phase 2 修音再取消注释
            # emit({'event': 'phase', 'phase': 'mix', 'percent': 96, 'message': '正在生成 AI 跟唱参考旋律…'})
            # from app.pitchfix.f0_curve import build_f0_cache_isolated, f0_cache_path
            # try:
            #     build_f0_cache_isolated(
            #         converted_vocal_path,
            #         cancel_check=self._is_cancelled,
            #         proc_holder=self._f0_proc,
            #     )
            #     f0_path = f0_cache_path(converted_vocal_path)
            #     lines.append('跟唱 F0 缓存：%s' % f0_path)
            #     logger.info('offline pitchfix f0 cache=%s', f0_path)
            # except Exception:
            #     logger.warning('offline F0 cache failed:\n%s', traceback.format_exc())
            #     lines.append('跟唱 F0 缓存失败（AI 跟唱首次启动会较慢）')

            result = OfflineCoverResult(
                preset_id=preset_id,
                source_path=input_audio_path,
                output_dir=output_dir,
                vocals_path=separation_result.vocals_path,
                instrumental_path=separation_result.instrumental_path,
                vocals_noreverb_path=separation_result.vocals_noreverb_path,
                converted_vocal_path=converted_vocal_path,
                cover_path=cover_path,
                harmony_path=separation_result.harmony_path,
                rvc_info=str(info),
                log_lines=lines,
            )
            emit({'event': 'phase', 'phase': 'done', 'percent': 100, 'message': '离线翻唱完成'})
            yield {'event': 'result', 'result': result, 'payload': result.as_dict()}
        except Exception:
            logger.error('offline pipeline failed:\n%s', traceback.format_exc())
            yield {'event': 'failed', 'message': traceback.format_exc()}
        finally:
            if moved and restore_vc_gpu and vc is not None:
                restore_vc_gpu(vc, moved)
            if vc_owned and vc is not None:
                _clear_cuda_cache()
