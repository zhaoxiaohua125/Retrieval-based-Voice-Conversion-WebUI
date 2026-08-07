"""Index 文件查找（不导入 infer/torch，供 UI 冷启动使用）。"""

import os
import re
from pathlib import Path


def find_index_for_model(model_sid, outside_index_root=None, index_root=None, speaker_id=None):
    model_stem = os.path.splitext(os.path.basename(str(model_sid or '')))[0]
    experiment_name = re.sub(r'_e\d+_s\d+$', '', model_stem, flags=re.IGNORECASE)
    if not experiment_name:
        return ''
    try:
        target_speaker_id = None if speaker_id is None else int(speaker_id)
    except (TypeError, ValueError):
        target_speaker_id = None
    candidates = []
    roots = [outside_index_root, index_root]
    for index_root_path in roots:
        if not index_root_path or not os.path.isdir(index_root_path):
            continue
        for root, _, files in os.walk(index_root_path, topdown=False):
            for name in files:
                if not name.lower().endswith('.index') or 'trained' in name.lower():
                    continue
                index_stem = os.path.splitext(name)[0]
                lower_index = index_stem.lower()
                lower_experiment = experiment_name.lower()
                speaker_match = re.search(r'_spkid(\d+)$', index_stem, re.IGNORECASE)
                indexed_speaker_id = int(speaker_match.group(1)) if speaker_match else None
                if target_speaker_id is None and indexed_speaker_id is not None:
                    continue
                if target_speaker_id is not None and indexed_speaker_id is not None and indexed_speaker_id != target_speaker_id:
                    continue
                standard_match = (
                    lower_index.startswith(lower_experiment + '_added_')
                    or ('_' + lower_experiment + '_v1') in lower_index
                    or ('_' + lower_experiment + '_v2') in lower_index
                )
                exact_model_match = model_stem.lower() in lower_index
                if standard_match or exact_model_match:
                    path = os.path.abspath(os.path.join(root, name))
                    score = (
                        0 if indexed_speaker_id == target_speaker_id else 1,
                        0 if standard_match else 1,
                        0 if os.path.abspath(str(index_root_path)) == os.path.abspath(str(roots[0] or '')) else 1,
                        -os.path.getmtime(path),
                        path.lower(),
                    )
                    candidates.append((score, path))
    return min(candidates, default=(None, ''), key=lambda item: item[0])[1]


def find_index_for_model_project(model_sid, project_root=None, speaker_id=None):
    root = Path(project_root or '.').resolve()
    outside = root / 'assets' / 'indices'
    logs = root / 'logs'
    return find_index_for_model(
        model_sid,
        str(outside) if outside.is_dir() else None,
        str(logs) if logs.is_dir() else None,
        speaker_id=speaker_id,
    )
