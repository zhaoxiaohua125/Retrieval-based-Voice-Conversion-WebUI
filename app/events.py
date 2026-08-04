from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModuleId(str, Enum):
    SCHEDULER = 'scheduler'
    UI = 'ui'
    OPS = 'ops'
    AUDIO = 'audio'
    RVC = 'rvc'
    MSST = 'msst'
    LYRICS = 'lyrics'


class SignalType(str, Enum):
    STATUS = 'status'
    PROGRESS = 'progress'
    ERROR = 'error'
    LOG = 'log'
    CONFIG_CHANGED = 'config_changed'
    SHUTDOWN = 'shutdown'


@dataclass(frozen=True)
class BusMessage:
    signal: SignalType
    source: ModuleId
    payload: dict[str, Any] = field(default_factory=dict)
