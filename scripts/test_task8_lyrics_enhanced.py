"""Task 8：Enhanced LRC 往返、均分对齐、修词重映射、字级 matcher。"""
import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_LINE = """[ti:逐字测试]
[ar:Demo]
[00:01.00]你好世界
[00:03.00]第二句歌词
"""

SAMPLE_ENHANCED = """[ti:Enhanced]
[00:01.00]<00:01.00>你<00:01.50>好
[00:03.00]<00:03.00>第<00:03.40>二
"""


def test_roundtrip(errors):
    from app.lyrics import dump_enhanced_lrc, parse_enhanced_lrc

    doc = parse_enhanced_lrc(SAMPLE_ENHANCED)
    if len(doc.lines) != 2 or not doc.has_words:
        errors.append('enhanced parse failed')
        return
    if doc.lines[0].words[0].text != '你' or abs(doc.lines[0].words[1].start_sec - 1.5) > 0.01:
        errors.append('enhanced word timestamp mismatch')
    text = dump_enhanced_lrc(doc)
    doc2 = parse_enhanced_lrc(text)
    if len(doc2.lines[0].words) != len(doc.lines[0].words):
        errors.append('enhanced dump/load roundtrip failed')


def test_even_fill(errors):
    from app.lyrics import fill_even_words, parse_enhanced_lrc

    doc = fill_even_words(parse_enhanced_lrc(SAMPLE_LINE))
    if not doc.has_words:
        errors.append('even fill produced no words')
        return
    w0 = doc.lines[0].words
    if ''.join(w.text for w in w0) != '你好世界':
        errors.append('even fill text mismatch: %s' % ''.join(w.text for w in w0))
    # 4 字约 1.6s，不应拖到下一句
    if w0[-1].end_sec - w0[0].start_sec > 2.2:
        errors.append('even fill not compressed: %s' % (w0[-1].end_sec - w0[0].start_sec))


def test_long_gap_compress(errors):
    from app.lyrics import LyricMatcher, fill_even_words, parse_enhanced_lrc

    doc = fill_even_words(parse_enhanced_lrc('[00:10.00]空凝眸情字深浅无解\n[00:40.00]下一句\n'))
    words = [w for w in doc.lines[0].words if not w.text.isspace()]
    span = words[-1].end_sec - words[0].start_sec
    if span > 6.0:
        errors.append('long gap line not compressed: %.2fs' % span)
    hit = LyricMatcher(doc).match(10.0 + span + 0.5)
    if hit.word_index < len(doc.lines[0].words):
        errors.append('after sing window should mark line done, got word_index=%s' % hit.word_index)


def test_matcher_words(errors):
    from app.lyrics import LyricMatcher, fill_even_words, parse_enhanced_lrc

    doc = fill_even_words(parse_enhanced_lrc(SAMPLE_LINE))
    hit = LyricMatcher(doc).match(1.1)
    if hit.index != 0 or hit.word_index < 0:
        errors.append('word matcher failed at 1.1')
    if not hit.to_dict().get('html'):
        errors.append('match html missing')


def test_rewrite(errors):
    from app.lyrics import fill_even_words, parse_enhanced_lrc, rewrite_line

    doc = fill_even_words(parse_enhanced_lrc(SAMPLE_LINE))
    rewrite_line(doc, 0, '你好啊')
    if doc.lines[0].text != '你好啊' or not doc.lines[0].words:
        errors.append('rewrite failed')
    if ''.join(w.text for w in doc.lines[0].words) != '你好啊':
        errors.append('rewrite tokens mismatch')


def test_energy_align(errors):
    import numpy as np
    import soundfile as sf

    from app.lyrics import align_words_by_energy, parse_enhanced_lrc

    sr = 16000
    # 两段有声：0.2~0.8s 与 1.2~1.8s，对应两句
    audio = np.zeros(int(2.2 * sr), dtype=np.float32)
    t = np.arange(int(0.6 * sr)) / sr
    audio[int(0.2 * sr) : int(0.8 * sr)] = 0.4 * np.sin(2 * np.pi * 220 * t)
    audio[int(1.2 * sr) : int(1.8 * sr)] = 0.4 * np.sin(2 * np.pi * 330 * t)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / 'v.wav'
        sf.write(str(wav), audio, sr)
        doc = parse_enhanced_lrc('[00:00.00]甲乙\n[00:01.00]丙丁\n')
        aligned = align_words_by_energy(doc, wav)
        w0 = aligned.lines[0].words
        if not w0 or w0[0].start_sec < 0.05 or w0[0].start_sec > 0.45:
            errors.append('energy align line0 start unexpected: %s' % (w0[0].start_sec if w0 else None))
        if w0 and w0[-1].end_sec > 1.05:
            errors.append('energy align line0 spilled into silence: %s' % w0[-1].end_sec)


def test_whisper_map_units(errors):
    from app.lyrics.aligner import _align_line_with_whisper
    from app.lyrics.types import LyricLine

    line = LyricLine(10.0, 20.0, '空凝眸情', index=0)
    timed = [
        (10.0, 10.4, '空'),
        (10.4, 10.9, '凝'),
        (10.9, 11.3, '眸'),
        (11.3, 11.8, '情'),
    ]
    words = _align_line_with_whisper(line, timed)
    plain = ''.join(w.text for w in words if not w.text.isspace())
    if plain != '空凝眸情':
        errors.append('whisper map text mismatch: %s' % plain)
    if abs(words[0].start_sec - 10.0) > 0.05 or words[-1].end_sec < 11.5:
        errors.append('whisper map times unexpected: %s-%s' % (words[0].start_sec, words[-1].end_sec))


def test_file_enhance(errors):
    from app.lyrics import enhance_lrc_file, load_enhanced_lrc

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'demo.lrc'
        p.write_text(SAMPLE_LINE, encoding='utf-8')
        out, mode = enhance_lrc_file(p, use_whisper=False)
        doc = load_enhanced_lrc(out)
        if not doc.has_words or '<' not in out.read_text(encoding='utf-8'):
            errors.append('enhance_lrc_file did not write word tags')
        if mode not in ('even', 'energy'):
            errors.append('unexpected enhance mode without whisper: %s' % mode)


def test_live(errors, vocal: str):
    from app.lyrics import align_with_whisper, parse_enhanced_lrc

    doc = parse_enhanced_lrc(SAMPLE_LINE)
    aligned = align_with_whisper(vocal, doc, language='zh')
    if not aligned.lines:
        errors.append('live align produced empty doc')
    else:
        print('live align lines=%s has_words=%s' % (len(aligned.lines), aligned.has_words))


def main():
    parser = argparse.ArgumentParser(description='Task8 Enhanced LRC test')
    parser.add_argument('--live', type=str, default='', help='optional vocal wav for whisper align')
    args = parser.parse_args()
    errors = []
    test_roundtrip(errors)
    test_even_fill(errors)
    test_long_gap_compress(errors)
    test_matcher_words(errors)
    test_rewrite(errors)
    test_energy_align(errors)
    test_whisper_map_units(errors)
    test_file_enhance(errors)
    if args.live:
        test_live(errors, args.live)
    if errors:
        print('FAIL')
        for e in errors:
            print(' -', e)
        return 1
    print('OK task8 enhanced lyrics')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
