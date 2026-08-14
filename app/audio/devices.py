"""sounddevice 设备枚举与 Voicemeeter/VB-Cable 标记。"""

from dataclasses import dataclass, field

VOICEMEETER_ROLES = (
    'voicemeeter_hardware_in',
    'voicemeeter_vaio_in',
    'voicemeeter_aux_in',
    'voicemeeter_out',
    'vb_cable',
)


@dataclass
class AudioDeviceInfo:
    index: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    tags: list[str] = field(default_factory=list)
    voicemeeter_role: str | None = None

    def to_dict(self):
        return {
            'index': self.index,
            'name': self.name,
            'hostapi': self.hostapi,
            'max_input_channels': self.max_input_channels,
            'max_output_channels': self.max_output_channels,
            'default_samplerate': self.default_samplerate,
            'tags': list(self.tags),
            'voicemeeter_role': self.voicemeeter_role,
        }


def _tag_device(name: str) -> tuple[list[str], str | None]:
    lower = name.lower()
    tags = []
    role = None
    if 'voicemeeter' in lower:
        tags.append('voicemeeter')
        if 'aux' in lower and 'input' in lower:
            role = 'voicemeeter_aux_in'
        elif 'vaio' in lower and 'input' in lower:
            role = 'voicemeeter_vaio_in'
        elif 'input' in lower or 'hardware' in lower:
            role = 'voicemeeter_hardware_in'
        elif 'out' in lower:
            role = 'voicemeeter_out'
    if 'vb-audio' in lower or 'vb cable' in lower or 'cable input' in lower or 'cable output' in lower:
        tags.append('vb_cable')
        if role is None:
            role = 'vb_cable'
    if 'wasapi' in lower:
        tags.append('wasapi_name_hint')
    return tags, role


def list_hostapis():
    import sounddevice as sd

    return [item['name'] for item in sd.query_hostapis()]


def list_devices(hostapi: str | None = None) -> list[AudioDeviceInfo]:
    """枚举音频设备，可选按 HostAPI 过滤。"""
    import sounddevice as sd

    hostapis = {item['name']: item for item in sd.query_hostapis()}
    hostapi_map = {}
    for api_name, api in hostapis.items():
        for dev_idx in api.get('devices', []):
            hostapi_map[dev_idx] = api_name
    result = []
    for index, item in enumerate(sd.query_devices()):
        api_name = hostapi_map.get(index, '')
        if hostapi and api_name != hostapi:
            continue
        name = str(item.get('name', ''))
        tags, role = _tag_device(name)
        if api_name and 'WASAPI' in api_name:
            tags.append('wasapi')
        elif api_name and 'MME' in api_name:
            tags.append('mme')
        elif api_name and 'DirectSound' in api_name:
            tags.append('directsound')
        result.append(
            AudioDeviceInfo(
                index=index,
                name=name,
                hostapi=api_name,
                max_input_channels=int(item.get('max_input_channels', 0)),
                max_output_channels=int(item.get('max_output_channels', 0)),
                default_samplerate=float(item.get('default_samplerate', 0) or 0),
                tags=sorted(set(tags)),
                voicemeeter_role=role,
            )
        )
    return result


_AUTO_ALIASES = frozenset({'', 'auto', 'voicemeeter', 'default'})


def is_auto_device(ref) -> bool:
    if ref is None:
        return True
    if isinstance(ref, bool):
        return False
    if isinstance(ref, (int, float)):
        return False
    return str(ref).strip().lower() in _AUTO_ALIASES


