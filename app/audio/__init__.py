"""音频硬件 IO 模块（sounddevice + 环形缓冲）。"""

from app.audio.devices import (
    AudioDeviceInfo,
    device_ref_for_config,
    device_summary,
    is_auto_device,
    list_devices,
    list_hostapis,
    pick_voicemeeter_defaults,
    resolve_io_devices,
)
from app.audio.ring_buffer import RingBuffer
from app.audio.service import AudioService
from app.audio.stream_manager import AudioStreamConfig, AudioStreamManager

__all__ = [
    'AudioDeviceInfo',
    'AudioService',
    'AudioStreamConfig',
    'AudioStreamManager',
    'RingBuffer',
    'device_ref_for_config',
    'device_summary',
    'is_auto_device',
    'list_devices',
    'list_hostapis',
    'pick_voicemeeter_defaults',
    'resolve_io_devices',
]
