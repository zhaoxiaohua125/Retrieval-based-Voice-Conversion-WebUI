import json
import zipfile
from datetime import datetime
from pathlib import Path


def bundle_log_files(log_dir, output_zip, extra_files=None, env_info=None):
    log_path = Path(log_dir)
    output_path = Path(output_zip)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if env_info is not None:
            zf.writestr('environment.json', json.dumps(env_info, ensure_ascii=False, indent=2))
        if log_path.is_dir():
            for item in sorted(log_path.glob('client.log*')):
                if item.is_file():
                    zf.write(item, arcname=item.name)
        for path in extra_files or []:
            src = Path(path)
            if src.is_file():
                zf.write(src, arcname=src.name)
    return str(output_path.resolve())
