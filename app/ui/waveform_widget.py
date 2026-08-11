"""播放页波形：人声能量条 + 伴奏段平直虚线（对标声迹条形图）。"""

import time

import numpy as np
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from app.playback.waveform_peaks import is_vocal_energy_region, load_waveform_peaks, silence_threshold


class _WaveformLoadWorker(QThread):
    loaded = pyqtSignal(object, float, str)
    failed = pyqtSignal(str)

    def __init__(self, path: str, points=1200):
        super().__init__()
        self._path = path
        self._points = points

    def run(self):
        try:
            peaks, duration = load_waveform_peaks(self._path, self._points)
            self.loaded.emit(peaks, duration, self._path)
        except Exception as exc:
            self.failed.emit(str(exc))


class WaveformWidget(QWidget):
    seek_requested = pyqtSignal(float)
    WINDOW_SEC = 36.0
    PLAYHEAD_RATIO = 0.36
    BAR_GAP = 3
    SILENCE_FLOOR = 0.06

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks = None
        self._duration = 0.0
        self._target_sec = 0.0
        self._display_sec = 0.0
        self._sync_mono = time.monotonic()
        self._playing = False
        self._path = ''
        self._loader = None
        self._pulse = 0.0
        self.setMinimumHeight(88)
        self.setToolTip('基于 AI 人声音轨：平直虚线=前奏/间奏/尾奏（无人声）；竖条=有人唱歌')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_frame)
        self._timer.start(50)

    def load_file(self, path: str):
        path = str(path or '')
        if not path:
            self.clear()
            return
        if path == self._path and self._peaks is not None:
            return
        self._path = path
        self._peaks = None
        self._duration = 0.0
        self._target_sec = 0.0
        self._display_sec = 0.0
        self._playing = False
        self.update()
        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()
        self._loader = _WaveformLoadWorker(path)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.failed.connect(self._on_failed)
        self._loader.start()

    def _on_loaded(self, peaks, duration, path):
        if path != self._path:
            return
        self._peaks = peaks
        self._duration = float(duration or 0.0)
        self.update()

    def _on_failed(self, _msg: str):
        self._peaks = None
        self.update()

    def clear(self):
        self._path = ''
        self._peaks = None
        self._duration = 0.0
        self._target_sec = 0.0
        self._display_sec = 0.0
        self._playing = False
        self.update()

    def set_position_ratio(self, ratio: float):
        if self._duration > 0:
            self._sync(float(ratio or 0) * self._duration, self._playing)

    def set_position_sec(self, sec: float, duration: float | None = None):
        if duration is not None and duration > 0:
            self._duration = float(duration)
        self._sync(float(sec or 0), self._playing)

    def set_playback(self, sec: float, duration: float, playing: bool):
        if duration > 0:
            self._duration = float(duration)
        self._sync(float(sec or 0), bool(playing))

    def reset_position(self):
        self._sync(0.0, False)

    def _sync(self, sec: float, playing: bool):
        sec = max(0.0, min(sec, self._duration or sec))
        self._target_sec = sec
        self._playing = playing
        self._sync_mono = time.monotonic()
        if not playing:
            self._display_sec = sec

    def _on_frame(self):
        if not self._playing or self._duration <= 0:
            if abs(self._display_sec - self._target_sec) > 0.02:
                self._display_sec += (self._target_sec - self._display_sec) * 0.35
                self.update()
            return
        elapsed = time.monotonic() - self._sync_mono
        smooth = min(self._target_sec + elapsed, self._duration)
        if abs(smooth - self._display_sec) > 0.008:
            self._display_sec = smooth
            self._pulse = (self._pulse + 0.1) % (2 * np.pi)
            self.update()

    def _silence_threshold(self) -> float:
        return silence_threshold(self._peaks, self.SILENCE_FLOOR)

    def _amp_at(self, t: float) -> float:
        peaks = self._peaks
        if peaks is None or len(peaks) == 0 or self._duration <= 0:
            return 0.0
        idx = int(t / self._duration * (len(peaks) - 1))
        idx = max(0, min(idx, len(peaks) - 1))
        return float(peaks[idx])

    def is_inst_region(self, t: float | None = None) -> bool:
        t = self._display_sec if t is None else float(t)
        if self._peaks is None or self._duration <= 0:
            return False
        return not is_vocal_energy_region(t, self._peaks, self._duration, self._silence_threshold())

    def _window_span(self):
        return max(self.WINDOW_SEC, self._duration * 0.12)

    def _x_for_time(self, t: float, w: int) -> float:
        head = w * self.PLAYHEAD_RATIO
        return head + (t - self._display_sec) / self._window_span() * w

    def _time_for_x(self, x: float, w: int) -> float:
        head = w * self.PLAYHEAD_RATIO
        return self._display_sec + (x - head) / w * self._window_span()

    def _visible_bars(self, w: int):
        peaks = self._peaks
        if peaks is None or len(peaks) == 0 or self._duration <= 0:
            return []
        n = len(peaks)
        span = self._window_span()
        head = w * self.PLAYHEAD_RATIO
        t0 = self._display_sec - head / max(w, 1) * span
        t1 = self._display_sec + (w - head) / max(w, 1) * span
        i0 = max(0, int(t0 / self._duration * (n - 1)))
        i1 = min(n, int(t1 / self._duration * (n - 1)) + 2)
        if i1 <= i0:
            return []
        bar_count = max(48, min(160, w // self.BAR_GAP))
        step = max(1, (i1 - i0) // bar_count)
        out = []
        for i in range(i0, i1, step):
            j = min(i + step, i1)
            amp = float(np.max(peaks[i:j]))
            t = (i + j) * 0.5 / max(n - 1, 1) * self._duration
            out.append((t, amp))
        return out

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor('#f8fafc'))
        grad.setColorAt(1, QColor('#eef2ff'))
        p.fillRect(0, 0, w, h, grad)
        if self._peaks is None or len(self._peaks) == 0:
            p.setPen(QColor('#94a3b8'))
            hint = '波形加载中…' if self._path else '选择歌曲后显示波形（优先 AI 人声）'
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, hint)
            p.end()
            return
        mid = h // 2
        head_x = int(w * self.PLAYHEAD_RATIO)
        bar_w = max(2, self.BAR_GAP - 1)
        thresh = self._silence_threshold()
        pulse = (np.sin(self._pulse) * 0.06 + 1.0) if self._playing else 1.0
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        played_prog = int(head_x)
        if played_prog > 0:
            p.fillRect(0, h - 4, played_prog, 4, QColor(37, 99, 235, 70))
        base_pen = QPen(QColor('#cbd5e1'), 1, Qt.PenStyle.DashLine)
        p.setPen(base_pen)
        p.drawLine(0, mid, w, mid)
        for t, amp in self._visible_bars(w):
            x = self._x_for_time(t, w)
            if x < -bar_w or x > w + bar_w:
                continue
            xi = int(x)
            played = t <= self._display_sec
            silent = amp < thresh
            if silent:
                seg_pen = QPen(QColor('#64748b' if played else '#94a3b8'), 1, Qt.PenStyle.DashLine)
                p.setPen(seg_pen)
                p.drawLine(xi, mid, xi + bar_w, mid)
                continue
            dist = abs(x - head_x) / max(w * 0.1, 1.0)
            boost = max(0.0, 1.0 - dist) * 0.25 * pulse
            bh = max(4, int(amp * (h * 0.38) * (1.0 + boost)))
            color = QColor('#2563eb' if played else '#93c5fd')
            if dist < 0.8:
                color = QColor('#1d4ed8' if played else '#bfdbfe')
            p.fillRect(xi, mid - bh, bar_w, bh * 2, color)
        p.setPen(QPen(QColor('#2563eb'), 2))
        p.drawLine(head_x, 6, head_x, h - 10)
        p.end()

    def mousePressEvent(self, event):
        if self._peaks is None or self.width() <= 0 or self._duration <= 0:
            return
        t = self._time_for_x(event.position().x(), self.width())
        t = max(0.0, min(t, self._duration))
        self._display_sec = t
        self._target_sec = t
        self._sync_mono = time.monotonic()
        self.seek_requested.emit(t / self._duration)
        self.update()
        event.accept()
