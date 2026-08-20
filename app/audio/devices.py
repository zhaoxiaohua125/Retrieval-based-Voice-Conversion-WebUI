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
        is_in = 'input' in lower or 'speakers (' in lower
        is_out = ('output' in lower or ' out' in lower) and not is_in
        if 'aux' in lower:
            role = 'voicemeeter_aux_in' if is_in else 'voicemeeter_aux_out'
        elif 'vaio3' in lower:
            role = 'voicemeeter_vaio3_in' if is_in else 'voicemeeter_vaio3_out'
        elif 'b1' in lower and is_out:
            role = 'voicemeeter_b1_out'
        elif is_in and ('vaio' in lower or 'input' in lower):
            role = 'voicemeeter_vaio_in'
        elif is_out:
            role = 'voicemeeter_out'
        elif 'hardware' in lower:
            role = 'voicemeeter_hardware_in'
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


def _first_device(items: list[AudioDeviceInfo], predicates) -> int | None:
    for pred in predicates:
        for dev in items:
            if pred(dev):
                return dev.index
    return None


def pick_voicemeeter_defaults(devices: list[AudioDeviceInfo] | None = None):
    """Potato 优先 Aux，避开主 VAIO（留给抖音/直播采 VoiceMeeter Output）。

    采集：Out B1 → Aux Output → VAIO3 Output → 其它 VM Output
    播放：Aux Input → VAIO3 Input → 主 VAIO Input
    """
    items = devices if devices is not None else list_devices()

    def _in(dev):
        return dev.max_input_channels > 0

    def _out(dev):
        return dev.max_output_channels > 0

    def _vm(dev):
        return 'voicemeeter' in dev.name.lower()

    input_idx = _first_device(
        items,
        (
            lambda d: _in(d) and _vm(d) and 'b1' in d.name.lower(),
            lambda d: _in(d) and d.voicemeeter_role == 'voicemeeter_aux_out',
            lambda d: _in(d) and _vm(d) and 'aux' in d.name.lower() and 'out' in d.name.lower(),
            lambda d: _in(d) and d.voicemeeter_role == 'voicemeeter_vaio3_out',
            lambda d: _in(d) and _vm(d) and 'vaio3' in d.name.lower() and 'out' in d.name.lower(),
            lambda d: _in(d) and d.voicemeeter_role in ('voicemeeter_b1_out', 'voicemeeter_out'),
            lambda d: _in(d) and _vm(d) and 'out' in d.name.lower(),
            lambda d: _in(d),
        ),
    )
    output_idx = _first_device(
        items,
        (
            lambda d: _out(d) and d.voicemeeter_role == 'voicemeeter_aux_in',
            lambda d: _out(d) and _vm(d) and 'aux' in d.name.lower() and 'input' in d.name.lower(),
            lambda d: _out(d) and d.voicemeeter_role == 'voicemeeter_vaio3_in',
            lambda d: _out(d) and _vm(d) and 'vaio3' in d.name.lower() and 'input' in d.name.lower(),
            lambda d: _out(d) and d.voicemeeter_role == 'voicemeeter_vaio_in',
            lambda d: _out(d) and _vm(d) and 'input' in d.name.lower(),
            lambda d: _out(d),
        ),
    )
    return input_idx, output_idx


def pick_monitor_default(devices: list[AudioDeviceInfo] | None, stream_out_idx: int | None):
    """直播输出为 Aux 时，监听默认走 VAIO Input（与 stream 分离）。"""
    if stream_out_idx is None:
        return None
    items = devices if devices is not None else list_devices()
    stream = next((d for d in items if d.index == stream_out_idx), None)
    roles = ('voicemeeter_vaio_in', 'voicemeeter_vaio3_in')
    if stream and stream.voicemeeter_role == 'voicemeeter_aux_in':
        roles = ('voicemeeter_vaio_in', 'voicemeeter_vaio3_in')
    elif stream and stream.voicemeeter_role == 'voicemeeter_vaio_in':
        roles = ('voicemeeter_aux_in', 'voicemeeter_vaio3_in')
    else:
        roles = ('voicemeeter_vaio_in', 'voicemeeter_aux_in', 'voicemeeter_vaio3_in')
    for role in roles:
        for dev in items:
            if dev.max_output_channels > 0 and dev.voicemeeter_role == role and dev.index != stream_out_idx:
                return dev.index
    for dev in items:
        if dev.max_output_channels > 0 and 'voicemeeter' in dev.tags and dev.index != stream_out_idx:
            return dev.index
    return None


def resolve_monitor_device(
    monitor_ref,
    stream_out_idx: int | None,
    hostapi: str | None = None,
    devices: list[AudioDeviceInfo] | None = None,
):
    ref = str(monitor_ref or '').strip().lower()
    if ref in ('off', 'none', 'false', '0', 'disable', 'disabled'):
        return None
    items = devices if devices is not None else list_devices(hostapi=hostapi)
    if not is_auto_device(monitor_ref):
        idx = resolve_device_index(monitor_ref, need_output=True, devices=items)
        if idx is not None and idx != stream_out_idx:
            return idx
        return None
    return pick_monitor_default(items, stream_out_idx)


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
