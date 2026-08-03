from functools import partial

import gradio as gr

from tools.pymss_webui import render_pymss_progress
from tools.song_cover import SONG_COVER_MODEL_CHOICES, run_song_cover


def _run_song_cover_webui(vc, *args):
    yield from run_song_cover(vc, *args)


def _sync_cover_index(path):
    return path


def _sync_cover_protect(vc, protect_value):
    return {
        'visible': vc.if_f0 != 0,
        'value': protect_value if vc.if_f0 != 0 else 0.33,
        '__type__': 'update',
    }


def build_song_cover_tab(vc, spk_item, protect0, file_index1, i18n):
    with gr.TabItem(i18n('一键翻唱')):
        gr.Markdown(
            value=i18n(
                '上传整首歌曲：自动分离人声与伴奏 → 音色转换 → 合并导出成品；并生成转换后人声/原始人声/伴奏三轨。'
            )
        )
        with gr.Row():
            with gr.Column():
                cover_audio = gr.Audio(
                    label=i18n('拖拽或点击上传整首歌曲'),
                    source='upload',
                    type='filepath',
                    interactive=True,
                )
                cover_model = gr.Dropdown(
                    label=i18n('分离模型'),
                    choices=SONG_COVER_MODEL_CHOICES,
                    value=SONG_COVER_MODEL_CHOICES[0],
                    interactive=True,
                )
                cover_transform = gr.Number(
                    label=i18n('变调(整数, 半音数量, 升八度12降八度-12)'),
                    value=0,
                )
                cover_f0method = gr.Radio(
                    label=i18n('选择音高提取算法'),
                    choices=['pm', 'rmvpe', 'fcpe'],
                    value='rmvpe',
                    interactive=True,
                )
                cover_format = gr.Radio(
                    label=i18n('导出文件格式'),
                    choices=['wav', 'flac', 'mp3', 'm4a'],
                    value='wav',
                    interactive=True,
                )
                cover_opt = gr.Textbox(label=i18n('指定输出文件夹'), value='opt')
                cover_keep_stems = gr.Checkbox(
                    label=i18n('保留分离中间文件'),
                    value=False,
                    interactive=True,
                )
            with gr.Column():
                cover_resample = gr.Slider(
                    minimum=0,
                    maximum=48000,
                    label=i18n('后处理重采样至最终采样率，0为不进行重采样'),
                    value=0,
                    step=1,
                    interactive=True,
                )
                cover_rms = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n('输入源音量包络替换输出音量包络融合比例，越靠近1越使用输出包络'),
                    value=0.25,
                    interactive=True,
                )
                cover_protect = gr.Slider(
                    minimum=0,
                    maximum=0.5,
                    label=i18n(
                        '保护清辅音和呼吸声，防止电音撕裂等artifact，拉满0.5不开启，调低加大保护力度但可能降低索引效果'
                    ),
                    value=0.33,
                    step=0.01,
                    interactive=True,
                )
                cover_index_rate = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n('检索特征占比'),
                    value=0.75,
                    interactive=True,
                )
                cover_file_index = gr.Textbox(
                    label=i18n('特征检索库文件路径（选择模型后自动匹配，可手动修改）'),
                    value='',
                    interactive=True,
                )
                cover_vocal_gain = gr.Slider(
                    minimum=0,
                    maximum=2,
                    label=i18n('人声音量'),
                    value=1.0,
                    step=0.05,
                    interactive=True,
                )
                cover_inst_gain = gr.Slider(
                    minimum=0,
                    maximum=2,
                    label=i18n('伴奏音量'),
                    value=1.0,
                    step=0.05,
                    interactive=True,
                )
        with gr.Column():
            cover_btn = gr.Button(i18n('一键翻唱'), variant='primary')
            cover_progress = gr.HTML(value=render_pymss_progress(0, i18n('等待开始'), 'idle'))
            cover_info = gr.Textbox(label=i18n('输出信息'))
            gr.Markdown('### %s' % i18n('音轨'))
            cover_output = gr.Audio(label=i18n('成品'))
            cover_converted = gr.Audio(label=i18n('转换后人声'))
            cover_original = gr.Audio(label=i18n('原始人声'))
            cover_instrumental = gr.Audio(label=i18n('伴奏音乐'))
            cover_btn.click(
                partial(_run_song_cover_webui, vc),
                [
                    spk_item,
                    cover_audio,
                    cover_model,
                    cover_transform,
                    cover_f0method,
                    cover_file_index,
                    cover_index_rate,
                    cover_resample,
                    cover_rms,
                    cover_protect,
                    cover_vocal_gain,
                    cover_inst_gain,
                    cover_format,
                    cover_opt,
                    cover_keep_stems,
                ],
                [
                    cover_info,
                    cover_progress,
                    cover_output,
                    cover_converted,
                    cover_original,
                    cover_instrumental,
                ],
                api_name='song_cover',
            )
        file_index1.change(_sync_cover_index, inputs=[file_index1], outputs=[cover_file_index], queue=False)
        protect0.change(
            partial(_sync_cover_protect, vc),
            inputs=[protect0],
            outputs=[cover_protect],
            queue=False,
        )
