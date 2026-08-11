"""RVC 客户端更新与日志上报服务（与 app/ 客户端分离）。"""

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RELEASES = DATA / 'releases'
LOGS = DATA / 'logs'

app = FastAPI(title='RVC Client Update Server', version='1.0.0')
RELEASES.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/version.json')
def version_json():
    path = DATA / 'version.json'
    if not path.is_file():
        return JSONResponse({'error': 'version.json missing'}, status_code=404)
    return JSONResponse(json.loads(path.read_text(encoding='utf-8')))


app.mount('/releases', StaticFiles(directory=str(RELEASES)), name='releases')


@app.post('/api/logs/upload')
async def upload_log(log_file: UploadFile = File(...), environment: str = Form(''), client_version: str = Form('')):
    name = Path(log_file.filename or 'client.log').name
    dest = LOGS / name
    dest.write_bytes(await log_file.read())
    meta = LOGS / (name + '.meta.json')
    meta.write_text(
        json.dumps({'environment': environment, 'client_version': client_version}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return {'ok': True, 'path': str(dest.name)}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('main:app', host='0.0.0.0', port=8765, reload=False)
