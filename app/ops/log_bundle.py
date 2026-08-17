import json
import zipfile
from pathlib import Path

from app.ops.rotating_log import iter_all_log_files


def bundle_log_files(log_dir, output_zip, extra_files=None, env_info=None):
    log_path = Path(log_dir)
    output_path = Path(output_zip)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if env_info is not None:
            zf.writestr('environment.json', json.dumps(env_info, ensure_ascii=False, indent=2))
        if log_path.is_dir():
            for item in iter_all_log_files(log_path):
                arc = item.relative_to(log_path).as_posix() if log_path in item.parents else item.name
                if arc not in seen:
                    zf.write(item, arcname=arc)
                    seen.add(arc)
        for path in extra_files or []:
            src = Path(path)
            if not src.is_file():
                continue
            arc = src.name
            if log_path in src.parents:
                try:
                    arc = src.relative_to(log_path).as_posix()
                except ValueError:
                    pass
            if arc not in seen:
                zf.write(src, arcname=arc)
                seen.add(arc)
    return str(output_path.resolve())
