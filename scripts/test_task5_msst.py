"""Task 5 acceptance: MSST multi-stage separation presets and pipeline."""
import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.msst.presets import get_preset
from app.ops.rotating_log import setup_rotating_logging

LIVE_DEPENDENCIES = (
    'torch',
    'soundfile',
    'numpy',
    'librosa',
)


def require_live_dependencies():
    """检查 --live 模式所需依赖；缺失时给出明确提示并退出。"""
    missing = []
    for name in LIVE_DEPENDENCIES:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print('TASK5 FAILED: --live 需要 RVC 运行环境，当前缺少依赖: %s' % ', '.join(missing))
        print('请先激活 conda 环境，例如: conda activate rvc312')
        print('并在项目根目录安装依赖: pip install -r requirments_cu118_py312.txt （按显卡选择对应文件）')
        raise SystemExit(1)


def test_presets(errors):
    """验证预设定义与阶段数量。"""
    normal = get_preset('normal')
    powerful = get_preset('powerful')
    if len(normal.stages) != 2:
        errors.append('normal preset should have 2 stages')
    if len(powerful.stages) != 3:
        errors.append('powerful preset should have 3 stages')
    if normal.stages[0].model_label != '去伴奏':
        errors.append('normal stage1 model mismatch')
    if powerful.stages[-1].stage_id != 'harmony':
        errors.append('powerful should end with harmony stage')


def test_cancel_cleanup(errors):
    """验证取消后临时目录会被清理。"""
    from app.msst.pipeline import MsstSongSeparator

    with tempfile.TemporaryDirectory() as tmp:
        work_root = Path(tmp) / 'work'
        separator = MsstSongSeparator(work_root=str(work_root), keep_work=False)
        separator._cancel_requested = True
        events = list(separator.run('missing.wav', preset_id='normal', output_dir=str(Path(tmp) / 'out')))
        if not events or events[-1].get('event') != 'failed':
            errors.append('missing input should fail')
        separator._cleanup_work_root(str(work_root))
        if work_root.exists() and any(work_root.iterdir()):
            errors.append('cleanup should remove work dir contents')


def test_live(input_path, preset_id, errors):
    """真实跑一遍 MSST（需 rvc312 环境 + 模型权重）。"""
    from app.msst.pipeline import MsstSongSeparator

    input_path = Path(input_path)
    if not input_path.is_file():
        errors.append('live test input not found: %s' % input_path)
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        work_root = tmp_path / 'work'
        out_dir = tmp_path / 'out'
        separator = MsstSongSeparator(work_root=str(work_root), keep_work=False)
        result_event = None
        for event in separator.run(str(input_path), preset_id=preset_id, output_dir=str(out_dir)):
            print(event.get('event'), event.get('stage', ''), event.get('message', '')[:80])
            if event.get('event') in {'result', 'failed', 'cancelled'}:
                result_event = event
        if result_event is None:
            errors.append('live test produced no terminal event')
            return
        if result_event.get('event') != 'result':
            errors.append('live test failed: %s' % result_event.get('message', result_event.get('event')))
            return
        result = result_event['result']
        for path in (result.vocals_path, result.instrumental_path, result.vocals_noreverb_path):
            if not Path(path).is_file():
                errors.append('live test missing output: %s' % path)
        if preset_id == 'powerful' and (not result.harmony_path or not Path(result.harmony_path).is_file()):
            errors.append('powerful live test missing harmony output')
        if work_root.exists() and any(work_root.rglob('*')):
            errors.append('live test work dir should be cleaned')
        print('live preset=%s outputs in %s' % (preset_id, out_dir))
        print('注意：--live 使用系统临时目录，脚本结束后会自动删除；正式使用请调用 OfflineSongPipeline 并指定 output_dir=opt/...')


def main():
    parser = argparse.ArgumentParser(description='Task5 MSST module acceptance')
    parser.add_argument('--live', action='store_true', help='run real MSST separation (slow, needs GPU/models)')
    parser.add_argument('--input', default='TEMP/tmpnau9ezdu.wav', help='audio path for --live')
    parser.add_argument('--preset', default='normal', choices=['normal', 'powerful'])
    args = parser.parse_args()

    setup_rotating_logging(console_level=20)
    errors = []
    test_presets(errors)
    test_cancel_cleanup(errors)
    if args.live:
        require_live_dependencies()
        test_live(args.input, args.preset, errors)

    if errors:
        print('TASK5 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK5 PASSED: msst presets and pipeline structure OK' + (' (live)' if args.live else ''))


if __name__ == '__main__':
    main()
