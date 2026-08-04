"""Studio One OSC 播放头读取。

Studio One 需在「外部设备 → OSC」中把播放位置映射为 UDP 浮点秒数发到本机。
常用监听端口见 config/client.json → lyrics.osc_port（默认 9000）。
地址示例（以 DAW 实际映射为准）：
  - /studioone/transport/time
  - /transport/time
  - /time
"""

import logging
import threading
import time

logger = logging.getLogger('rvc_client.lyrics.osc')


class OscPlaybackClock:
    """后台 OSC 监听线程，维护最新播放时间 T（秒）。"""

    def __init__(self, port: int = 9000, addresses: list[str] | None = None):
        self.port = int(port)
        self.addresses = set(addresses or ['/transport/time', '/studioone/transport/time', '/time'])
        self._time = None
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self._running = False

    @property
    def available(self):
        try:
            import pythonosc  # noqa: F401
            return True
        except ImportError:
            return False

    def current_time(self):
        with self._lock:
            return self._time

    def _set_time(self, value):
        try:
            t = float(value)
        except (TypeError, ValueError):
            return
        with self._lock:
            self._time = max(0.0, t)

    def _on_message(self, address, *args):
        if self.addresses and address not in self.addresses:
            return
        if not args:
            return
        self._set_time(args[0])

    def start(self):
        if self._running:
            return self
        if not self.available:
            raise RuntimeError('python-osc 未安装，请 pip install python-osc')
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import ThreadingOSCUDPServer

        disp = Dispatcher()
        disp.set_default_handler(self._on_message)
        self._server = ThreadingOSCUDPServer(('0.0.0.0', self.port), disp)
        self._thread = threading.Thread(target=self._server.serve_forever, name='osc-clock', daemon=True)
        self._running = True
        self._thread.start()
        logger.info('OSC clock listening port=%s addresses=%s', self.port, sorted(self.addresses))
        return self

    def stop(self):
        self._running = False
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        self._thread = None


class ManualPlaybackClock:
    """手动/测试用时钟。"""

    def __init__(self, time_sec: float = 0.0):
        self._time = float(time_sec)

    def current_time(self):
        return self._time

    def set_time(self, time_sec: float):
        self._time = max(0.0, float(time_sec))


class SimPlaybackClock:
    """仿真时钟：按倍速递增，用于无 DAW 验收。"""

    def __init__(self, speed: float = 1.0):
        self.speed = float(speed)
        self._origin = time.perf_counter()
        self._base = 0.0
        self._running = False

    def start(self, base: float = 0.0):
        self._base = float(base)
        self._origin = time.perf_counter()
        self._running = True

    def stop(self):
        self._running = False

    def current_time(self):
        if not self._running:
            return self._base
        return self._base + (time.perf_counter() - self._origin) * self.speed
