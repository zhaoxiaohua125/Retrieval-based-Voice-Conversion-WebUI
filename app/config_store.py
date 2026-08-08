import json
import logging
import os
import threading
import time
from copy import deepcopy
from pathlib import Path

logger = logging.getLogger('rvc_client.config')

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
        'passthrough_gain': 2.0,
        'passthrough_ui': 100,
        'passthrough_block_ms': 50,
        'reverb_mix': 0.35,
        'reverb_decay': 0.72,
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
        'threhold': -60,
        'rms_mix_rate': 0.0,
        'I_noise_reduce': False,
        'O_noise_reduce': False,
    },
    'msst': {
        'preset': 'normal',
    },
    'lyrics': {
        'clock_source': 'manual',
        'osc_port': 9000,
        'osc_addresses': [
            '/transport/time',
            '/studioone/transport/time',
            '/time',
        ],
        'offset_ms': 0,
        'mtc_port': '',
        'sim_speed': 1.0,
    },
    'shortcuts': {
        'transport': 'Space',
        'ai_follow': '1',
        'ai_sing': '2',
        'reverb_talk': '3',
        'normal_talk': '4',
    },
}


class ConfigStore:
    _save_lock = threading.Lock()

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
        text = json.dumps(self._data, ensure_ascii=False, indent=2) + '\n'
        with self._save_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.json.tmp')
            last_err = None
            for attempt in range(6):
                try:
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(text)
                    for i in range(5):
                        try:
                            os.replace(tmp, self.path)
                            return self
                        except (PermissionError, OSError) as exc:
                            last_err = exc
                            time.sleep(0.04 * (i + 1))
                    with open(self.path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    try:
                        tmp.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return self
                except (PermissionError, OSError) as exc:
                    last_err = exc
                    time.sleep(0.05 * (attempt + 1))
            logger.warning('config save failed after retries: %s', last_err)
            raise last_err

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
