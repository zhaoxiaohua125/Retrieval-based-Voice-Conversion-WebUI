# RVC 客户端更新服务器

与 `app/` 客户端代码分离，提供版本 manifest 与更新包静态下载。

## 启动

```bash
cd server
pip install -r requirements.txt
python main.py
```

默认监听 `http://127.0.0.1:8765`。

## 接口

| 路径 | 说明 |
|------|------|
| `GET /version.json` | 版本 manifest |
| `GET /releases/*.zip` | 更新包下载 |
| `POST /api/logs/upload` | 客户端日志上报（multipart） |
| `GET /health` | 健康检查 |

## 发布更新包

```bash
python tools/publish_release.py path/to/update.zip --version 1.0.2 --desc "修复与优化"
```

客户端 `config/client.json` 中设置：

```json
"update": {
  "check_url": "http://127.0.0.1:8765/version.json",
  "auto_check": true
}
```

## 目录

- `data/version.json` — 当前线上版本信息
- `data/releases/` — 全量/增量 zip
- `data/logs/` — 客户端上传日志
