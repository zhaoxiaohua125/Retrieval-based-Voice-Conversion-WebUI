"""悬浮歌词窗口（无边框、置顶、可拖拽/缩放；双行展示；横/竖屏切换）。"""

import ctypes
import re
from html import escape

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter, QPalette,
)
from PyQt6.QtWidgets import QBoxLayout, QLabel, QLayout, QMenu, QSizePolicy, QWidget

from app.ui.layout_store import load_ui_layout, save_ui_layout

_ORIENT_H = 'horizontal'
_ORIENT_V = 'vertical'
_SIZE_H = (640, 180)
_SIZE_V = (260, 620)
_MIN_H = (280, 100)
_MIN_V = (140, 280)
_EDGE = 8
_QWIDGETSIZE_MAX = 16777215
_CHROMA_DEFAULT = '#00FF00'
_TEXT_DEFAULT = '#FFFFFF'
_HIGHLIGHT_DEFAULT = '#FB923C'
_SPAN_RE = re.compile(r'<span\s+style="([^"]*)">(.*?)</span>', re.I | re.S)
_EDGE_CURSORS = {
    'left': Qt.CursorShape.SizeHorCursor,
    'right': Qt.CursorShape.SizeHorCursor,
    'top': Qt.CursorShape.SizeVerCursor,
    'bottom': Qt.CursorShape.SizeVerCursor,
    'top-left': Qt.CursorShape.SizeFDiagCursor,
    'bottom-right': Qt.CursorShape.SizeFDiagCursor,
    'top-right': Qt.CursorShape.SizeBDiagCursor,
    'bottom-left': Qt.CursorShape.SizeBDiagCursor,
}


