"""Task 4A acceptance: offline MSST + RVC cover pipeline."""
import argparse
import sys
from pathlib import Path


"""
输出文件（在 opt 目录）
{stem}_vocals.wav — 原唱人声
{stem}_instrumental.wav — 伴奏
{stem}_vocals_noreverb.wav — 去混响干声
{stem}_converted_vocal.wav — AI 人声
{stem}_cover.wav — 成品混音
{stem}_harmony.wav — 和声（仅 powerful 预设）

"""

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ops.rotating_log import setup_rotating_logging
from app.rvc.types import RvcInferParams


def require_live_dependencies():
    missing = []
    for name in ('torch', 'soundfile', 'numpy', 'librosa'):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print('TASK4 FAILED: --live 需要 RVC 环境，缺少: %s' % ', '.join(missing))
        print('请先: conda activate rvc312')
        raise SystemExit(1)


def test_types(errors):
    params = RvcInferParams(f0_up_key=2, index_rate=0.5)
    if params.f0_up_key != 2:
        errors.append('RvcInferParams default mismatch')


def test_live(input_path, output_dir, preset, model_sid, errors):
    from app.rvc import OfflineSongPipeline, discover_first_model, resolve_index_for_model

    input_path = Path(input_path)
    if not input_path.is_file():
        errors.append('input not found: %s' % input_path)
        return
    model_sid = model_sid or discover_first_model()
    if not model_sid:
        errors.append('no .pth model found in assets/weights, use --model your_model.pth')
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    params = RvcInferParams(file_index=resolve_index_for_model(model_sid))
    pipeline = OfflineSongPipeline(work_root=str(output_dir / 'msst_work'), msst_keep_work=False)
    terminal = None
    for event in pipeline.run(
        model_sid,
        str(input_path),
        vc=None,
        preset_id=preset,
        output_dir=str(output_dir),
        rvc_params=params,
        mix_cover=True,
        output_format='wav',
        event_callback=lambda e: print(e.get('event'), e.get('phase', ''), (e.get('message') or '')[:60]),
    ):
        if event.get('event') in {'result', 'failed', 'cancelled'}:
            terminal = event
    if terminal is None:
        errors.append('pipeline produced no terminal event')
        return
    if terminal.get('event') != 'result':
        errors.append('live failed: %s' % terminal.get('message', terminal.get('event')))
        return
    result = terminal['result']
    for path in (
        result.vocals_path,
        result.instrumental_path,
        result.vocals_noreverb_path,
        result.converted_vocal_path,
        result.cover_path,
    ):
        if not path or not Path(path).is_file():
            errors.append('missing output: %s' % path)
    if preset == 'powerful' and (not result.harmony_path or not Path(result.harmony_path).is_file()):
        errors.append('powerful preset missing harmony track')
    print('outputs saved to: %s' % output_dir.resolve())


def main():
    parser = argparse.ArgumentParser(description='Task4A offline cover pipeline test')
    parser.add_argument('--live', action='store_true', help='run full MSST+RVC pipeline (slow)')
    parser.add_argument('--input', default='TEMP/上春山片段qhheph0n.WAV')
    parser.add_argument('--output', default='opt/task4_offline', help='persistent output directory')
    parser.add_argument('--preset', default='normal', choices=['normal', 'powerful'])
    parser.add_argument('--model', default='', help='RVC model file name under assets/weights')
    args = parser.parse_args()

    setup_rotating_logging()
    errors = []
    test_types(errors)
    if args.live:
        require_live_dependencies()
        test_live(args.input, args.output, args.preset, args.model, errors)
    if errors:
        print('TASK4 FAILED:')
        for item in errors:
            print(' -', item)
        raise SystemExit(1)
    print('TASK4 PASSED: offline pipeline OK' + (' (live)' if args.live else ''))


if __name__ == '__main__':
    main()
