"""扫描离线做歌输出，构建播放页歌库。"""

from pathlib import Path


def _stem_from_wav_name(name: str) -> str:
    stem = name
    for suffix in ('_cover', '_converted_vocal', '_instrumental', '_vocals', '_original_vocal', '_vocals_noreverb'):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def find_lrc_in_dir(folder: Path, stem: str):
    """在同目录查找 LRC：优先 {stem}.lrc，兼容 {stem}_cover.lrc 等。"""
    folder = Path(folder)
    if not stem:
        return None
    for name in (
        f'{stem}.lrc',
        f'{stem}.LRC',
        f'{stem}_cover.lrc',
        f'{stem}_cover.LRC',
        f'{stem}_vocals.lrc',
    ):
        p = folder / name
        if p.is_file():
            return str(p.resolve())
    for pattern in ('*.lrc', '*.LRC'):
        for p in sorted(folder.glob(pattern)):
            base = _stem_from_wav_name(p.stem)
            if base == stem or p.stem == stem:
                return str(p.resolve())
    return None


def _find_lrc(wav_path: Path):
    return find_lrc_in_dir(wav_path.parent, _stem_from_wav_name(wav_path.stem))


def _song_from_stem(stem: str, folder: Path):
    cover = folder / f'{stem}_cover.wav'
    vocal = folder / f'{stem}_converted_vocal.wav'
    inst = folder / f'{stem}_instrumental.wav'
    play_path = cover if cover.is_file() else vocal if vocal.is_file() else None
    if not play_path:
        return None
    ref = cover if cover.is_file() else vocal
    return {
        'id': str(play_path.resolve()),
        'title': stem,
        'cover_path': str(cover.resolve()) if cover.is_file() else None,
        'vocal_path': str(vocal.resolve()) if vocal.is_file() else None,
        'instrumental_path': str(inst.resolve()) if inst.is_file() else None,
        'play_path': str(play_path.resolve()),
        'lrc_path': _find_lrc(ref),
        'dir': str(folder.resolve()),
    }


def scan_song_library(project_root, dirs=None):
    root = Path(project_root)
    rel_dirs = dirs or ['opt', 'opt/task4_offline']
    songs = {}
    for rel in rel_dirs:
        folder = root / rel
        if not folder.is_dir():
            continue
        for wav in folder.glob('*.wav'):
            name = wav.stem
            for suffix in ('_cover', '_converted_vocal'):
                if name.endswith(suffix):
                    stem = name[: -len(suffix)]
                    entry = _song_from_stem(stem, folder)
                    if entry:
                        songs[entry['id']] = entry
                    break
    return sorted(songs.values(), key=lambda s: s['title'])
