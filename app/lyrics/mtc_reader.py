"""LoopMIDI / MTC 备选时钟（骨架）。"""

import logging
import threading

logger = logging.getLogger('rvc_client.lyrics.mtc')


class MtcPlaybackClock:
    """接收 MIDI Time Code 并换算为秒（需 mido + 可用 MIDI 端口）。"""

    def __init__(self, port_name: str = ''):
        self.port_name = port_name
        self._time = 0.0
        self._fps = 30.0
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._input = None

    @property
    def available(self):
        try:
            import mido  # noqa: F401
            return True
        except ImportError:
            return False

    def current_time(self):
        with self._lock:
            return self._time

    def _update_qframe(self, msg):
        # 简化：仅累积分帧，完整 SMPTE 解码在集成阶段可扩展
        if msg.type != 'quarter_frame':
            return
        frame_type = msg.frame_type
        value = msg.value
        with self._lock:
            if frame_type == 0:
                self._time = int(self._time) // 60 * 60 + value
            elif frame_type == 1:
                self._time = (int(self._time) % 60 // 10) * 10 + value + int(self._time) // 60 * 60
            elif frame_type == 4:
                self._time = int(self._time) + value / self._fps

    def start(self):
        if self._running:
            return self
        if not self.available:
            raise RuntimeError('mido 未安装，MTC 时钟不可用')
        import mido

        names = mido.get_input_names()
        target = self.port_name
        if not target:
            for name in names:
                if 'loopmidi' in name.lower() or 'mtc' in name.lower():
                    target = name
                    break
        if not target or target not in names:
            raise RuntimeError('未找到 MTC MIDI 输入端口，请配置 lyrics.mtc_port')
        self._input = mido.open_input(target)
        self._running = True

        def _loop():
            import time as _time
            while self._running and self._input is not None:
                for msg in self._input.iter_pending():
                    self._update_qframe(msg)
                _time.sleep(0.002)

        self._thread = threading.Thread(target=_loop, name='mtc-clock', daemon=True)
        self._thread.start()
        logger.info('MTC clock listening port=%s', target)
        return self

    def stop(self):
        self._running = False
        if self._input is not None:
            self._input.close()
            self._input = None
        self._thread = None