class LyricsWindow(QWidget):
    """独立桌面歌词层：可被直播伴侣窗口采集；酷狗式当前行+下一行。"""

    _tick = pyqtSignal(dict)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self._config = config
        self._bg_alpha = 170
        self._win_opacity = 0.9
        self._capture_mode = 'normal'
        self._chroma_color = _CHROMA_DEFAULT
        self._chroma_text_color = _TEXT_DEFAULT
        self._chroma_highlight_color = _HIGHLIGHT_DEFAULT
        self._click_through = True
        self._stay_on_top = False
        self._drag_pos = None
        self._resize_edge = None
        self._resize_origin = None
        self._orientation = _ORIENT_H
        self._restored_geo = False
        self._last_html = ''
        self._last_bot_html = ''
        self._last_text = ''
        self._last_next = ''
        self._last_highlight = False
        self._use_html = False
        self._anchor_window = None
        self._chroma_font = QFont('Microsoft YaHei UI', 10)
        self.setWindowTitle('桌面歌词')
        self._apply_window_flags()
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.line_cur = QLabel('歌词悬浮窗', self)
        self.line_next = QLabel('', self)
        for lab in (self.line_cur, self.line_next):
            lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setWordWrap(True)
            lab.setMinimumSize(0, 0)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._layout.addWidget(self.line_cur, stretch=1)
        self._layout.addWidget(self.line_next, stretch=1)
        self._tick.connect(self._apply_lyric_tick)
        self._restore_layout()
        self.apply_desktop_style()
        self._apply_orientation(force_size=not self._restored_geo)
        self._sync_font()

    def apply_desktop_style(
        self, bg_alpha=None, opacity=None, capture_mode=None, chroma_color=None,
        click_through=None, stay_on_top=None, text_color=None, highlight_color=None,
    ):
        cfg = self._config
        if capture_mode is None:
            capture_mode = cfg.get('lyrics.desktop_capture_mode', 'normal') if cfg else 'normal'
        if chroma_color is None:
            chroma_color = cfg.get('lyrics.desktop_chroma_color', _CHROMA_DEFAULT) if cfg else _CHROMA_DEFAULT
        if bg_alpha is None:
            bg_alpha = cfg.get('lyrics.desktop_bg_alpha', 170) if cfg else 170
        if opacity is None:
            opacity = cfg.get('lyrics.desktop_opacity', 0.9) if cfg else 0.9
        mode = str(capture_mode or 'normal').strip().lower()
        chroma = mode in ('chroma', 'chroma_key', 'live', 'green')
        self._capture_mode = 'chroma' if chroma else 'normal'
        if click_through is None:
            click_through = cfg.get('lyrics.desktop_click_through') if cfg else None
        if click_through is None:
            click_through = chroma
        if stay_on_top is None:
            stay_on_top = cfg.get('lyrics.desktop_stay_on_top') if cfg else None
        if stay_on_top is None:
            stay_on_top = not chroma
        self._click_through = bool(click_through)
        self._stay_on_top = bool(stay_on_top)
        color = str(chroma_color or _CHROMA_DEFAULT).strip() or _CHROMA_DEFAULT
        if not color.startswith('#'):
            color = '#' + color
        self._chroma_color = self._norm_hex(color, _CHROMA_DEFAULT)
        if text_color is None:
            text_color = cfg.get('lyrics.desktop_chroma_text_color', _TEXT_DEFAULT) if cfg else _TEXT_DEFAULT
        if highlight_color is None:
            highlight_color = cfg.get('lyrics.desktop_chroma_highlight_color', _HIGHLIGHT_DEFAULT) if cfg else _HIGHLIGHT_DEFAULT
        self._chroma_text_color = self._norm_hex(text_color, _TEXT_DEFAULT)
        hl = str(highlight_color or _HIGHLIGHT_DEFAULT).strip()
        self._chroma_highlight_color = '' if hl.lower() == 'same' else self._norm_hex(hl, self._chroma_text_color)
        self._bg_alpha = max(0, min(255, int(bg_alpha if bg_alpha is not None else 170)))
        self._win_opacity = max(0.2, min(1.0, float(opacity if opacity is not None else 0.9)))
        if self._capture_mode == 'chroma':
            self._win_opacity = 1.0
            want_trans = False
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            pal = self.palette()
            pal.setColor(QPalette.ColorRole.Window, QColor(self._chroma_color))
            self.setPalette(pal)
            self.setStyleSheet('background-color:%s;' % self._chroma_color)
        else:
            want_trans = self._bg_alpha < 255
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
            self.setStyleSheet('')
            self.setAutoFillBackground(not want_trans)
        self.setWindowOpacity(self._win_opacity)
        old = self.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if old != want_trans:
            vis = self.isVisible()
            if vis:
                self.hide()
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, want_trans)
            if vis:
                self.show()
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, want_trans)
        self._apply_window_flags()
        self._apply_orientation(force_size=False)
        self._refresh_text()
        self.sync_desktop_stack()

    def _norm_hex(self, color, default=_TEXT_DEFAULT):
        s = str(color or default).strip()
        if not s.startswith('#'):
            s = '#' + s
        return s.upper() if len(s) in (4, 7) else str(default).upper()

    def _chroma_fill_color(self, bold=False) -> QColor:
        if bold and self._chroma_highlight_color:
            return QColor(self._chroma_highlight_color)
        return QColor(self._chroma_text_color)

    def set_anchor_window(self, window):
        self._anchor_window = window

    def sync_desktop_stack(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self._click_through)
        self._expose_for_capture()
        if not self.isVisible():
            return
        if self._stay_on_top:
            self.raise_()
            return
        self._nudge_if_overlaps()
        self.lower()
        anchor = self._anchor_window
        if anchor is not None and anchor.isVisible():
            anchor.raise_()
        QTimer.singleShot(0, self._expose_for_capture)
        QTimer.singleShot(120, self._expose_for_capture)

    def click_through(self) -> bool:
        return self._click_through

    def stay_on_top(self) -> bool:
        return self._stay_on_top

    def set_click_through(self, enabled: bool, persist=True):
        self._click_through = bool(enabled)
        if persist and self._config:
            self._config.set('lyrics.desktop_click_through', self._click_through)
            try:
                self._config.save()
            except Exception:
                pass
        self._expose_for_capture()
        self.sync_desktop_stack()

    def set_stay_on_top(self, enabled: bool, persist=True):
        self._stay_on_top = bool(enabled)
        if persist and self._config:
            self._config.set('lyrics.desktop_stay_on_top', self._stay_on_top)
            try:
                self._config.save()
            except Exception:
                pass
        self._apply_window_flags()
        self.sync_desktop_stack()

    def _nudge_if_overlaps(self):
        anchor = self._anchor_window
        if anchor is None or not anchor.isVisible():
            return
        mine = self.frameGeometry()
        other = anchor.frameGeometry()
        if not mine.intersects(other):
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = other.right() + 8
        y = other.top()
        if x + mine.width() > avail.right():
            x = other.left() - mine.width() - 8
        if x < avail.left():
            x = avail.left() + 8
        if y + mine.height() > avail.bottom():
            y = max(avail.top(), avail.bottom() - mine.height())
        self.move(int(x), int(y))
        self._save_layout()

    def move_beside_anchor(self):
        anchor = self._anchor_window
        if anchor is None or not anchor.isVisible():
            return False
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return False
        other = anchor.frameGeometry()
        avail = screen.availableGeometry()
        x = other.right() + 8
        y = other.top()
        if x + self.width() > avail.right():
            x = other.left() - self.width() - 8
        if x < avail.left():
            x = avail.left() + 8
        if y + self.height() > avail.bottom():
            y = max(avail.top(), avail.bottom() - self.height())
        self.move(int(x), int(y))
        self._save_layout()
        self.sync_desktop_stack()
        return True

    def _apply_window_flags(self):
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if self._stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        vis = self.isVisible()
        if vis:
            self.hide()
        self.setWindowFlags(flags)
        if vis:
            self.show()

    def paintEvent(self, event):
        if self._capture_mode == 'chroma':
            p = QPainter(self)
            p.fillRect(self.rect(), QColor(self._chroma_color))
            self._paint_chroma_lyrics(p)
            return
        if self._bg_alpha >= 255:
            p = QPainter(self)
            p.fillRect(self.rect(), QColor(0, 0, 0))
            return
        super().paintEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_desktop_stack()

    def _expose_for_capture(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            gwl, app, tool, layered, transparent = -20, 0x00040000, 0x00000080, 0x00080000, 0x00000020
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long, set_long = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
                get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
                get_long.restype = ctypes.c_int64
                set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int64]
                set_long.restype = ctypes.c_int64
            else:
                get_long, set_long = user32.GetWindowLongW, user32.SetWindowLongW
            style = (get_long(hwnd, gwl) | app) & ~tool
            if self._capture_mode == 'chroma':
                style &= ~layered
            if self._click_through:
                style |= transparent
            else:
                style &= ~transparent
            set_long(hwnd, gwl, style)
            pos_flags = 0x0013
            if self.isVisible() and not self._stay_on_top:
                user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, pos_flags)
            else:
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        except Exception:
            pass

    def minimumSizeHint(self):
        return QSize(*(_MIN_V if self._orientation == _ORIENT_V else _MIN_H))

    def sizeHint(self):
        return QSize(*(_SIZE_V if self._orientation == _ORIENT_V else _SIZE_H))

    def set_orientation(self, orientation: str):
        o = _ORIENT_V if orientation == _ORIENT_V else _ORIENT_H
        if o == self._orientation:
            return
        self._save_layout()
        self._orientation = o
        # 先清空竖排 <br> 富文本，否则 Windows 会按内容把高度撑到上千
        self.line_cur.setText('')
        self.line_next.setText('')
        self._apply_orientation(force_size=False)
        x, y, w, h = self._pick_mode_geometry()
        self._set_geometry_forced(x, y, w, h)
        self._refresh_text()
        self._sync_font()
        self._set_geometry_forced(x, y, w, h)
        self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        if self.width() != w or self.height() != h or self.x() != x or self.y() != y:
            self.setMaximumSize(w, h)
            self.setGeometry(x, y, w, h)
            self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        self._save_layout()

    def toggle_orientation(self):
        self.set_orientation(_ORIENT_V if self._orientation == _ORIENT_H else _ORIENT_H)

    def orientation(self) -> str:
        return self._orientation

    def set_line(self, text, highlight=False, next_text=''):
        self._apply_line(text, highlight=highlight, next_text=next_text)

    def set_lyric_tick(self, payload: dict):
        self._tick.emit(dict(payload or {}))

    def _apply_lyric_tick(self, payload: dict):
        # 酷狗双行页：page_top/page_bot，两行唱完才翻页
        top_html = (payload or {}).get('page_top_html') or ''
        bot_html = (payload or {}).get('page_bot_html') or ''
        top_text = (payload or {}).get('page_top_text')
        bot_text = (payload or {}).get('page_bot_text')
        if top_text is None and bot_text is None:
            top_text = (payload or {}).get('text') or ''
            bot_text = (payload or {}).get('next_text') or ''
            top_html = (payload or {}).get('html') or ''
            bot_html = ''
        top_text = top_text or ''
        bot_text = bot_text or ''
        self._use_html = bool(top_html or bot_html)
        self._last_html = top_html
        self._last_bot_html = bot_html
        self._last_text = top_text
        self._last_next = bot_text
        self._last_highlight = True
        self._paint_pair(top_html, bot_html, top_text, bot_text)

    def _apply_line(self, text, highlight=False, next_text=''):
        self._use_html = False
        self._last_text = text or ''
        self._last_html = ''
        self._last_bot_html = ''
        self._last_next = next_text or ''
        self._last_highlight = bool(highlight)
        self._paint_pair('', '', self._last_text, self._last_next)

    def _parse_chroma_chars(self, text: str, html: str):
        chars = []
        if html:
            for m in _SPAN_RE.finditer(html or ''):
                bold = 'font-weight' in m.group(1) and ('700' in m.group(1) or 'bold' in m.group(1).lower())
                for c in m.group(2):
                    if c not in '\n\r':
                        chars.append((c, bold))
        if not chars:
            chars = [(c, False) for c in (text or '') if c not in '\n\r']
        return chars

    def _make_chroma_font(self, px: int, bold=False) -> QFont:
        f = QFont('Microsoft YaHei UI')
        f.setPixelSize(max(10, int(px)))
        f.setBold(bool(bold))
        f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        return f

    def _draw_chroma_char(self, p: QPainter, x: int, y: int, ch: str, font: QFont, bold=False):
        p.setFont(font)
        fill = self._chroma_fill_color(bold)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            p.setPen(QColor(0, 0, 0))
            p.drawText(x + dx, y + dy, ch)
        p.setPen(fill)
        p.drawText(x, y, ch)

    def _draw_chroma_run(self, p: QPainter, x: int, y: int, chars, base_px: int):
        if not chars:
            return x
        cx = x
        for ch, bold in chars:
            f = self._make_chroma_font(base_px, bold=bold)
            fm = QFontMetrics(f)
            self._draw_chroma_char(p, cx, y, ch, f, bold=bold)
            cx += fm.horizontalAdvance(ch)
        return cx

    def _paint_chroma_lyrics(self, p: QPainter):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        top = self._parse_chroma_chars(self._last_text, self._last_html if self._use_html else '')
        bot = self._parse_chroma_chars(self._last_next, self._last_bot_html if self._use_html else '')
        w, h = self.width(), self.height()
        if self._orientation == _ORIENT_V:
            n = max(len(top), len(bot), 1)
            px = max(8, min(28, int((h - 28) / (n * 1.25)), int(w * 0.22)))
            f = self._make_chroma_font(px)
            fm = QFontMetrics(f)
            step = max(fm.height() + 2, int(px * 1.15))
            col_w = w // 2
            x_top = col_w // 2
            x_bot = col_w + col_w // 2
            y0 = 10 + fm.ascent()
            for i, (ch, bold) in enumerate(top):
                cf = self._make_chroma_font(px, bold)
                self._draw_chroma_char(p, x_top - fm.horizontalAdvance(ch) // 2, y0 + i * step, ch, cf, bold)
            for i, (ch, bold) in enumerate(bot):
                yy = h - 10 - (len(bot) - i) * step
                cf = self._make_chroma_font(px, bold)
                self._draw_chroma_char(p, x_bot - fm.horizontalAdvance(ch) // 2, yy, ch, cf, bold)
        else:
            px = max(12, min(42, int(h * 0.26)))
            f = self._make_chroma_font(px)
            fm = QFontMetrics(f)
            self._draw_chroma_run(p, 14, 10 + fm.ascent(), top, px)
            bot_w = sum(QFontMetrics(self._make_chroma_font(px, b)).horizontalAdvance(c) for c, b in bot)
            self._draw_chroma_run(p, max(14, w - bot_w - 14), h - 10 - fm.descent(), bot, max(10, px - 2))

    def _paint_pair(self, top_html: str, bot_html: str, top_text: str, bot_text: str):
        if top_text:
            self._last_text = top_text
        if bot_text is not None:
            self._last_next = bot_text or ''
        if top_html or bot_html:
            self._last_html = top_html or ''
            self._last_bot_html = bot_html or ''
            self._use_html = bool(top_html or bot_html)
        if self._capture_mode == 'chroma':
            self.line_cur.hide()
            self.line_next.hide()
            self.line_cur.setText('')
            self.line_next.setText('')
            self._sync_font()
            self.update()
            return
        self.line_cur.show()
        self.line_next.show()
        if self._orientation == _ORIENT_V:
            self.line_cur.setText(
                self._html_to_vertical(top_html) if top_html else self._plain_vertical(top_text, '#ffffff')
            )
            self.line_next.setText(
                self._html_to_vertical(bot_html) if bot_html else self._plain_vertical(bot_text, self._next_color())
            )
        else:
            self.line_cur.setText(top_html or ('<span style="color:#ffffff;">%s</span>' % escape(top_text) if top_text else ''))
            self.line_next.setText(
                bot_html or ('<span style="color:%s;">%s</span>' % (self._next_color(), escape(bot_text)) if bot_text else '')
            )
        self._sync_font()

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
        menu.addSeparator()
        act_passthrough = QAction('鼠标穿透', self)
        act_passthrough.setCheckable(True)
        act_passthrough.setChecked(self._click_through)
        act_passthrough.triggered.connect(lambda on: self.set_click_through(bool(on)))
        act_top = QAction('窗口置顶', self)
        act_top.setCheckable(True)
        act_top.setChecked(self._stay_on_top)
        act_top.triggered.connect(lambda on: self.set_stay_on_top(bool(on)))
        menu.addAction(act_passthrough)
        menu.addAction(act_top)
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        edge = self._hit_edge(event.position().toPoint())
        if edge:
            self._resize_edge = edge
            self._resize_origin = (event.globalPosition().toPoint(), self.geometry())
            self._drag_pos = None
        else:
            self._resize_edge = None
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_edge and event.buttons() & Qt.MouseButton.LeftButton and self._resize_origin:
            self._do_resize(event.globalPosition().toPoint())
            event.accept()
            return
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        edge = self._hit_edge(event.position().toPoint())
        self.setCursor(QCursor(_EDGE_CURSORS.get(edge, Qt.CursorShape.ArrowCursor)))
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        was_resize = self._resize_edge is not None
        self._resize_edge = None
        self._resize_origin = None
        if was_resize:
            self._sync_font()
        self._save_layout()
        event.accept()

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_edge is None:
            self._sync_font()

    def closeEvent(self, event):
        self._save_layout()
        super().closeEvent(event)

    def _hit_edge(self, pos):
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        left, right = x <= _EDGE, x >= w - _EDGE
        top, bottom = y <= _EDGE, y >= h - _EDGE
        if top and left:
            return 'top-left'
        if top and right:
            return 'top-right'
        if bottom and left:
            return 'bottom-left'
        if bottom and right:
            return 'bottom-right'
        if left:
            return 'left'
        if right:
            return 'right'
        if top:
            return 'top'
        if bottom:
            return 'bottom'
        return None

    def _do_resize(self, global_pos):
        origin_pos, geo = self._resize_origin
        dx = global_pos.x() - origin_pos.x()
        dy = global_pos.y() - origin_pos.y()
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        edge = self._resize_edge
        if 'left' in edge:
            x, w = x + dx, w - dx
        if 'right' in edge:
            w = w + dx
        if 'top' in edge:
            y, h = y + dy, h - dy
        if 'bottom' in edge:
            h = h + dy
        if w < self.minimumWidth():
            if 'left' in edge:
                x = x - (self.minimumWidth() - w)
            w = self.minimumWidth()
        if h < self.minimumHeight():
            if 'top' in edge:
                y = y - (self.minimumHeight() - h)
            h = self.minimumHeight()
        self.setGeometry(x, y, w, h)

    def _sync_font(self):
        if self._orientation == _ORIENT_V:
            n_top = len([c for c in (self._last_text or '') if c not in '\n\r'])
            n_bot = len([c for c in (self._last_next or '') if c not in '\n\r'])
            n = max(n_top, n_bot, 1)
            # 左右列共用整窗高度；用像素字号，并按字数压到能排下
            avail = max(60, self.height() - 28)
            by_chars = int(avail / (n * 1.25))
            by_width = int(self.width() * 0.22)
            px = max(8, min(28, by_chars, by_width))
            font = QFont('Microsoft YaHei UI')
            font.setPixelSize(px)
            self.line_cur.setFont(font)
            self.line_next.setFont(font)
        else:
            px = max(12, min(42, int(self.height() * 0.26)))
            font = QFont('Microsoft YaHei UI')
            font.setPixelSize(px)
            self.line_cur.setFont(font)
            font2 = QFont('Microsoft YaHei UI')
            font2.setPixelSize(max(10, px - 2))
            self.line_next.setFont(font2)
        if self._capture_mode == 'chroma':
            self._chroma_font = self._make_chroma_font(px if self._orientation == _ORIENT_H else max(8, min(28, int((self.height() - 28) / 12))))
            self.update()

    def _label_bg(self):
        if self._capture_mode == 'chroma':
            return 'transparent'
        return 'rgba(0,0,0,%d)' % self._bg_alpha

    def _next_color(self):
        return '#ffffff' if self._capture_mode == 'chroma' else '#93c5fd'

    def _apply_orientation(self, force_size=False):
        bg = self._label_bg()
        next_c = self._next_color()
        radius = '0' if self._capture_mode == 'chroma' else '8px'
        if self._orientation == _ORIENT_V:
            self.setMinimumSize(*_MIN_V)
            self._layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.line_cur.setWordWrap(False)
            self.line_next.setWordWrap(False)
            self.line_cur.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.line_next.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.line_cur.setStyleSheet(
                'color:#ffffff;background:%s;padding:10px 6px 10px 10px;'
                'border-top-left-radius:%s;border-bottom-left-radius:%s;' % (bg, radius, radius)
            )
            self.line_next.setStyleSheet(
                'color:%s;background:%s;padding:10px 10px 10px 6px;'
                'border-top-right-radius:%s;border-bottom-right-radius:%s;' % (next_c, bg, radius, radius)
            )
        else:
            self.setMinimumSize(*_MIN_H)
            self._layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.line_cur.setWordWrap(True)
            self.line_next.setWordWrap(True)
            self.line_cur.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.line_next.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.line_cur.setStyleSheet(
                'color:#ffffff;background:%s;padding:10px 14px 4px 14px;'
                'border-top-left-radius:%s;border-top-right-radius:%s;' % (bg, radius, radius)
            )
            self.line_next.setStyleSheet(
                'color:%s;background:%s;padding:4px 14px 10px 14px;'
                'border-bottom-left-radius:%s;border-bottom-right-radius:%s;' % (next_c, bg, radius, radius)
            )
        if force_size:
            x, y, w, h = self._pick_mode_geometry()
            self._set_geometry_forced(x, y, w, h)
            self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        self._sync_font()

    def _mode_geo_key(self):
        return 'geometry_v' if self._orientation == _ORIENT_V else 'geometry_h'

    def _default_size(self):
        return _SIZE_V if self._orientation == _ORIENT_V else _SIZE_H

    def _min_size(self):
        return _MIN_V if self._orientation == _ORIENT_V else _MIN_H

    def _normalize_mode_size(self, w: int, h: int):
        mw, mh = self._min_size()
        dw, dh = self._default_size()
        w, h = max(mw, int(w)), max(mh, int(h))
        if self._orientation == _ORIENT_H:
            if h >= w or h > max(dh * 2, 360):
                return dw, dh
        else:
            if w >= h or w > max(dw * 2, 400) or h > max(dh * 2, 900):
                return dw, dh
        return w, h

    def _pick_mode_geometry(self):
        """恢复该方向上次的位置+尺寸；没有记录则保留当前位置、用默认尺寸。"""
        cfg = (load_ui_layout().get('lyrics_window') or {})
        geo = cfg.get(self._mode_geo_key())
        dw, dh = self._default_size()
        if isinstance(geo, (list, tuple)) and len(geo) == 4:
            w, h = self._normalize_mode_size(geo[2], geo[3])
            return int(geo[0]), int(geo[1]), w, h
        return self.x(), self.y(), dw, dh

    def _set_geometry_forced(self, x: int, y: int, w: int, h: int):
        mw, mh = self._min_size()
        w, h = max(mw, int(w)), max(mh, int(h))
        self.setMinimumSize(mw, mh)
        self.setMaximumSize(w, h)
        self.setGeometry(int(x), int(y), w, h)

    def _apply_mode_geometry(self):
        x, y, w, h = self._pick_mode_geometry()
        self._set_geometry_forced(x, y, w, h)
        self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)

    def _refresh_text(self):
        if self._use_html and (self._last_html or self._last_bot_html):
            self._paint_pair(self._last_html, self._last_bot_html, self._last_text, self._last_next)
        else:
            self._apply_line(self._last_text, highlight=self._last_highlight, next_text=self._last_next)

    def _plain_vertical(self, text: str, color: str) -> str:
        parts = ['<span style="color:%s;">%s</span>' % (color, escape(c)) for c in (text or '') if c not in '\n\r']
        return '<br>'.join(parts) if parts else ''

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
        geo = cfg.get(self._mode_geo_key()) or cfg.get('geometry')
        if isinstance(geo, (list, tuple)) and len(geo) == 4:
            w, h = self._normalize_mode_size(geo[2], geo[3])
            self.setGeometry(int(geo[0]), int(geo[1]), w, h)
            self._restored_geo = True
        else:
            self._restored_geo = False

    def _save_layout(self):
        layout = load_ui_layout()
        g = self.geometry()
        w, h = self._normalize_mode_size(g.width(), g.height())
        if w != g.width() or h != g.height():
            self._set_geometry_forced(g.x(), g.y(), w, h)
            self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
            g = self.geometry()
        geo = [g.x(), g.y(), g.width(), g.height()]
        cfg = dict(layout.get('lyrics_window') or {})
        cfg['orientation'] = self._orientation
        cfg['geometry'] = geo
        cfg[self._mode_geo_key()] = geo
        layout['lyrics_window'] = cfg
        save_ui_layout(layout)
