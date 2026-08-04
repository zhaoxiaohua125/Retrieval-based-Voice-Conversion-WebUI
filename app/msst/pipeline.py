"""MSST 多阶段离线分离流水线。

本模块仅封装调用 ``tools.pymss_webui.pymss_separate``，不修改上游 pymss 实现。
pymss 相关依赖（torch、soundfile 等）在真正执行分离时才按需加载。
"""

import logging
import os
import shutil
import sys
import traceback
from pathlib import Path

from app.msst.presets import get_preset
from app.msst.types import SeparationResult, StageOutput


logger = logging.getLogger('rvc_client')


def _clean_path(path):
    """与 pymss_webui.clean_path 等价的轻量路径规范化（避免 import 时加载 pymss）。"""
    path = path or ''
    if path.endswith(('\\', '/')):
        path = path[:-1]
    return path.replace('/', os.sep).replace('\\', os.sep).strip(" '\n\"\u202a")


def _pymss_tools():
    """按需导入 pymss WebUI 封装；缺少依赖时抛出 ImportError。"""
    from app.rvc.vc_context import upstream_import_context

    with upstream_import_context():
        from tools.pymss_webui import clean_path, pymss_separate, resolve_model, stop_pymss_separation
        return clean_path, pymss_separate, resolve_model, stop_pymss_separation


