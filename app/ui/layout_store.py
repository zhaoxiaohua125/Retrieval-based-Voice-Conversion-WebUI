"""客户端 UI 布局持久化（写入 config/client.json 的 ui 字段）。"""

from app.config_store import ConfigStore


def load_ui_layout(config_path=None):
    store = ConfigStore(config_path).load()
    layout = store.get('ui', {})
    return layout if isinstance(layout, dict) else {}


def save_ui_layout(layout, config_path=None):
    store = ConfigStore(config_path).load()
    store.set('ui', layout)
    store.save()
    return layout
