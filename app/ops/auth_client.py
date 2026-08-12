"""客户端登录：调用 server /api/auth/login。"""

import json
import logging
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger('rvc_client.auth')


def resolve_login_url(config) -> str:
    explicit = str(_cfg_get(config, 'auth.login_url', '') or '').strip()
    if explicit:
        return explicit
    check = str(_cfg_get(config, 'update.check_url', '') or '').strip()
    if not check:
        return 'http://127.0.0.1:8765/api/auth/login'
    parsed = urlparse(check)
    if not parsed.scheme or not parsed.netloc:
        return 'http://127.0.0.1:8765/api/auth/login'
    return urljoin('%s://%s/' % (parsed.scheme, parsed.netloc), 'api/auth/login')


def login(username: str, password: str, config, timeout=10.0) -> dict:
    name = (username or '').strip()
    if not name:
        return {'ok': False, 'message': '请输入账号'}
    if not str(password or ''):
        return {'ok': False, 'message': '请输入密码'}
    url = resolve_login_url(config)
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=3.0)) as client:
            resp = client.post(url, json={'username': name, 'password': password})
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get('ok'):
                return {
                    'ok': True,
                    'message': data.get('message') or '登录成功',
                    'token': data.get('token'),
                    'user': data.get('user') or {},
                }
            msg = data.get('message') or ('HTTP %s' % resp.status_code)
            return {'ok': False, 'message': msg}
    except httpx.ConnectError:
        return {'ok': False, 'message': '无法连接登录服务（%s），请确认 server 已启动' % url}
    except httpx.TimeoutException:
        return {'ok': False, 'message': '登录请求超时，请检查网络或 server 状态'}
    except json.JSONDecodeError:
        return {'ok': False, 'message': '登录服务返回格式错误'}
    except Exception as exc:
        logger.warning('login failed: %s', exc)
        return {'ok': False, 'message': '登录失败：%s' % exc}


def _cfg_get(config, key, default=None):
    if hasattr(config, 'get'):
        return config.get(key, default)
    if isinstance(config, dict):
        node = config
        for part in str(key).split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node
    return default