def pick_voicemeeter_defaults(devices: list[AudioDeviceInfo] | None = None):
    """RVC 客户端推荐设备：采集 Voicemeeter Out B1，播放到 Voicemeeter Input VAIO。"""
    items = devices if devices is not None else list_devices()
    input_idx = None
    output_idx = None
    for dev in items:
        lower = dev.name.lower()
        if dev.max_input_channels > 0 and 'voicemeeter' in lower and 'out' in lower:
            if 'b1' in lower:
                input_idx = dev.index
                break
    if input_idx is None:
        for dev in items:
            if dev.max_input_channels > 0 and dev.voicemeeter_role == 'voicemeeter_out':
                input_idx = dev.index
                break
    for dev in items:
        lower = dev.name.lower()
        if dev.max_output_channels > 0 and 'voicemeeter' in lower and 'input' in lower and 'vaio' in lower:
            output_idx = dev.index
            break
    if output_idx is None:
        for dev in items:
            if dev.max_output_channels > 0 and dev.voicemeeter_role == 'voicemeeter_vaio_in':
                output_idx = dev.index
                break
    if input_idx is None:
        for dev in items:
            if dev.max_input_channels > 0:
                input_idx = dev.index
                break
    if output_idx is None:
        for dev in items:
            if dev.max_output_channels > 0:
                output_idx = dev.index
                break
    return input_idx, output_idx


def find_device_by_name(
    name: str,
    devices: list[AudioDeviceInfo] | None = None,
    *,
    need_input: bool = False,
    need_output: bool = False,
) -> AudioDeviceInfo | None:
    items = devices if devices is not None else list_devices()
    needle = str(name or '').strip().lower()
    if not needle:
        return None
    partial = []
    for dev in items:
        if need_input and dev.max_input_channels <= 0:
            continue
        if need_output and dev.max_output_channels <= 0:
            continue
        lower = dev.name.lower()
        if lower == needle:
            return dev
        if needle in lower:
            partial.append(dev)
    return partial[0] if partial else None


def resolve_device_index(
    ref,
    *,
    need_input: bool = False,
    need_output: bool = False,
    hostapi: str | None = None,
    devices: list[AudioDeviceInfo] | None = None,
) -> int | None:
    """把配置中的设备引用解析为 sounddevice index；支持 auto / 名称 / 旧版数字。"""
    items = devices if devices is not None else list_devices(hostapi=hostapi)
    if is_auto_device(ref):
        return None
    if isinstance(ref, (int, float)) or (isinstance(ref, str) and str(ref).strip().isdigit()):
        idx = int(ref)
        for dev in items:
            if dev.index != idx:
                continue
            if need_input and dev.max_input_channels <= 0:
                return None
            if need_output and dev.max_output_channels <= 0:
                return None
            return idx
        return None
    found = find_device_by_name(str(ref), items, need_input=need_input, need_output=need_output)
    return found.index if found else None


def resolve_io_devices(
    input_ref=None,
    output_ref=None,
    hostapi: str | None = None,
    devices: list[AudioDeviceInfo] | None = None,
):
    """解析输入/输出设备；auto 或失效引用时回退 Voicemeeter 推荐。"""
    items = devices if devices is not None else list_devices(hostapi=hostapi)
    def_in, def_out = pick_voicemeeter_defaults(items)
    in_idx = def_in if is_auto_device(input_ref) else resolve_device_index(
        input_ref, need_input=True, devices=items
    )
    out_idx = def_out if is_auto_device(output_ref) else resolve_device_index(
        output_ref, need_output=True, devices=items
    )
    if in_idx is None:
        in_idx = def_in
    if out_idx is None:
        out_idx = def_out
    return in_idx, out_idx


def device_ref_for_config(ref, devices: list[AudioDeviceInfo] | None = None) -> str:
    """写入 client.json 的稳定引用：auto 或设备名，永不写易变 index。"""
    if is_auto_device(ref):
        return 'auto'
    if isinstance(ref, (int, float)) or (isinstance(ref, str) and str(ref).strip().isdigit()):
        items = devices if devices is not None else list_devices()
        idx = int(ref)
        for dev in items:
            if dev.index == idx:
                return dev.name
        return 'auto'
    name = str(ref or '').strip()
    return name or 'auto'


def device_summary(devices: list[AudioDeviceInfo] | None = None) -> dict:
    items = devices if devices is not None else list_devices()
    tagged = [d for d in items if d.tags]
    vm = [d for d in items if 'voicemeeter' in d.tags]
    return {
        'total': len(items),
        'tagged': len(tagged),
        'voicemeeter': len(vm),
        'hostapis': list_hostapis(),
    }
