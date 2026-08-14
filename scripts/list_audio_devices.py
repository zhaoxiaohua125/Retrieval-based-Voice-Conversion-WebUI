"""列出 sounddevice 设备，便于核对 Voicemeeter 自动识别结果。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audio.devices import list_devices, pick_voicemeeter_defaults


def main():
    devices = list_devices()
    print('=== Voicemeeter 相关设备（client.json 请写 auto 或设备名，勿写 index）===\n')
    vm = [d for d in devices if 'voicemeeter' in d.name.lower()]
    for d in vm:
        io = []
        if d.max_input_channels > 0:
            io.append('IN')
        if d.max_output_channels > 0:
            io.append('OUT')
        print('[index=%s] [%s] %s' % (d.index, '/'.join(io) or '-', d.name))
    in_idx, out_idx = pick_voicemeeter_defaults(devices)
    print('\n=== auto 推荐（Potato：Aux，避开主 VAIO 留给抖音）===')
    if in_idx is not None:
        print('input_device  (RVC 采集): auto → [%s] %s' % (in_idx, next(d.name for d in devices if d.index == in_idx)))
    if out_idx is not None:
        print('output_device (RVC 播放): auto → [%s] %s' % (out_idx, next(d.name for d in devices if d.index == out_idx)))
    print('\n=== config/client.json 示例 ===')
    print("""{
  "audio": {
    "input_device": "auto",
    "output_device": "auto",
    "hostapi": "Windows WASAPI",
    "sample_rate": 48000,
    "block_ms": 200
  },
  "realtime": {
    "model_sid": "孙悟空模型.pth"
  }
}""")


if __name__ == '__main__':
    main()
