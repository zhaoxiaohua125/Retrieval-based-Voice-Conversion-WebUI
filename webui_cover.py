"""Launch official webui.py with local 一键翻唱 tab injected (no webui.py edits)."""
import os
import sys


WEBUI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webui.py')
INJECT_MARKERS = (
    'with gr.TabItem(i18n("人声伴奏分离&去混响")):',
    "with gr.TabItem(i18n('人声伴奏分离&去混响')):",
)
INJECT_BLOCK = """
            from tools.song_cover_webui import build_song_cover_tab
            build_song_cover_tab(
                vc=vc,
                spk_item=spk_item,
                protect0=protect0,
                file_index1=file_index1,
                i18n=i18n,
            )
"""


def prepare_source(src):
    if 'build_song_cover_tab(' in src:
        return src
    if 'from tools.song_cover import' in src or 'run_song_cover_webui' in src:
        raise SystemExit(
            'webui.py 仍包含一键翻唱代码。请先还原官方 webui.py，再用本启动器注入功能。'
        )
    for marker in INJECT_MARKERS:
        if marker in src:
            return src.replace(marker, INJECT_BLOCK + '\n        ' + marker, 1)
    raise SystemExit('未在 webui.py 中找到注入锚点：人声伴奏分离&去混响')


def main():
    with open(WEBUI_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    src = prepare_source(src)
    sys.argv[0] = WEBUI_PATH
    globals_dict = {
        '__name__': '__main__',
        '__file__': WEBUI_PATH,
        '__package__': None,
        '__builtins__': __builtins__,
    }
    exec(compile(src, WEBUI_PATH, 'exec'), globals_dict)


if __name__ == '__main__':
    main()
