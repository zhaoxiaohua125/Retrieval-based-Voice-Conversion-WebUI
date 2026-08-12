"""人声轨 / 行级 LRC → 字级时间轴：Whisper 对齐优先，能量/均分回退。"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from app.lyrics.enhanced_lrc import load_enhanced_lrc, save_enhanced_lrc
from app.lyrics.types import LyricDocument, LyricLine, LyricWord

logger = logging.getLogger('rvc_client.lyrics.aligner')

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]')
_WHISPER_MODEL = None
_WHISPER_KEY = None
_WHISPER_CUDA_OK = None  # None未知 / True可用 / False已证实失败（本进程不再尝试）
_WHISPER_UNITS_CACHE: dict = {}


def tokenize_lyric_text(text: str) -> list[str]:
    """中日韩逐字，拉丁按词，空白保留为独立 token（便于还原原文）。"""
    text = text or ''
    tokens: list[str] = []
    buf = ''
    for ch in text:
        if ch.isspace():
            if buf:
                tokens.append(buf)
                buf = ''
            tokens.append(ch)
        elif _CJK_RE.match(ch):
            if buf:
                tokens.append(buf)
                buf = ''
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens or ([text] if text else [])


def _content_count(tokens: list[str]) -> int:
    return sum(1 for t in tokens if not t.isspace())


def _clamp_sing_window(t0: float, t1: float, n_content: int, line_end: float) -> tuple[float, float]:
    """压缩句间大空白；保留慢歌可唱速度（约 0.8s/字），避免字跳过快。"""
    t0 = float(t0)
    t1 = max(t0 + 0.05, float(t1))
    n = max(1, int(n_content))
    ideal = max(1.2, min(14.0, n * 0.82))
    span = t1 - t0
    if span > ideal:
        t1 = t0 + ideal
    if t1 > line_end:
        t1 = max(t0 + 0.05, line_end)
    return t0, t1


def normalize_line_words(line: LyricLine, min_char_sec: float = 0.28) -> None:
    """修复过密字轴与末字吞进句间空白（Enhanced LRC 只存字起点时尤甚）。"""
    content = [w for w in line.words if not (w.text or '').isspace()]
    if not content:
        return
    n = len(content)
    gaps = [content[i + 1].start_sec - content[i].start_sec for i in range(n - 1)]
    gaps = [g for g in gaps if g > 1e-6]
    med = sorted(gaps)[len(gaps) // 2] if gaps else float(content[0].end_sec - content[0].start_sec)
    t0 = float(content[0].start_sec)
    line_end = float(line.end_sec)
    # 仅修复病态过密（如 0.1s/字）；正常 0.4~0.5s 间隔不动
    if n >= 2 and med < min_char_sec:
        budget = max(min_char_sec * n, min(n * 0.82, max(0.05, line_end - t0)))
        step = budget / n
        for i, w in enumerate(content):
            w.start_sec = t0 + i * step
            w.end_sec = t0 + (i + 1) * step
        med = step
    else:
        for i in range(n - 1):
            content[i].end_sec = max(content[i].start_sec + 0.03, content[i + 1].start_sec)
    last_dur = max(0.25, min(2.0, med if med > 0 else 0.8))
    content[-1].end_sec = min(line_end, content[-1].start_sec + last_dur)
    if content[-1].end_sec <= content[-1].start_sec:
        content[-1].end_sec = min(line_end, content[-1].start_sec + 0.25)


def _words_from_window(tokens: list[str], t0: float, t1: float, clamp: bool = True) -> list[LyricWord]:
    contents = [i for i, tok in enumerate(tokens) if not tok.isspace()]
    if not tokens:
        return []
    if not contents:
        return [LyricWord(t0, t1, tok, i) for i, tok in enumerate(tokens)]
    nc = len(contents)
    if clamp:
        t0, t1 = _clamp_sing_window(t0, t1, nc, t1)
    else:
        t0, t1 = float(t0), max(float(t0) + 0.05, float(t1))
    step = max(0.03, (t1 - t0) / nc)
    edges = [t0 + i * step for i in range(nc)]
    edges.append(t0 + nc * step)
    words: list[LyricWord] = []
    ci = 0
    for i, tok in enumerate(tokens):
        if tok.isspace():
            t = edges[min(ci, len(edges) - 1)]
            words.append(LyricWord(t, t + 0.01, tok, i))
            continue
        s = edges[ci]
        e = edges[ci + 1]
        words.append(LyricWord(s, max(e, s + 0.03), tok, i))
        ci += 1
    return words


def _even_line_words(line: LyricLine, tokens: list[str], _sing_ratio: float) -> list[LyricWord]:
    n = _content_count(tokens)
    t0 = line.start_sec
    t1 = line.start_sec + max(0.05, line.end_sec - line.start_sec)
    t0, t1 = _clamp_sing_window(t0, t1, n, line.end_sec)
    return _finalize_words(line, _words_from_window(tokens, t0, t1))


def fill_even_words(doc: LyricDocument, sing_ratio: float = 0.78) -> LyricDocument:
    """无音频时的回退：按字数压缩均分。"""
    for line in doc.lines:
        tokens = tokenize_lyric_text(line.text)
        if not tokens:
            line.words = []
            continue
        line.words = _even_line_words(line, tokens, sing_ratio)
        line.text = ''.join(tokens)
    return doc


def ensure_words(doc: LyricDocument, sing_ratio: float = 0.78) -> LyricDocument:
    if doc.has_words:
        return doc
    return fill_even_words(doc, sing_ratio=sing_ratio)


def _load_mono(path: str | Path):
    import soundfile as sf

    data, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return np.asarray(data.mean(axis=1), dtype=np.float32), int(sr)


def _line_energy_words(line: LyricLine, mono: np.ndarray, sr: int, hop: int, sing_ratio: float) -> list[LyricWord]:
    tokens = tokenize_lyric_text(line.text)
    if not tokens:
        return []
    # 句间大空白时只取行首一段，避免把后面副歌能量算进来
    nc = _content_count(tokens)
    max_scan = min(float(line.end_sec), float(line.start_sec) + max(8.0, nc * 1.2))
    i0 = max(0, int(line.start_sec * sr))
    i1 = min(len(mono), int(max_scan * sr))
    seg = mono[i0:i1]
    if seg.size < hop * 2:
        return _even_line_words(line, tokens, sing_ratio)
    n = max(1, seg.size // hop)
    rms = np.empty(n, dtype=np.float32)
    for i in range(n):
        chunk = seg[i * hop : (i + 1) * hop]
        rms[i] = float(np.sqrt(np.mean(chunk * chunk)) + 1e-12)
    if n >= 3:
        rms = np.convolve(rms, np.ones(3, dtype=np.float32) / 3.0, mode='same')
    peak = float(np.max(rms))
    thr = max(peak * 0.12, float(np.median(rms)) * 0.85)
    active = np.flatnonzero(rms >= thr)
    if active.size == 0:
        return _even_line_words(line, tokens, sing_ratio)
    # 取第一段连续有声（中间长静音不跨段）
    gap_max = max(3, int(0.45 * sr / hop))
    a0 = int(active[0])
    a1 = a0
    for x in active[1:]:
        if int(x) - a1 > gap_max:
            break
        a1 = int(x)
    a1 = a1 + 1
    pad = max(0, min(2, (a1 - a0) // 10))
    a0 = min(a0 + pad, a1 - 1)
    a1 = max(a1 - pad, a0 + 1)
    t0 = line.start_sec + a0 * hop / sr
    t1 = line.start_sec + a1 * hop / sr
    t0, t1 = _clamp_sing_window(t0, t1, nc, line.end_sec)
    words = _words_from_window(tokens, t0, t1)
    tmp = LyricLine(line.start_sec, line.end_sec, line.text, line.index, words)
    normalize_line_words(tmp)
    return tmp.words


def align_words_by_energy(doc: LyricDocument, audio_path: str | Path, hop_ms: float = 20.0, sing_ratio: float = 0.78) -> LyricDocument:
    """按人声能量在行内分配字时间（不依赖 Whisper）。"""
    mono, sr = _load_mono(audio_path)
    hop = max(1, int(sr * float(hop_ms) / 1000.0))
    for line in doc.lines:
        tokens = tokenize_lyric_text(line.text)
        line.words = _line_energy_words(line, mono, sr, hop, sing_ratio)
        line.text = ''.join(tokens) if tokens else line.text
    logger.info('energy align done path=%s lines=%s', audio_path, len(doc.lines))
    return doc


def prepare_word_timing(
    doc: LyricDocument,
    vocal_path: str | Path | None = None,
    sing_ratio: float = 0.78,
) -> LyricDocument:
    """优先人声能量对齐，否则压缩均分。进歌快速路径，不跑 Whisper。"""
    if vocal_path and Path(vocal_path).is_file():
        try:
            align_words_by_energy(doc, vocal_path, sing_ratio=sing_ratio)
            doc.align_mode = 'energy'
            return doc
        except Exception as exc:
            logger.warning('energy align failed, fallback even: %s', exc)
    for ln in doc.lines:
        ln.words = []
    fill_even_words(doc, sing_ratio=sing_ratio)
    doc.align_mode = 'even'
    return doc


def word_timing_label(
    align_mode: str = '',
    has_words: bool = False,
    from_file: bool = False,
    config_engine: str = '',
) -> str:
    """状态栏逐字来源文案（显示文件实际算法，不是当前 config 意向）。"""
    mode = (align_mode or '').strip().lower()
    cfg = (config_engine or '').strip().lower()
    cfg_whisper = cfg.startswith('whisper') or cfg in ('faster-whisper', 'asr')
    if mode.startswith('whisper'):
        base = '，文件内 Whisper 逐字' if from_file else '，Whisper 逐字'
    elif mode == 'energy':
        base = '，人声能量逐字' + ('（进歌快速补齐）' if not from_file else '（文件）')
    elif mode == 'even':
        base = '，均分逐字'
    elif has_words:
        base = '，逐字（文件缓存）'
    else:
        return ''
    # 配置与文件不一致时说明：改 align_engine 不会自动改已生成的 LRC
    if has_words and cfg:
        if cfg_whisper and not mode.startswith('whisper'):
            base += '；配置 Whisper，点「生成逐字」重算'
        elif (not cfg_whisper) and mode.startswith('whisper'):
            base += '；配置已是 energy，点「生成逐字」可重算为能量'
        elif (not cfg_whisper) and mode == 'energy' and cfg == 'energy':
            pass
        elif cfg == 'even' and mode != 'even':
            base += '；点「生成逐字」按当前配置重算'
    return base


def refresh_karaoke_timing(doc: LyricDocument, sing_ratio: float = 0.78, vocal_path: str | Path | None = None) -> LyricDocument:
    """加载/增强时统一入口（快速路径，不用 Whisper）。"""
    if not doc.lines:
        return doc
    return prepare_word_timing(doc, vocal_path=vocal_path, sing_ratio=sing_ratio)


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def _words_from_weighted_timeline(tokens: list[str], timed_units: list[tuple[float, float, str]]) -> list[LyricWord]:
    """按 Whisper 各片时长加权，把歌词字铺到真实演唱时间轴上（不依赖 ASR 文本是否认对）。"""
    contents = [tok for tok in tokens if not tok.isspace()]
    if not contents or not timed_units:
        return []
    weights = [max(0.03, float(u[1]) - float(u[0])) for u in timed_units]
    total_w = float(sum(weights)) or 1.0
    n = len(contents)

    def time_at_frac(frac: float) -> float:
        target = total_w * max(0.0, min(1.0, frac))
        c = 0.0
        for u, w in zip(timed_units, weights):
            if c + w >= target - 1e-9:
                local = (target - c) / w if w > 0 else 1.0
                return float(u[0]) + (float(u[1]) - float(u[0])) * min(1.0, max(0.0, local))
            c += w
        return float(timed_units[-1][1])

    edges = [time_at_frac(i / n) for i in range(n)]
    edges.append(time_at_frac(1.0))
    words: list[LyricWord] = []
    ci = 0
    for i, tok in enumerate(tokens):
        if tok.isspace():
            t = edges[min(ci, len(edges) - 1)]
            words.append(LyricWord(t, t + 0.01, tok, i))
            continue
        s, e = edges[ci], edges[ci + 1]
        if e - s > 1.8:
            e = s + 1.8
        words.append(LyricWord(s, max(e, s + 0.03), tok, i))
        ci += 1
    return words


def _finalize_words(line: LyricLine, words: list[LyricWord]) -> list[LyricWord]:
    tmp = LyricLine(line.start_sec, line.end_sec, line.text, line.index, words)
    normalize_line_words(tmp)
    return tmp.words


def resolve_local_whisper_dir(model_size: str = 'small') -> Path | None:
    """若本机已有 faster-whisper 权重目录则返回（含 model.bin），避免反复访问 Hub。"""
    name = (model_size or 'small').strip()
    if not name:
        return None
    direct = Path(name)
    if direct.is_dir() and (direct / 'model.bin').is_file():
        return direct.resolve()
    root = Path(__file__).resolve().parents[2]
    for cand in (root / 'assets' / 'whisper' / name, root / 'assets' / 'faster-whisper' / name):
        if (cand / 'model.bin').is_file():
            return cand.resolve()
    hub = Path.home() / '.cache' / 'huggingface' / 'hub' / ('models--Systran--faster-whisper-%s' % name) / 'snapshots'
    if hub.is_dir():
        snaps = sorted([p for p in hub.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        for snap in snaps:
            if (snap / 'model.bin').is_file():
                return snap.resolve()
    return None


def local_whisper_ready(model_size: str = 'small') -> bool:
    return resolve_local_whisper_dir(model_size) is not None


def _get_whisper_model(model_size: str = 'small', force_cpu: bool = False, device_pref: str = 'auto'):
    global _WHISPER_MODEL, _WHISPER_KEY, _WHISPER_CUDA_OK
    import os

    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from faster_whisper import WhisperModel

    device, compute = 'cpu', 'int8'
    pref = (device_pref or 'auto').lower()
    if force_cpu or pref == 'cpu' or _WHISPER_CUDA_OK is False:
        device, compute = 'cpu', 'int8'
    elif pref == 'cuda':
        device, compute = 'cuda', 'float16'
    else:
        try:
            import torch

            if torch.cuda.is_available() and _WHISPER_CUDA_OK is not False:
                device, compute = 'cuda', 'float16'
        except Exception:
            pass
    local_dir = resolve_local_whisper_dir(model_size)
    model_id = str(local_dir) if local_dir else model_size
    key = (model_id, device, compute)
    if _WHISPER_MODEL is not None and _WHISPER_KEY == key:
        return _WHISPER_MODEL
    # 已有同尺寸 CPU 模型时，不要因 auto→cuda 失败路径反复卸载
    if (
        _WHISPER_MODEL is not None
        and _WHISPER_KEY
        and _WHISPER_KEY[0] == model_id
        and _WHISPER_KEY[1] == 'cpu'
        and device == 'cuda'
    ):
        logger.info('reuse cached whisper CPU model (skip flaky CUDA reload)')
        return _WHISPER_MODEL
    logger.info(
        'loading faster-whisper model=%s device=%s compute=%s local=%s',
        model_size,
        device,
        compute,
        bool(local_dir),
    )
    kwargs = {'device': device, 'compute_type': compute}
    if local_dir:
        kwargs['local_files_only'] = True
    try:
        _WHISPER_MODEL = WhisperModel(model_id, **kwargs)
        _WHISPER_KEY = key
        if device == 'cuda':
            _WHISPER_CUDA_OK = True
    except Exception as exc:
        msg = str(exc)
        if device == 'cuda' and ('CUBLAS' in msg or 'CUDA' in msg or 'cuda' in msg.lower()):
            _WHISPER_CUDA_OK = False
            logger.warning('whisper CUDA load failed (%s), fall back CPU', msg)
            return _get_whisper_model(model_size, force_cpu=True, device_pref='cpu')
        raise
    return _WHISPER_MODEL


def _norm_unit(text: str) -> str:
    return re.sub(r'\s+', '', (text or '').lower())


def _expand_timed_units(start: float, end: float, text: str) -> list[tuple[float, float, str]]:
    units = [u for u in tokenize_lyric_text(text) if not u.isspace() and u.strip()]
    if not units:
        return []
    s, e = float(start), float(end)
    if e <= s:
        e = s + 0.05 * len(units)
    step = (e - s) / len(units)
    return [(s + i * step, s + (i + 1) * step, u) for i, u in enumerate(units)]


def _whisper_units_cache_key(audio_path: str, model_size: str) -> tuple:
    p = Path(audio_path)
    st = p.stat()
    return (str(p.resolve()), int(st.st_mtime_ns), int(st.st_size), model_size)


def _whisper_timed_units(
    audio_path: str,
    language: str | None,
    model_size: str,
    device_pref: str = 'auto',
) -> list[tuple[float, float, str]]:
    global _WHISPER_MODEL, _WHISPER_KEY, _WHISPER_CUDA_OK, _WHISPER_UNITS_CACHE
    cache_key = _whisper_units_cache_key(audio_path, model_size)
    cached = _WHISPER_UNITS_CACHE.get(cache_key)
    if cached is not None:
        logger.info('whisper units cache hit path=%s n=%s', audio_path, len(cached))
        return list(cached)

    def _run(force_cpu: bool = False):
        model = _get_whisper_model(model_size, force_cpu=force_cpu, device_pref=device_pref)
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            beam_size=5,
        )
        units: list[tuple[float, float, str]] = []
        for seg in segments:
            words = list(seg.words or [])
            if words:
                for w in words:
                    t = (w.word or '').strip()
                    if not t:
                        continue
                    units.extend(_expand_timed_units(float(w.start), float(w.end), t))
            else:
                t = (seg.text or '').strip()
                if t:
                    units.extend(_expand_timed_units(float(seg.start), float(seg.end), t))
        return units, info

    try:
        units, info = _run(force_cpu=False)
    except Exception as exc:
        msg = str(exc)
        if 'CUBLAS' in msg or 'CUDA' in msg or 'cuda' in msg.lower():
            logger.warning('whisper CUDA failed (%s), retry on CPU', msg)
            _WHISPER_CUDA_OK = False
            if _WHISPER_KEY and _WHISPER_KEY[1] == 'cuda':
                _WHISPER_MODEL = None
                _WHISPER_KEY = None
            units, info = _run(force_cpu=True)
        else:
            raise
    logger.info(
        'whisper units=%s lang=%s duration=%.1fs model=%s',
        len(units),
        getattr(info, 'language', language),
        float(getattr(info, 'duration', 0) or 0),
        model_size,
    )
    _WHISPER_UNITS_CACHE[cache_key] = list(units)
    return units


def _fill_none_times(starts: list, ends: list, t0: float, t1: float):
    n = len(starts)
    if n <= 0:
        return
    for i in range(n):
        if starts[i] is not None:
            continue
        prev = next((j for j in range(i - 1, -1, -1) if starts[j] is not None), None)
        nxt = next((j for j in range(i + 1, n) if starts[j] is not None), None)
        if prev is not None and nxt is not None and nxt > prev:
            ratio = (i - prev) / (nxt - prev)
            starts[i] = starts[prev] + (starts[nxt] - starts[prev]) * ratio
            ends[i] = starts[i] + max(0.03, (ends[nxt] - starts[prev]) / (nxt - prev))
        elif prev is not None:
            starts[i] = ends[prev]
            ends[i] = starts[i] + 0.12
        elif nxt is not None:
            starts[i] = max(t0, starts[nxt] - 0.12 * (nxt - i))
            ends[i] = starts[nxt]
    if any(x is None for x in starts):
        step = max(0.03, (t1 - t0) / n)
        for i in range(n):
            if starts[i] is None:
                starts[i] = t0 + i * step
                ends[i] = t0 + (i + 1) * step
    for i in range(n):
        if ends[i] is None or ends[i] <= starts[i]:
            ends[i] = starts[i] + 0.05
        if i + 1 < n and starts[i + 1] is not None:
            ends[i] = min(ends[i], max(starts[i] + 0.03, starts[i + 1]))


def _line_whisper_window(
    line: LyricLine,
    timed_units: list[tuple[float, float, str]],
    n_content: int,
) -> list[tuple[float, float, str]]:
    """取本句附近的 Whisper 片；硬截断句间大空白，并按静音间隙切开乐句。"""
    # 绝不能用「下一句之前」整段当窗口，否则句间伴奏空白会吞进后面所有人声
    hard_hi = min(line.end_sec, line.start_sec + max(10.0, n_content * 1.15))
    lo = line.start_sec - 0.2
    candidates = [u for u in timed_units if lo <= (u[0] + u[1]) * 0.5 < hard_hi]
    if not candidates:
        lo2 = line.start_sec - 0.4
        hi2 = min(line.end_sec, line.start_sec + max(12.0, n_content * 1.3))
        candidates = [u for u in timed_units if lo2 <= (u[0] + u[1]) * 0.5 < hi2]
    if not candidates:
        return []
    min_span = max(1.5, n_content * 0.55)
    window = [candidates[0]]
    for u in candidates[1:]:
        gap = u[0] - window[-1][1]
        span = window[-1][1] - window[0][0]
        # 已够唱时长后才允许按静音切句；过短窗口会把整句字挤到 0.1s 级
        if gap > 1.25 and span >= min_span:
            break
        if gap > 2.8:
            break
        window.append(u)
    # 仍过短则尽量多取候选，保证可唱跨度
    if window[-1][1] - window[0][0] < min_span:
        window = list(candidates)
        while len(window) > 1 and window[-1][1] - window[0][0] > max(min_span * 1.8, n_content * 1.2):
            window.pop()
    return window


def _align_line_with_whisper(line: LyricLine, timed_units: list[tuple[float, float, str]]) -> list[LyricWord]:
    tokens = tokenize_lyric_text(line.text)
    if not tokens:
        return []
    lyric_units = [tok for tok in tokens if not tok.isspace()]
    if not lyric_units:
        return _even_line_words(line, tokens, 0.78)
    window = _line_whisper_window(line, timed_units, len(lyric_units))
    if not window:
        return _even_line_words(line, tokens, 0.78)
    a = [_norm_unit(u) for u in lyric_units]
    b = [_norm_unit(u[2]) for u in window]
    sm = SequenceMatcher(None, a, b, autojunk=False)
    ratio = sm.ratio()
    # 唱歌 ASR 常错字：文本匹配差时仍用 Whisper 时间轴（相对能量对齐的增益）
    if ratio < 0.45:
        return _finalize_words(line, _words_from_weighted_timeline(tokens, window))
    starts: list = [None] * len(lyric_units)
    ends: list = [None] * len(lyric_units)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if i1 >= i2:
            continue
        if tag in ('equal', 'replace') and j1 < j2:
            ws, we = window[j1][0], window[j2 - 1][1]
            span_i = i2 - i1
            if span_i == 1:
                starts[i1], ends[i1] = ws, max(we, ws + 0.03)
            elif tag == 'equal' and (j2 - j1) == span_i:
                for k, i in enumerate(range(i1, i2)):
                    starts[i], ends[i] = window[j1 + k][0], window[j1 + k][1]
            else:
                step = max(0.03, (we - ws) / span_i)
                for k, i in enumerate(range(i1, i2)):
                    starts[i] = ws + k * step
                    ends[i] = ws + (k + 1) * step
    t0, t1 = float(window[0][0]), float(window[-1][1])
    _fill_none_times(starts, ends, t0, t1)
    hit = sum(1 for s in starts if s is not None)
    if hit < max(2, len(lyric_units) // 3):
        return _finalize_words(line, _words_from_weighted_timeline(tokens, window))
    # 禁止单字拖到下一句（句间大空白）
    max_end = t1 + 0.15
    words: list[LyricWord] = []
    ci = 0
    for i, tok in enumerate(tokens):
        if tok.isspace():
            t = starts[ci] if ci < len(starts) else t1
            words.append(LyricWord(float(t), float(t) + 0.01, tok, i))
            continue
        s, e = float(starts[ci]), float(ends[ci])
        e = min(e, max_end)
        if e - s > 1.8:
            e = s + 1.8
        words.append(LyricWord(s, max(e, s + 0.03), tok, i))
        ci += 1
    return _finalize_words(line, words)


def align_with_whisper(
    audio_path: str | Path,
    document: LyricDocument | None = None,
    language: str | None = 'zh',
    model_size: str = 'small',
    device_pref: str = 'auto',
) -> tuple[LyricDocument, bool]:
    """faster-whisper 对齐。返回 (doc, used_whisper)。失败则能量/均分且 used=False。"""
    audio_path = Path(audio_path)
    if document is None:
        document = LyricDocument()
    if not whisper_available():
        logger.warning('faster-whisper not installed, fallback energy/even')
        return prepare_word_timing(document, vocal_path=audio_path), False
    try:
        timed = _whisper_timed_units(str(audio_path), language=language, model_size=model_size, device_pref=device_pref)
    except Exception as exc:
        logger.warning('whisper align unavailable: %s', exc)
        return prepare_word_timing(document, vocal_path=audio_path), False
    if not timed:
        logger.warning('whisper produced no units, fallback energy/even')
        return prepare_word_timing(document, vocal_path=audio_path), False
    if not document.lines:
        lines = []
        buf: list[tuple[float, float, str]] = []
        last_end = None
        for u in timed:
            if last_end is not None and u[0] - last_end > 0.8 and buf:
                text = ''.join(x[2] for x in buf)
                lines.append(
                    LyricLine(
                        start_sec=buf[0][0],
                        end_sec=buf[-1][1],
                        text=text,
                        index=len(lines),
                        words=[LyricWord(s, e, t, i) for i, (s, e, t) in enumerate(buf)],
                    )
                )
                buf = []
            buf.append(u)
            last_end = u[1]
        if buf:
            text = ''.join(x[2] for x in buf)
            lines.append(
                LyricLine(
                    start_sec=buf[0][0],
                    end_sec=buf[-1][1],
                    text=text,
                    index=len(lines),
                    words=[LyricWord(s, e, t, i) for i, (s, e, t) in enumerate(buf)],
                )
            )
        return LyricDocument(title=document.title, artist=document.artist, lines=lines), True
    for line in document.lines:
        tokens = tokenize_lyric_text(line.text)
        line.words = _align_line_with_whisper(line, timed)
        line.text = ''.join(tokens) if tokens else line.text
    document.align_mode = 'whisper'
    logger.info('whisper align mapped lines=%s path=%s units=%s', len(document.lines), audio_path, len(timed))
    return document, True


def enhance_lrc_file(
    lrc_path: str | Path,
    vocal_path: str | Path | None = None,
    out_path: str | Path | None = None,
    use_whisper: bool = True,
    language: str | None = 'zh',
    model_size: str = 'small',
    device_pref: str = 'auto',
) -> tuple[Path, str]:
    """读取 LRC → Whisper/能量字级 → 写回 Enhanced LRC。返回 (path, mode)。"""
    lrc_path = Path(lrc_path)
    doc = load_enhanced_lrc(lrc_path)
    mode = 'even'
    if use_whisper and vocal_path and Path(vocal_path).is_file() and whisper_available():
        doc, ok = align_with_whisper(
            vocal_path, doc, language=language, model_size=model_size, device_pref=device_pref
        )
        mode = 'whisper' if ok else ('energy' if Path(str(vocal_path)).is_file() else 'even')
        if not ok:
            logger.warning('whisper requested but fell back to %s', mode)
    else:
        if use_whisper and not whisper_available():
            logger.warning('use_whisper requested but faster-whisper missing')
        doc = prepare_word_timing(doc, vocal_path=vocal_path)
        mode = 'energy' if vocal_path and Path(str(vocal_path)).is_file() else 'even'
    doc.align_mode = mode
    dest = Path(out_path) if out_path else lrc_path
    save_enhanced_lrc(doc, dest)
    logger.info('enhance_lrc mode=%s out=%s', mode, dest)
    return dest, mode


def find_vocal_for_song(song_dir: str | Path, title: str = '', song: dict | None = None) -> Path | None:
    """优先干声轨，便于对齐。"""
    if song:
        for key in ('vocal_path', 'converted_vocal_path', 'original_vocal_path', 'cover_path', 'play_path'):
            p = song.get(key)
            if p and Path(p).is_file() and 'instrumental' not in Path(p).name.lower():
                return Path(p)
    d = Path(song_dir)
    title = title or ''
    candidates = []
    if title:
        candidates.extend(
            [
                d / ('%s_converted_vocal.wav' % title),
                d / ('%s_vocals_noreverb.wav' % title),
                d / ('%s_original_vocal.wav' % title),
                d / ('%s_vocals.wav' % title),
                d / ('%s_cover.wav' % title),
            ]
        )
    candidates.extend(
        [
            d / 'vocals_noreverb.wav',
            d / 'vocals.wav',
            d / 'converted_vocal.wav',
        ]
    )
    for p in candidates:
        if p.is_file():
            return p
    for p in sorted(d.glob('*converted_vocal*.wav')):
        return p
    for p in sorted(d.glob('*vocals*.wav')):
        return p
    return None
