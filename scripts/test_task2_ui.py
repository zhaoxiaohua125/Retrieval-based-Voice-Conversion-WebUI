"""Task 2 acceptance: PyQt6 UI skeleton imports and optional launch."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_imports(errors):
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        errors.append('PyQt6 未安装，请执行: pip install PyQt6')
        return
    from app.ui import MainWindow, LyricsWindow, UiBridge, build_tray
    from app.ui.layout_store import load_ui_layout, save_ui_layout
    if not callable(load_ui_layout):
        errors.append('layout_store broken')


def test_headless(errors):
    from PyQt6.QtWidgets import QApplication
    from app.scheduler import AppScheduler
    from app.ui import MainWindow, UiBridge

    app = QApplication([])
    scheduler = AppScheduler.reset_for_test()
    scheduler = AppScheduler.instance().start()
    bridge = UiBridge()
    window = MainWindow(bridge, project_root=ROOT)
    if window.stack.count() != 3:
        errors.append('expected 3 top-level pages (播放/制作歌曲/公告)')
    if len(window.header.TAB_NAMES) != 3:
        errors.append('expected 3 nav tabs')
    if window.page_song_make.file_list is None:
        errors.append('song make page missing file list')
    window.close()
    scheduler.shutdown()
    app.quit()


def main():
    parser = argparse.ArgumentParser(description='Task2 UI skeleton test')
    parser.add_argument('--show', action='store_true', help='launch interactive UI (manual)')
    args = parser.parse_args()

    if args.show:
        import subprocess
        raise SystemExit(subprocess.call([sys.executable, str(ROOT / 'scripts' / 'run_ui_skeleton.py')]))

    errors = []
    test_imports(errors)
    if not errors:
        test_headless(errors)
    if errors:
        print('TASK2 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK2 PASSED: UI skeleton imports and headless build OK')
    print('交互验收请运行: python scripts/run_ui_skeleton.py')


if __name__ == '__main__':
    main()
