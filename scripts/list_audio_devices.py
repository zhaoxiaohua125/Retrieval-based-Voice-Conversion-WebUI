"""列出 sounddevice 设备编号，便于填写 config/client.json。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audio.devices import list_devices, pick_voicemeeter_defaults


def main():
    devices = list_devices()
    print('=== Voicemeeter 相关设备（填 audio.input_device / output_device 用 index）===\n')
    vm = [d for d in devices if 'voicemeeter' in d.name.lower()]
    for d in vm:
        io = []
        if d.max_input_channels > 0:
            io.append('IN')
        if d.max_output_channels > 0:
            io.append('OUT')
        print('[index=%s] [%s] %s' % (d.index, '/'.join(io) or '-', d.name))
    in_idx, out_idx = pick_voicemeeter_defaults(devices)
    print('\n=== 推荐（麦克风→Out B1 录，RVC→Input VAIO 播）===')
    if in_idx is not None:
        print('input_device  (RVC 采集): %s  →  %s' % (in_idx, next(d.name for d in devices if d.index == in_idx)))
    if out_idx is not None:
        print('output_device (RVC 播放): %s  →  %s' % (out_idx, next(d.name for d in devices if d.index == out_idx)))
    print('\n=== config/client.json 示例 ===')
    print("""{
  "audio": {
    "input_device": %s,
    "output_device": %s,
    "sample_rate": 48000,
    "block_ms": 200
  },
  "realtime": {
    "model_sid": "孙悟空模型.pth"
  }
}""" % (in_idx if in_idx is not None else 'null', out_idx if out_idx is not None else 'null'))


if __name__ == '__main__':
    main()
