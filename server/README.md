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
| `POST /api/auth/login` | 账号密码登录（校验 `bus_user` 表） |
| `GET /api/auth/health` | 登录模块 / 数据库连通性 |
| `GET /health` | 健康检查（含 `db` 字段） |

## 登录验证（MySQL）

表：`bus_user`（字段见业务库 DDL）

### 配置

复制示例并按实际库名修改（**server 优先读 `config/db.json`；若不存在则自动回退到 `config/db.json.example`**）：

```bash
copy config\db.json.example config\db.json
```

`config/db.json` 支持：

```json
{
  "host": "127.0.0.1",
  "port": 13306,
  "user": "root",
  "password": "2020@Wkrj+-",
  "database": "你的库名",
  "charset": "utf8mb4",
  "pool_size": 5,
  "max_overflow": 10,
  "pool_recycle": 3600
}
```

也可用环境变量：`MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE`。

连接池：**SQLAlchemy QueuePool** + `pool_pre_ping`（业界常用，自动剔除失效连接）。

### 登录 API

```http
POST /api/auth/login
Content-Type: application/json

{"username": "demo", "password": "123456"}
```

成功：

```json
{
  "ok": true,
  "message": "登录成功",
  "token": "...",
  "user": {
    "user_id": "...",
    "user_name": "demo",
    "user_real": "昵称",
    "user_money": 0.0,
    "start_time": null,
    "end_time": null
  }
}
```

失败：`401` 账号或密码错误；`403` 账号未生效/已过期；`503` 数据库不可用。

密码仅支持 **32 位小写 MD5**（客户端传明文，服务端比对 MD5）。登录成功会更新 `login_time`、`update_time`。

### 目录结构

```
server/
  config/settings.py   # 配置加载
  db/engine.py         # SQLAlchemy 连接池
  db/user_repo.py      # bus_user 查询
  auth/service.py      # 登录业务
  auth/router.py       # HTTP 路由
```

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
  "check_url": "http://127.0.0.1:8765/version.json"
},
"logs": {
  "auto_upload_crash": true,
  "upload_url": ""
}
```

`upload_url` 留空时，自动从 `update.check_url` 推导为 `/api/logs/upload`。崩溃/异常退出时会打包 `client.log`、`crash.log` 等并 POST 上报。

## 目录

- `data/version.json` — 当前线上版本信息
- `data/releases/` — 全量/增量 zip
- `data/logs/` — 客户端上传日志
