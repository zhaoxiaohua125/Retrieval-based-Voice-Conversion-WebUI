import json
import os
from copy import deepcopy
from pathlib import Path


DEFAULT_CONFIG = {
    'version': 1,
    'paths': {
        'log_dir': 'logs/client',
        'opt_dir': 'opt',
        'model_dir': 'assets/weights',
        'index_dir': 'assets/indices',
    },
    'update': {
        'check_url': '',
        'auto_check': True,
    },
    'audio': {
        'sample_rate': 48000,
        'block_ms': 200,
        'channels': 1,
        'dtype': 'float32',
        'input_device': None,
        'output_device': None,
        'hostapi': None,
        'wasapi_exclusive': False,
        'ring_ms': 500,
        'passthrough': False,
    },
    'rvc': {
        'f0_method': 'rmvpe',
        'index_rate': 0.75,
        'protect': 0.33,
        'f0_up_key': 0,
        'formant': 0.0,
    },
    'realtime': {
        'model_sid': '',
        'index_path': '',
        'pitch': 0,
        'formant': 0.0,
        'index_rate': 0.0,
        'f0_method': 'rmvpe',
        'block_time': 0.25,
        'crossfade_time': 0.05,
        'extra_time': 2.5,
        'sr_type': 'sr_model',
    },
    'msst': {
        'preset': 'normal',
    },
}


class ConfigStore:
    def __init__(self, path=None):
        root = Path(__file__).resolve().parents[1]
        self.path = Path(path or root / 'config' / 'client.json')
        self._data = deepcopy(DEFAULT_CONFIG)

    @property
    def data(self):
        return self._data

    def load(self):
        if not self.path.is_file():
            self._data = deepcopy(DEFAULT_CONFIG)
            return self
        with open(self.path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        merged = deepcopy(DEFAULT_CONFIG)
        self._merge_dict(merged, loaded if isinstance(loaded, dict) else {})
        self._data = merged
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, self.path)
        return self

    def get(self, dotted_key, default=None):
        node = self._data
        for part in str(dotted_key).split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted_key, value):
        parts = str(dotted_key).split('.')
        node = self._data
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise KeyError('config path conflict: %s' % dotted_key)
            node = child
        node[parts[-1]] = value
        return self

    def _merge_dict(self, base, override):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge_dict(base[key], value)
            else:
                base[key] = value
