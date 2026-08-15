"""服务端地址：origin + nginx 前缀，供登录/日志上报等 API 推导。"""

from urllib.parse import urljoin, urlparse


def cfg_get(config, key, default=None):
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


def resolve_server_root(config) -> str:
    """返回 http://host[/nginx_prefix]，无配置则空串。"""
    base = str(cfg_get(config, 'server.base_url', '') or '').strip().rstrip('/')
    prefix = str(cfg_get(config, 'server.nginx_prefix', '') or '').strip().strip('/')
    if not base:
        check = str(cfg_get(config, 'update.check_url', '') or '').strip()
        if check:
            parsed = urlparse(check)
            if parsed.scheme and parsed.netloc:
                base = '%s://%s' % (parsed.scheme, parsed.netloc)
                check_path = parsed.path.strip('/')
                if check_path and '/' in check_path:
                    # http://host/ai-sound/update.json -> 保留 ai-sound
                    first = check_path.split('/', 1)[0]
                    if first and first != 'api':
                        prefix = prefix or first
    if not base:
        return ''
    if not prefix:
        return base
    path = urlparse(base).path.strip('/')
    if path == prefix or path.endswith('/' + prefix):
        return base
    return '%s/%s' % (base, prefix)


def join_server_api(config, api_path: str) -> str:
    root = resolve_server_root(config)
    if not root:
        return ''
    return urljoin(root.rstrip('/') + '/', str(api_path or '').lstrip('/'))
