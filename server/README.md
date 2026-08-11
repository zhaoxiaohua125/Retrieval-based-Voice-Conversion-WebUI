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

### 按 Git 提交自动生成增量 zip（推荐）

在仓库根目录：

```bash
# 自 tag v0.1.0-demo 至今所有客户端相关改动 → dist/update-0.1.1.zip
python scripts/make_update_zip.py --since v0.1.0-demo --version 0.1.1

# 打包并发布到本机 server
python scripts/make_update_zip.py --since v0.1.0-demo --version 0.1.1 --publish

# 先看会打哪些文件
python scripts/make_update_zip.py --since v0.1.0-demo --list-only

# 指定 commit 范围
python scripts/make_update_zip.py --since abc1234 --to HEAD --version 0.1.2
```

规则：对比 `git diff since..to`，只纳入 `packaging/manifest.json` 定义的客户端路径（`app/`、`config/` 等），自动排除 `server/`、`dist/` 等。

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
