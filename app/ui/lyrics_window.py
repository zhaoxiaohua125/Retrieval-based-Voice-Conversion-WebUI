"""悬浮歌词窗口（无边框、置顶、可拖拽；支持逐字高亮；横/竖屏切换）。"""

import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from app.ui.layout_store import load_ui_layout, save_ui_layout

_ORIENT_H = 'horizontal'
_ORIENT_V = 'vertical'
_SIZE_H = (560, 140)
_SIZE_V = (160, 560)
_SPAN_RE = re.compile(r'<span\s+style="([^"]*)">(.*?)</span>', re.I | re.S)


class LyricsWindow(QWidget):
    """独立悬浮歌词层，供 OBS 采集。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._orientation = _ORIENT_H
        self._restored_geo = False
        self._last_html = ''
        self._last_text = ''
        self._last_highlight = False
        self._use_html = False
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.9)
        self.label = QLabel('歌词悬浮窗', self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.label.setStyleSheet(
            'color: #ffffff; background: rgba(0,0,0,170); padding: 16px; border-radius: 8px;'
        )
        font = QFont('Microsoft YaHei UI', 20)
        self.label.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self._restore_layout()
        self._apply_orientation(force_size=not self._restored_geo)

    def set_orientation(self, orientation: str):
        o = _ORIENT_V if orientation == _ORIENT_V else _ORIENT_H
        if o == self._orientation:
            return
        self._orientation = o
        self._apply_orientation(force_size=True)
        self._refresh_text()
        self._save_layout()

    def toggle_orientation(self):
        self.set_orientation(_ORIENT_V if self._orientation == _ORIENT_H else _ORIENT_H)

    def orientation(self) -> str:
        return self._orientation

    def set_line(self, text, highlight=False):
        self._use_html = False
        self._last_text = text or ''
        self._last_html = ''
        self._last_highlight = bool(highlight)
        color = '#fbbf24' if highlight else '#ffffff'
        if self._orientation == _ORIENT_V:
            parts = ['<span style="color:%s;">%s</span>' % (color, c) for c in self._last_text if c not in '\n\r']
            self.label.setText('<br>'.join(parts) if parts else '')
        else:
            self.label.setText('<span style="color:%s;">%s</span>' % (color, self._last_text))

    def set_lyric_tick(self, payload: dict):
        html = (payload or {}).get('html') or ''
        text = (payload or {}).get('text') or ''
        if html and (payload or {}).get('has_words'):
            self._use_html = True
            self._last_html = html
            self._last_text = text
            self.label.setText(self._html_to_vertical(html) if self._orientation == _ORIENT_V else html)
        else:
            self.set_line(text, highlight=True)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_h = QAction('横屏展示', self)
        act_h.setCheckable(True)
        act_h.setChecked(self._orientation == _ORIENT_H)
        act_h.triggered.connect(lambda: self.set_orientation(_ORIENT_H))
        act_v = QAction('竖屏展示', self)
        act_v.setCheckable(True)
        act_v.setChecked(self._orientation == _ORIENT_V)
        act_v.triggered.connect(lambda: self.set_orientation(_ORIENT_V))
        menu.addAction(act_h)
        menu.addAction(act_v)
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._save_layout()
        event.accept()

    def closeEvent(self, event):
        self._save_layout()
        super().closeEvent(event)

    def _apply_orientation(self, force_size=False):
        if self._orientation == _ORIENT_V:
            self.label.setWordWrap(False)
            if force_size:
                self.resize(*_SIZE_V)
        else:
            self.label.setWordWrap(True)
            if force_size:
                self.resize(*_SIZE_H)

    def _refresh_text(self):
        if self._use_html and self._last_html:
            self.label.setText(
                self._html_to_vertical(self._last_html) if self._orientation == _ORIENT_V else self._last_html
            )
        else:
            self.set_line(self._last_text, highlight=self._last_highlight)

    def _html_to_vertical(self, html: str) -> str:
        parts, pos = [], 0
        for m in _SPAN_RE.finditer(html or ''):
            for c in (html or '')[pos:m.start()]:
                if c not in '\n\r':
                    parts.append(c)
            style, content = m.group(1), m.group(2)
            for c in content:
                if c in '\n\r':
                    continue
                parts.append('<span style="%s">%s</span>' % (style, c))
            pos = m.end()
        for c in (html or '')[pos:]:
            if c not in '\n\r':
                parts.append(c)
        if not parts:
            return '<br>'.join(c for c in (html or '') if c not in '\n\r')
        return '<br>'.join(parts)

    def _restore_layout(self):
        cfg = (load_ui_layout().get('lyrics_window') or {})
        o = cfg.get('orientation') or _ORIENT_H
        self._orientation = _ORIENT_V if o == _ORIENT_V else _ORIENT_H
        geo = cfg.get('geometry')
        if isinstance(geo, (list, tuple)) and len(geo) == 4:
            self.setGeometry(int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
            self._restored_geo = True
        else:
            self._restored_geo = False

    def _save_layout(self):
        layout = load_ui_layout()
        g = self.geometry()
        layout['lyrics_window'] = {
            'orientation': self._orientation,
            'geometry': [g.x(), g.y(), g.width(), g.height()],
        }
        save_ui_layout(layout)