class MsstSongSeparator:
    """对标 SoundTrail 离线做歌：按预设顺序执行 MSST 分离阶段。"""

    def __init__(self, work_root=None, keep_work=False):
        self.work_root = _clean_path(work_root) if work_root else os.path.join('opt', 'msst_work')
        self.keep_work = bool(keep_work)
        self._cancel_requested = False

    def cancel(self):
        """请求终止当前分离任务，并通知 pymss 子进程停止。"""
        self._cancel_requested = True
        _, _, _, stop_pymss_separation = _pymss_tools()
        return stop_pymss_separation()

    def run(self, input_audio_path, preset_id='normal', output_dir='opt', event_callback=None):
        """执行多阶段分离。

        Args:
            input_audio_path: 原始整曲路径（FFmpeg 可解码格式）。
            preset_id: ``normal`` 或 ``powerful``。
            output_dir: 最终标准文件名输出目录。
            event_callback: 接收 pymss 事件 dict（附加 ``stage`` / ``stage_index`` 字段）。

        Yields:
            dict: 进度事件；最后一项 ``event`` 为 ``result`` 或 ``failed`` / ``cancelled``。
        """
        input_audio_path = _clean_path(input_audio_path)
        output_dir = _clean_path(output_dir) or 'opt'
        if not input_audio_path or not os.path.isfile(input_audio_path):
            yield {'event': 'failed', 'message': '输入音频不存在', 'source': input_audio_path}
            return
        try:
            clean_path, _, _, _ = _pymss_tools()
        except ImportError as exc:
            yield {
                'event': 'failed',
                'message': 'MSST 依赖未安装（需要 torch、soundfile 等）。请激活 rvc312 环境后重试。详情: %s' % exc,
            }
            return
        input_audio_path = clean_path(input_audio_path)
        output_dir = clean_path(output_dir) or 'opt'
        try:
            preset = get_preset(preset_id)
        except KeyError as exc:
            yield {'event': 'failed', 'message': str(exc)}
            return

        stem = Path(input_audio_path).stem
        work_root = os.path.abspath(self.work_root)
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(work_root, exist_ok=True)
        stage_logs = []
        stage_outputs = []
        context = {'source': input_audio_path, 'stage1_vocals': None, 'stage2_noreverb': None}

        try:
            total = len(preset.stages)
            for index, stage in enumerate(preset.stages):
                if self._cancel_requested:
                    yield {'event': 'cancelled', 'message': '用户取消分离', 'stage': stage.stage_id}
                    return
                stage_input = self._resolve_stage_input(stage.stage_id, context)
                if not stage_input:
                    yield {'event': 'failed', 'message': '阶段 %s 缺少输入' % stage.stage_id}
                    return
                yield {
                    'event': 'stage_start',
                    'stage': stage.stage_id,
                    'stage_index': index + 1,
                    'stage_total': total,
                    'model_label': stage.model_label,
                    'message': stage.description,
                }

                def on_event(event, stage_id=stage.stage_id, stage_index=index + 1, stage_total=total):
                    payload = dict(event or {})
                    payload['stage'] = stage_id
                    payload['stage_index'] = stage_index
                    payload['stage_total'] = stage_total
                    if event_callback is not None:
                        event_callback(payload)
                    return payload

                stage_result, stage_log = self._run_single_stage(
                    stage,
                    stage_input,
                    work_root,
                    on_event,
                )
                if stage_log:
                    stage_logs.append(stage_log)
                if stage_result is None:
                    if self._cancel_requested:
                        yield {'event': 'cancelled', 'message': '分离已取消', 'stage': stage.stage_id}
                    else:
                        yield {'event': 'failed', 'message': '阶段 %s 分离失败' % stage.stage_id, 'log': stage_log}
                    return
                stage_outputs.append(stage_result)
                self._update_context(stage.stage_id, stage_result, context)

            result = self._export_outputs(stem, preset, context, output_dir, stage_outputs, '\n'.join(stage_logs))
            yield {'event': 'result', 'result': result, 'payload': result.as_dict()}
        except Exception:
            logger.error('msst pipeline failed:\n%s', traceback.format_exc())
            yield {'event': 'failed', 'message': traceback.format_exc()}
        finally:
            if not self.keep_work:
                self._cleanup_work_root(work_root)

    def _resolve_stage_input(self, stage_id, context):
        """根据阶段 ID 决定当前输入文件。"""
        if stage_id == 'split':
            return context['source']
        if stage_id == 'dereverb':
            return context.get('stage1_vocals')
        if stage_id == 'harmony':
            return context.get('stage1_vocals')
        return None

    def _update_context(self, stage_id, stage_result, context):
        """把阶段产物写入上下文，供后续阶段引用。"""
        if stage_id == 'split':
            context['stage1_vocals'] = stage_result.desired_path
            context['stage1_instrumental'] = stage_result.secondary_path
        elif stage_id == 'dereverb':
            context['stage2_noreverb'] = stage_result.desired_path
        elif stage_id == 'harmony':
            context['stage3_harmony'] = stage_result.secondary_path

    def _run_single_stage(self, stage, input_path, work_root, on_event):
        """调用 pymss_separate 执行单个阶段。"""
        _, pymss_separate, resolve_model, stop_pymss_separation = _pymss_tools()
        spec = resolve_model(stage.model_label)
        stage_dir = os.path.join(work_root, stage.stage_id)
        vocal_dir = os.path.join(stage_dir, 'primary')
        secondary_dir = os.path.join(stage_dir, 'secondary')
        os.makedirs(vocal_dir, exist_ok=True)
        os.makedirs(secondary_dir, exist_ok=True)
        stem = Path(input_path).stem
        last_log = ''
        for info in pymss_separate(
            stage.model_label,
            '',
            vocal_dir,
            [input_path],
            secondary_dir,
            'wav',
            event_callback=on_event,
        ):
            last_log = info
            if self._cancel_requested:
                stop_pymss_separation()
                return None, last_log
            if isinstance(info, str) and '分离任务已停止' in info:
                self._cancel_requested = True
                return None, last_log
        desired = os.path.join(vocal_dir, '%s_%s.wav' % (stem, spec.desired_suffix))
        secondary = os.path.join(secondary_dir, '%s_%s.wav' % (stem, spec.secondary_suffix))
        if not os.path.isfile(desired):
            return None, last_log
        return StageOutput(
            stage_id=stage.stage_id,
            model_label=stage.model_label,
            desired_path=desired,
            secondary_path=secondary if os.path.isfile(secondary) else None,
        ), last_log

    def _export_outputs(self, stem, preset, context, output_dir, stage_outputs, log_text):
        """复制到 output_dir 并使用统一命名。"""
        vocals_src = context.get('stage1_vocals')
        inst_src = context.get('stage1_instrumental')
        noreverb_src = context.get('stage2_noreverb')
        harmony_src = context.get('stage3_harmony')
        if not all([vocals_src, inst_src, noreverb_src]):
            raise FileNotFoundError('missing stage outputs for export')

        paths = {
            'vocals': os.path.join(output_dir, '%s_vocals.wav' % stem),
            'instrumental': os.path.join(output_dir, '%s_instrumental.wav' % stem),
            'vocals_noreverb': os.path.join(output_dir, '%s_vocals_noreverb.wav' % stem),
        }
        shutil.copy2(vocals_src, paths['vocals'])
        shutil.copy2(inst_src, paths['instrumental'])
        shutil.copy2(noreverb_src, paths['vocals_noreverb'])
        harmony_path = None
        if harmony_src and os.path.isfile(harmony_src):
            harmony_path = os.path.join(output_dir, '%s_harmony.wav' % stem)
            shutil.copy2(harmony_src, harmony_path)
        return SeparationResult(
            preset_id=preset.preset_id,
            source_path=context['source'],
            output_dir=output_dir,
            vocals_path=paths['vocals'],
            instrumental_path=paths['instrumental'],
            vocals_noreverb_path=paths['vocals_noreverb'],
            harmony_path=harmony_path,
            stages=stage_outputs,
            log=log_text,
        )

    def _cleanup_work_root(self, work_root):
        """删除临时工作目录。"""
        try:
            if work_root and os.path.isdir(work_root):
                shutil.rmtree(work_root, ignore_errors=True)
        except OSError:
            logger.warning('failed to cleanup msst work dir: %s', work_root)
