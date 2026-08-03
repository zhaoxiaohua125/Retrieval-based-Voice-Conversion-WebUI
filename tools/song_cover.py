import logging
import os
import shutil
import traceback
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

from configs.config import Config
from i18n.i18n import I18nAuto
from tools.pymss_webui import (
    MODEL_SPECS,
    _write_audio,
    clean_path,
    pymss_separate,
    render_pymss_progress,
    resolve_model,
)


logger = logging.getLogger(__name__)
i18n = I18nAuto()
config = Config()

SONG_COVER_MODEL_CHOICES = [
    spec.label
    for spec in MODEL_SPECS
    if spec.desired_suffix in ('vocals', 'main_vocal')
]


def _to_float_audio(audio):
    audio = np.asarray(audio)
    if np.issubdtype(audio.dtype, np.integer):
        return audio.astype(np.float32) / 32768.0
    audio = audio.astype(np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        return audio / (32768.0 if peak > 2.0 else peak)
    return audio


def mix_vocal_instrumental(vocal, vocal_sr, instrumental_path, vocal_gain=1.0, inst_gain=1.0):
    inst, inst_sr = sf.read(instrumental_path, always_2d=True)
    vocal = _to_float_audio(vocal).reshape(-1)
    inst = _to_float_audio(inst)
    if inst.ndim == 1:
        inst = inst.reshape(-1, 1)
    if int(vocal_sr) != int(inst_sr):
        vocal = librosa.resample(vocal, orig_sr=int(vocal_sr), target_sr=int(inst_sr))
    channels = inst.shape[1]
    vocal_st = np.stack([vocal] * channels, axis=1) if channels > 1 else vocal.reshape(-1, 1)
    n = max(len(vocal_st), len(inst))
    if len(vocal_st) < n:
        vocal_st = np.pad(vocal_st, ((0, n - len(vocal_st)), (0, 0)))
    else:
        vocal_st = vocal_st[:n]
    if len(inst) < n:
        inst = np.pad(inst, ((0, n - len(inst)), (0, 0)))
    else:
        inst = inst[:n]
    mixed = vocal_st * float(vocal_gain) + inst * float(inst_gain)
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 1.0:
        mixed = mixed / peak * 0.99
    return int(inst_sr), mixed


def cover_status(state, detail='', lines=None):
    text = ['【%s】' % i18n('一键翻唱'), '%s：%s' % (i18n('状态'), i18n(state))]
    if detail:
        text.extend(['', str(detail).strip()])
    if lines:
        text.extend(['', '\n'.join(lines)])
    return '\n'.join(text)


def _empty_tracks():
    return None, None, None, None


def _release_vc_gpu(vc):
    moved = []
    for name in ('net_g', 'hubert_model'):
        model = getattr(vc, name, None)
        if model is None:
            continue
        try:
            model.to('cpu')
            moved.append(name)
        except Exception:
            logger.exception('Failed to move %s to CPU before separation', name)
    pipeline = getattr(vc, 'pipeline', None)
    if pipeline is not None:
        for name in ('model_rmvpe', 'model_fcpe'):
            model = getattr(pipeline, name, None)
            if model is None:
                continue
            target = getattr(model, 'model', model)
            try:
                if hasattr(target, 'to'):
                    target.to('cpu')
                    moved.append('pipeline.%s' % name)
            except Exception:
                logger.exception('Failed to move %s to CPU before separation', name)
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            logger.exception('Failed to clear CUDA cache before separation')
    return moved


def _restore_vc_gpu(vc, moved):
    device = vc.config.device
    for name in moved:
        if name.startswith('pipeline.'):
            pipeline = getattr(vc, 'pipeline', None)
            if pipeline is None:
                continue
            attr = name.split('.', 1)[1]
            model = getattr(pipeline, attr, None)
            target = getattr(model, 'model', model) if model is not None else None
            if target is None or not hasattr(target, 'to'):
                continue
            try:
                target.to(device)
            except Exception:
                logger.exception('Failed to restore %s to %s', name, device)
            continue
        model = getattr(vc, name, None)
        if model is None:
            continue
        try:
            model.to(device)
        except Exception:
            logger.exception('Failed to restore %s to %s', name, device)


def run_song_cover(
    vc,
    sid,
    input_audio_path,
    model_name,
    f0_up_key,
    f0_method,
    file_index,
    index_rate,
    resample_sr,
    rms_mix_rate,
    protect,
    vocal_gain,
    inst_gain,
    output_format,
    opt_root,
    keep_stems,
):
    lines = []
    progress = {'percent': 0.0, 'label': i18n('等待开始'), 'state': 'idle'}
    moved = []

    def progress_html():
        return render_pymss_progress(**progress)

    def set_progress(percent, label, state='running'):
        progress.update({'percent': float(percent), 'label': label, 'state': state})

    def on_separate_event(event):
        event_type = event.get('event')
        file_count = max(1, int(event.get('file_count') or 1))
        file_index_no = max(1, int(event.get('file_index') or 1))
        message = str(event.get('message') or '')
        if event_type == 'progress':
            done = max(0.0, float(event.get('done') or 0))
            total = max(1.0, float(event.get('total') or 1))
            file_fraction = min(1.0, done / total)
            percent = 5.0 + ((file_index_no - 1 + file_fraction) / file_count) * 70.0
            set_progress(
                percent,
                '文件 %s/%s · %s · %.0f/%.0f 秒' % (
                    file_index_no,
                    file_count,
                    message or i18n('正在分离人声与伴奏…'),
                    done,
                    total,
                ),
            )
        elif event_type == 'file_start':
            set_progress(5.0 + (file_index_no - 1) / file_count * 70.0, message or i18n('正在分离人声与伴奏…'))
        elif event_type == 'file':
            set_progress(
                5.0 + file_index_no / file_count * 70.0,
                message.splitlines()[0] if message else i18n('正在分离人声与伴奏…'),
                'running' if event.get('ok') else 'failed',
            )
        elif event_type == 'done':
            set_progress(75.0, message or i18n('正在分离人声与伴奏…'), 'running')
        elif event_type in {'fatal', 'busy', 'cancelled'}:
            set_progress(progress['percent'], message.splitlines()[0] if message else progress['label'], 'failed')
        elif event_type in {'preparing', 'precision_attempt', 'status', 'retry_fp32'}:
            set_progress(max(progress['percent'], 3.0), message or progress['label'])

    try:
        if not input_audio_path:
            set_progress(0, i18n('请上传音频文件'), 'idle')
            yield cover_status('等待输入', i18n('请上传音频文件')), progress_html(), *_empty_tracks()
            return
        if vc.net_g is None:
            set_progress(0, i18n('请先选择推理音色'), 'idle')
            yield cover_status('等待输入', i18n('请先选择推理音色')), progress_html(), *_empty_tracks()
            return
        if model_name not in SONG_COVER_MODEL_CHOICES:
            set_progress(0, i18n('请选择去伴奏类分离模型'), 'failed')
            yield cover_status('失败', i18n('请选择去伴奏类分离模型')), progress_html(), *_empty_tracks()
            return
        input_audio_path = clean_path(
            input_audio_path if isinstance(input_audio_path, str) else getattr(input_audio_path, 'name', '')
        )
        if not input_audio_path or not os.path.isfile(input_audio_path):
            set_progress(0, i18n('输入音频不存在'), 'failed')
            yield cover_status('失败', i18n('输入音频不存在')), progress_html(), *_empty_tracks()
            return
        opt_root = clean_path(opt_root) or 'opt'
        output_format = (output_format or 'wav').lower()
        if output_format not in {'wav', 'flac', 'mp3', 'm4a'}:
            output_format = 'wav'
        work_root = os.path.abspath(os.path.join(opt_root, 'song_cover_work'))
        vocal_root = os.path.join(work_root, 'vocals')
        ins_root = os.path.join(work_root, 'instrumental')
        out_root = os.path.abspath(opt_root)
        os.makedirs(vocal_root, exist_ok=True)
        os.makedirs(ins_root, exist_ok=True)
        os.makedirs(out_root, exist_ok=True)
        stem = Path(input_audio_path).stem
        spec = resolve_model(model_name)
        lines.append('%s：%s' % (i18n('分离模型'), model_name))
        device_type = torch.device(config.device).type
        if device_type == 'cpu':
            lines.append(i18n('当前为 CPU 模式，分离很慢，请耐心等待；建议安装 CUDA 版 PyTorch'))
        set_progress(2, i18n('正在释放显存以便分离…'))
        yield cover_status('运行中', i18n('正在分离人声与伴奏…'), lines), progress_html(), *_empty_tracks()
        moved = _release_vc_gpu(vc)
        set_progress(5, i18n('正在分离人声与伴奏…'))
        yield cover_status('运行中', i18n('正在分离人声与伴奏…'), lines), progress_html(), *_empty_tracks()
        separate_log = ''
        for info in pymss_separate(
            model_name, '', vocal_root, [input_audio_path], ins_root, 'wav', event_callback=on_separate_event
        ):
            separate_log = info
            yield (
                cover_status('运行中', '%s\n%s' % (i18n('正在分离人声与伴奏…'), info), lines),
                progress_html(),
                *_empty_tracks(),
            )
        sep_vocal = os.path.join(vocal_root, '%s_%s.wav' % (stem, spec.desired_suffix))
        sep_ins = os.path.join(ins_root, '%s_%s.wav' % (stem, spec.secondary_suffix))
        if not os.path.isfile(sep_vocal) or not os.path.isfile(sep_ins):
            set_progress(progress['percent'], i18n('分离失败，未找到人声或伴奏文件'), 'failed')
            yield (
                cover_status('失败', '%s\n%s' % (i18n('分离失败，未找到人声或伴奏文件'), separate_log), lines),
                progress_html(),
                *_empty_tracks(),
            )
            return
        original_vocal_path = os.path.join(out_root, '%s_original_vocal.wav' % stem)
        instrumental_path = os.path.join(out_root, '%s_instrumental.wav' % stem)
        shutil.copy2(sep_vocal, original_vocal_path)
        shutil.copy2(sep_ins, instrumental_path)
        lines.append('%s：%s' % (i18n('原始人声'), original_vocal_path))
        lines.append('%s：%s' % (i18n('伴奏音乐'), instrumental_path))
        set_progress(78, i18n('正在进行音色转换…'))
        yield cover_status('运行中', i18n('正在进行音色转换…'), lines), progress_html(), *_empty_tracks()
        _restore_vc_gpu(vc, moved)
        moved = []
        info, opt = vc.vc_single(
            sid, original_vocal_path, f0_up_key, f0_method, file_index, index_rate, resample_sr, rms_mix_rate, protect
        )
        if not opt or opt[0] is None or opt[1] is None:
            set_progress(78, i18n('音色转换失败'), 'failed')
            yield (
                cover_status('失败', '%s\n%s' % (i18n('音色转换失败'), info), lines),
                progress_html(),
                *_empty_tracks(),
            )
            return
        tgt_sr, vocal_audio = opt
        lines.append(str(info))
        converted_vocal_path = os.path.join(out_root, '%s_converted_vocal.wav' % stem)
        sf.write(converted_vocal_path, _to_float_audio(vocal_audio), tgt_sr)
        lines.append('%s：%s' % (i18n('转换后人声'), converted_vocal_path))
        set_progress(92, i18n('正在合并人声与伴奏…'))
        yield cover_status('运行中', i18n('正在合并人声与伴奏…'), lines), progress_html(), *_empty_tracks()
        mix_sr, mixed = mix_vocal_instrumental(
            vocal_audio, tgt_sr, instrumental_path, vocal_gain=vocal_gain, inst_gain=inst_gain
        )
        cover_path = os.path.join(out_root, '%s_cover.%s' % (stem, output_format))
        _write_audio(cover_path, mixed, mix_sr, output_format)
        lines.append('%s：%s' % (i18n('成品'), cover_path))
        if not keep_stems:
            for path in (sep_vocal, sep_ins):
                try:
                    os.remove(path)
                except OSError:
                    pass
        set_progress(100, i18n('一键翻唱完成'), 'done')
        yield (
            cover_status('成功', i18n('一键翻唱完成'), lines),
            progress_html(),
            cover_path,
            converted_vocal_path,
            original_vocal_path,
            instrumental_path,
        )
    except Exception:
        detail = traceback.format_exc()
        logger.exception('Song cover pipeline failed')
        set_progress(progress['percent'], i18n('失败'), 'failed')
        yield cover_status('失败', detail, lines), progress_html(), *_empty_tracks()
    finally:
        if moved:
            _restore_vc_gpu(vc, moved)
