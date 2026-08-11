import json
from pathlib import Path

import httpx


def upload_log_bundle(url, zip_path, env_info=None, timeout=30.0):
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError('log bundle not found: %s' % zip_path)
    files = {'log_file': (path.name, path.read_bytes(), 'application/zip')}
    data = {}
    if env_info is not None:
        data['environment'] = json.dumps(env_info, ensure_ascii=False)
        data['client_version'] = str(env_info.get('client_version') or '')
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, data=data, files=files)
        response.raise_for_status()
        return response.json() if response.content else {'ok': True}
