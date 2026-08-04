import logging
import platform
import sys


def collect_environment_info():
    info = {
        'client_version': None,
        'platform': platform.platform(),
        'python': sys.version.split()[0],
        'machine': platform.machine(),
        'processor': platform.processor() or '',
        'cuda': _collect_cuda_info(),
        'audio_devices': _collect_audio_devices(),
        'windows': _collect_windows_info(),
    }
    try:
        from app.ops.version import CLIENT_VERSION
        info['client_version'] = CLIENT_VERSION
    except Exception:
        pass
    return info


def _collect_cuda_info():
    try:
        import torch
    except ImportError:
        return {'available': False, 'reason': 'torch not installed'}
    data = {
        'available': bool(torch.cuda.is_available()),
        'device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        'torch_version': torch.__version__,
        'cuda_version': getattr(torch.version, 'cuda', None),
    }
    if torch.cuda.is_available():
        try:
            data['device_name'] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            data['total_memory_gb'] = round(props.total_memory / (1024 ** 3), 2)
        except Exception as exc:
            data['device_error'] = str(exc)
    return data


def _collect_audio_devices():
    try:
        import sounddevice as sd
    except ImportError:
        return {'available': False, 'devices': [], 'reason': 'sounddevice not installed'}
    devices = []
    try:
        for index, item in enumerate(sd.query_devices()):
            devices.append({
                'index': index,
                'name': item.get('name', ''),
                'max_input_channels': int(item.get('max_input_channels', 0)),
                'max_output_channels': int(item.get('max_output_channels', 0)),
                'default_samplerate': float(item.get('default_samplerate', 0) or 0),
            })
    except Exception as exc:
        return {'available': False, 'devices': [], 'error': str(exc)}
    return {'available': True, 'devices': devices}


def _collect_windows_info():
    if platform.system() != 'Windows':
        return {'is_windows': False}
    data = {'is_windows': True}
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion')
        for name, field in (('ProductName', 'product'), ('DisplayVersion', 'display_version'), ('CurrentBuild', 'build')):
            try:
                data[field] = winreg.QueryValueEx(key, name)[0]
            except OSError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass
    return data
