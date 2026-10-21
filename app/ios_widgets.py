"""macOS-flavoured widgets: switch, grouped lists, segmented control, key caps, step rail, animated page stack."""
from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import ios_theme, pill_styles


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class IOSSwitch(QCheckBox):
    """Drop-in QCheckBox that paints as a macOS-style toggle with a soft spring."""

    TRACK_W, TRACK_H, KNOB = 38, 22, 18

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._t = 1.0 if self.isChecked() else 0.0
        self._pressed = False
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def _get(self) -> float:
        return self._t

    def _set(self, v: float) -> None:
        self._t = v
        self.update()

    knob = Property(float, _get, _set)

    def _on_toggled(self, on: bool) -> None:
        target = 1.0 if on else 0.0
        if not self.isVisible():
            self._t = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.start()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def _text_rect(self, width: int) -> QRectF:
        return QRectF(0, 0, max(40, width - self.TRACK_W - 14), 10000)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        bound = QFontMetrics(self.font()).boundingRect(self._text_rect(w).toRect(), Qt.TextWordWrap, self.text())
        return max(self.minimumHeight(), bound.height() + 12)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + self.TRACK_W + 24, self.minimumHeight())

    def mousePressEvent(self, e) -> None:
        self._pressed = True
        self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        p.setPen(QColor(pal.text if enabled else pal.text3))
        p.drawText(QRectF(0, 0, self.width() - self.TRACK_W - 14, self.height()), Qt.AlignVCenter | Qt.TextWordWrap, self.text())
        tx = self.width() - self.TRACK_W
        ty = (self.height() - self.TRACK_H) / 2
        off = QColor("#CFCFD6") if not pal.is_dark else QColor("#58585F")
        track_c = mix(off, QColor(pal.accent), min(1.0, max(0.0, self._t)))
        if not enabled:
            track_c.setAlpha(110)
        track = QPainterPath()
        track.addRoundedRect(QRectF(tx, ty, self.TRACK_W, self.TRACK_H), self.TRACK_H / 2, self.TRACK_H / 2)
        p.fillPath(track, track_c)
        kw = self.KNOB + (3 if self._pressed else 0)
        span = self.TRACK_W - 4 - kw
        kx = tx + 2 + span * self._t
        ky = ty + (self.TRACK_H - self.KNOB) / 2
        shadow = QPainterPath()
        shadow.addRoundedRect(QRectF(kx, ky + 1, kw, self.KNOB), self.KNOB / 2, self.KNOB / 2)
        p.fillPath(shadow, QColor(0, 0, 0, 40))
        knob = QPainterPath()
        knob.addRoundedRect(QRectF(kx, ky, kw, self.KNOB), self.KNOB / 2, self.KNOB / 2)
        p.fillPath(knob, QColor("#FFFFFF"))
        if self.hasFocus():
            p.setPen(QPen(QColor(pal.accent), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(tx - 2, ty - 2, self.TRACK_W + 4, self.TRACK_H + 4), (self.TRACK_H + 4) / 2, (self.TRACK_H + 4) / 2)


class PillPreview(QWidget):
    """Animated sample of a pill style on a neutral backdrop."""

    def __init__(self, style_key: str, accent: str = pill_styles.DEFAULT_ACCENT, scale: float = 1.0, status: str = "Listening", parent=None) -> None:
        super().__init__(parent)
        self.style_def = pill_styles.get_style(style_key)
        self.accent = accent
        self.scale = scale
        self.status = status
        self.phase = 0.0
        self.setMinimumSize(120, 58)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_look(self, style_key: str | None = None, accent: str | None = None, scale: float | None = None) -> None:
        if style_key:
            self.style_def = pill_styles.get_style(style_key)
        if accent:
            self.accent = accent
        if scale:
            self.scale = scale
        self.update()

    def _tick(self) -> None:
        if self.isVisible():
            self.phase = (self.phase + 0.045) % 1.0
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            area = QRectF(self.rect())
            path = QPainterPath()
            path.addRoundedRect(area, 9, 9)
            p.fillPath(path, QColor("#1B1C22"))
            inner = QRectF(area.x(), area.y(), area.width(), area.height())
            pill_styles.paint(p, inner, self.style_def, self.status, self.phase, 99.0,
                              bottom_margin=(area.height() - 26 * self.scale) / 2 / max(self.scale, 0.1), scale=self.scale, accent=self.accent)
        finally:
            if p.isActive():
                p.end()


class StyleCard(QFrame):
    clicked = Signal(str)

    def __init__(self, style: pill_styles.PillStyle, accent: str, parent=None) -> None:
        super().__init__(parent)
        self.key = style.key
        self.setObjectName("styleCard")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        self.preview = PillPreview(style.key, accent)
        title = QLabel(style.label)
        title.setStyleSheet("font-weight:600;font-size:13px;")
        blurb = QLabel(style.blurb)
        blurb.setObjectName("caption")
        lay.addWidget(self.preview)
        lay.addWidget(title)
        lay.addWidget(blurb)
        self.setProperty("selected", False)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e) -> None:
        self.clicked.emit(self.key)
        super().mousePressEvent(e)


class StepDots(QWidget):
    """Page indicator whose active dot stretches into a pill and glides between steps."""

    def __init__(self, count: int, parent=None) -> None:
        super().__init__(parent)
        self.count = count
        self._v = 0.0
        self.setFixedHeight(14)
        self.setMinimumWidth(count * 14 + 30)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.OutBack)

    def _get(self) -> float:
        return self._v

    def _set(self, v: float) -> None:
        self._v = v
        self.update()

    value = Property(float, _get, _set)

    def go(self, index: float, animate: bool = True) -> None:
        if not animate or not self.isVisible():
            self._v = float(index)
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._v)
        self._anim.setEndValue(float(index))
        self._anim.start()

    def set_count(self, n: int) -> None:
        self.count = n
        self.update()

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        widths = []
        for i in range(self.count):
            w = max(0.0, 1.0 - abs(self._v - i))
            widths.append(8 + 18 * min(1.0, w))
        total = sum(widths) + 8 * (self.count - 1)
        x = (self.width() - total) / 2
        for i, w in enumerate(widths):
            weight = max(0.0, min(1.0, 1.0 - abs(self._v - i)))
            c = mix(QColor(pal.sep), QColor(pal.accent), weight)
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, (self.height() - 8) / 2, w, 8), 4, 4)
            p.fillPath(path, c)
            x += w + 8


class AnimatedStack(QStackedWidget):
    """QStackedWidget that cross-fades and slides the incoming page (OutCubic, ~320 ms)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._group: QParallelAnimationGroup | None = None

    def go(self, index: int, direction: int = 1, animate: bool = True) -> None:
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        page = self.currentWidget()
        if not animate or page is None or not self.isVisible():
            return
        if self._group is not None:
            self._group.stop()
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", page)
        fade.setDuration(300)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        def start() -> None:
            end = page.pos()
            slide = QPropertyAnimation(page, b"pos", page)
            slide.setDuration(380)
            slide.setStartValue(end + QPoint(36 * direction, 0))
            slide.setEndValue(end)
            slide.setEasingCurve(QEasingCurve.OutCubic)
            group = QParallelAnimationGroup(page)
            group.addAnimation(fade)
            group.addAnimation(slide)
            group.finished.connect(lambda: page.setGraphicsEffect(None))
            self._group = group
            group.start()

        QTimer.singleShot(0, start)


def fade_in(widget: QWidget, duration: int = 280, delay: int = 0) -> None:
    """Fade a widget in once (used for window entrances)."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    QTimer.singleShot(delay, anim.start)
    widget._fade_anim = anim  # keep a reference


class PageStack(AnimatedStack):
    """Settings pages: a title, a subtitle, then the page content (groups) in a centred column inside a scroll area."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.titles: list[str] = []
        self.describe = None

    def addTab(self, widget: QWidget, title: str, subtitle: str | None = None) -> int:  # noqa: N802 (QTabWidget-compatible name)
        from PySide6.QtWidgets import QHBoxLayout, QScrollArea

        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        column = QWidget()
        column.setMaximumWidth(720)
        v = QVBoxLayout(column)
        v.setContentsMargins(30, 26, 30, 30)
        v.setSpacing(0)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        sub = QLabel(subtitle if subtitle is not None else (self.describe(title) if self.describe else ""))
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        v.addWidget(heading)
        v.addSpacing(2)
        v.addWidget(sub)
        v.addSpacing(18)
        v.addWidget(widget)
        v.addStretch()
        outer.addStretch(1)
        outer.addWidget(column, 100)
        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        scroll.viewport().setAutoFillBackground(False)
        self.addWidget(scroll)
        self.titles.append(title)
        return self.count() - 1

    def index_of(self, title: str) -> int:
        return self.titles.index(title) if title in self.titles else 0


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("section")
    label.setContentsMargins(4, 0, 0, 0)
    return label


def glyph_pixmap(glyph: str, color: str, size: int = 22, radius: float = 0.27, glyph_color: str = "#FFFFFF") -> QPixmap:
    """A macOS-style app tile: coloured rounded square with a white Segoe Fluent glyph."""
    scale = 2
    px = size * scale
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), px * radius, px * radius)
    grad = QLinearGradient(0, 0, 0, px)
    base = QColor(color)
    grad.setColorAt(0, base.lighter(112))
    grad.setColorAt(1, base)
    p.fillPath(path, grad)
    families = QFontDatabase.families()
    family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)
    if family and glyph:
        font = QFont(family)
        font.setPixelSize(int(px * 0.56))
        p.setFont(font)
        p.setPen(QColor(glyph_color))
        p.drawText(QRectF(0, 0, px, px), Qt.AlignCenter, glyph)
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


class Group(QFrame):
    """macOS 'inset grouped' list: a rounded card whose rows are separated by hairlines.

    addRow() mirrors QFormLayout, so a page can be built the same way it always was:
      addRow(widget)              a switch, button, label or any widget on its own row
      addRow("Label", widget)     label on the left, control on the right (long editors are stacked underneath)
      addRow(widget_a, widget_b)  a wrapping row of buttons
    """

    STACKED = ("QPlainTextEdit", "QTextEdit", "QListWidget", "QTableWidget")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("group")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._rows: list[QWidget] = []

    def rowCount(self) -> int:  # noqa: N802
        return len(self._rows)

    def _append(self, row: QWidget, inset: bool = True) -> QWidget:
        if self._rows:
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(14 if inset else 0, 0, 0, 0)
            hair = QFrame()
            hair.setObjectName("hairline")
            hair.setFixedHeight(1)
            hl.addWidget(hair)
            holder.setFixedHeight(1)
            self._lay.addWidget(holder)
            row._hairline = holder
        self._lay.addWidget(row)
        self._rows.append(row)
        return row

    @staticmethod
    def _is(widget, names) -> bool:
        return any(c.__name__ in names for c in type(widget).__mro__)

    def addRow(self, a, b=None, hint: str = "", stacked: bool | None = None) -> QWidget:  # noqa: N802
        if isinstance(a, QLayout) and b is None:
            row = QWidget()
            a.setContentsMargins(14, 8, 14, 8)
            row.setLayout(a)
            return self._append(row)
        if b is None:
            return self._single(a, hint)
        if isinstance(a, str):
            return self._labelled(a, b, hint, stacked)
        row = QWidget()
        flow = FlowLayout(row, spacing=8)
        flow.setContentsMargins(14, 8, 14, 8)
        flow.addWidget(a)
        flow.addWidget(b)
        return self._append(row)

    def addWidgetRow(self, widget: QWidget, margins=(14, 8, 14, 8)) -> QWidget:  # noqa: N802
        row = QWidget()
        lay = QVBoxLayout(row)
        lay.setContentsMargins(*margins)
        lay.addWidget(widget)
        return self._append(row)

    def _single(self, widget, hint: str) -> QWidget:
        row = QWidget()
        lay = QVBoxLayout(row)
        lay.setSpacing(0)
        if isinstance(widget, QCheckBox):
            lay.setContentsMargins(14, 2, 14, 2)
            lay.addWidget(widget)
            if hint:
                note = QLabel(hint)
                note.setObjectName("caption")
                note.setWordWrap(True)
                note.setContentsMargins(0, 0, 54, 6)
                lay.addWidget(note)
        elif isinstance(widget, QLabel):
            lay.setContentsMargins(14, 9, 14, 9)
            if widget.objectName() in ("", "sub"):
                widget.setObjectName("caption")
            widget.setWordWrap(True)
            lay.addWidget(widget)
        elif isinstance(widget, QPushButton):
            lay.setContentsMargins(14, 8, 14, 8)
            lay.addWidget(widget, 0, Qt.AlignLeft)
        else:
            lay.setContentsMargins(14, 8, 14, 8)
            lay.addWidget(widget)
        return self._append(row)

    def _labelled(self, text: str, control: QWidget, hint: str, stacked: bool | None) -> QWidget:
        row = QWidget()
        if stacked is None:
            stacked = self._is(control, self.STACKED)
        label = QLabel(text)
        label.setObjectName("rowLabel")
        label.setWordWrap(True)
        note = None
        if hint:
            note = QLabel(hint)
            note.setObjectName("caption")
            note.setWordWrap(True)
        if stacked:
            lay = QVBoxLayout(row)
            lay.setContentsMargins(14, 10, 14, 12)
            lay.setSpacing(6)
            lay.addWidget(label)
            if note:
                lay.addWidget(note)
            lay.addWidget(control)
            return self._append(row)
        if note and isinstance(control, Segmented):   # wide control: the explanation goes underneath, full width
            outer = QVBoxLayout(row)
            outer.setContentsMargins(14, 7, 14, 9)
            outer.setSpacing(5)
            top = QHBoxLayout()
            top.addWidget(label, 1)
            top.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
            outer.addLayout(top)
            outer.addWidget(note)
            return self._append(row)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 7, 14, 7)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(1)
        left.addWidget(label)
        if note:
            left.addWidget(note)
        lay.addLayout(left, 1)
        free = control.minimumWidth() == 0 and control.maximumWidth() >= 16777215
        if free and self._is(control, ("QLineEdit", "QComboBox")):
            control.setFixedWidth(260)
        elif free and self._is(control, ("QSpinBox", "QDoubleSpinBox")):
            control.setFixedWidth(110)
        lay.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        row.setMinimumHeight(40)
        return self._append(row)

    def set_row_visible(self, row: QWidget, visible: bool) -> None:
        row.setVisible(visible)
        hair = getattr(row, "_hairline", None)
        if hair is not None:
            hair.setVisible(visible)


class Segmented(QWidget):
    """macOS segmented control: a pill-shaped track with a sliding thumb behind the selected option."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.options = options
        self._index = 0
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"thumb", self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        fm = QFontMetrics(self.font())
        self._seg_w = max(fm.horizontalAdvance(label) for _k, label in options) + 28
        self.setMinimumWidth(self._seg_w * len(options) + 4)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        if value is not None:
            self.set_value(value, animate=False)

    def sizeHint(self) -> QSize:
        return QSize(self._seg_w * len(self.options) + 4, 28)

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    thumb = Property(float, _get, _set)

    def value(self) -> str:
        return self.options[self._index][0]

    def set_value(self, key: str, animate: bool = True, emit: bool = False) -> None:
        keys = [k for k, _ in self.options]
        if key not in keys:
            return
        index = keys.index(key)
        changed = index != self._index
        self._index = index
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(float(index))
            self._anim.start()
        else:
            self._pos = float(index)
            self.update()
        if emit and changed:
            self.changed.emit(key)

    def _segment_width(self) -> float:
        return (self.width() - 4) / max(1, len(self.options))

    def mousePressEvent(self, e) -> None:
        index = int((e.position().x() - 2) // max(1.0, self._segment_width()))
        index = max(0, min(len(self.options) - 1, index))
        self.set_value(self.options[index][0], emit=True)

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QPainterPath()
        track.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8, 8)
        p.fillPath(track, QColor(pal.surface2))
        p.setPen(QPen(QColor(pal.sep), 1))
        p.drawPath(track)
        seg = self._segment_width()
        thumb = QRectF(2 + seg * self._pos, 2, seg, self.height() - 4)
        shadow = QPainterPath()
        shadow.addRoundedRect(thumb.adjusted(0, 1, 0, 1), 6.5, 6.5)
        p.fillPath(shadow, QColor(0, 0, 0, 28))
        body = QPainterPath()
        body.addRoundedRect(thumb, 6.5, 6.5)
        p.fillPath(body, QColor("#FFFFFF") if not pal.is_dark else QColor("#5B5B62"))
        font = self.font()
        for i, (_k, label) in enumerate(self.options):
            active = max(0.0, 1.0 - abs(self._pos - i))
            font.setWeight(QFont.DemiBold if active > 0.5 else QFont.Normal)
            p.setFont(font)
            colour = mix(QColor(pal.text2), QColor("#1D1D1F") if not pal.is_dark else QColor("#FFFFFF"), active)
            p.setPen(colour)
            p.drawText(QRectF(2 + seg * i, 0, seg, self.height()), Qt.AlignCenter, label)


class KeyCaps(QWidget):
    """Drawn keyboard keys. The keys dip gently as if held, then release, to show 'press and hold'."""

    def __init__(self, keys: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.keys = keys or ["Ctrl", "Win"]
        self._phase = 0.0
        self.setMinimumHeight(86)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_keys(self, keys: list[str]) -> None:
        self.keys = keys or ["?"]
        self.update()

    def _tick(self) -> None:
        if self.isVisible():
            self._phase = (self._phase + 0.012) % 1.0
            self.update()

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(18)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        fm = QFontMetrics(font)
        widths = [max(64, fm.horizontalAdvance(k) + 38) for k in self.keys]
        gap = 14
        total = sum(widths) + gap * (len(widths) - 1)
        x = (self.width() - total) / 2
        h = 58
        top = (self.height() - h) / 2 - 3
        # held for the middle of the cycle, released at the ends
        t = self._phase
        down = 1.0 if 0.18 < t < 0.7 else (max(0.0, (t - 0.05) / 0.13) if t <= 0.18 else max(0.0, 1.0 - (t - 0.7) / 0.12))
        for key, w in zip(self.keys, widths):
            dip = 3.0 * down
            base = QPainterPath()
            base.addRoundedRect(QRectF(x, top + 4, w, h), 12, 12)
            p.fillPath(base, QColor(pal.border))
            face = QRectF(x, top + dip, w, h)
            path = QPainterPath()
            path.addRoundedRect(face, 12, 12)
            p.fillPath(path, mix(QColor(pal.surface), QColor("#EAF0FF" if not pal.is_dark else "#26304F"), down))
            p.setPen(QPen(mix(QColor(pal.border), QColor(pal.accent), down), 1.2))
            p.drawPath(path)
            p.setPen(mix(QColor(pal.text), QColor(pal.accent), down))
            p.drawText(face, Qt.AlignCenter, key)
            x += w + gap


class StepRail(QWidget):
    """Vertical progress list for the setup assistant: done steps get a tick, the current one an accent ring."""

    ROW = 34

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        self.labels = labels
        self.current = 0
        self.done: set[int] = set()
        self.setMinimumHeight(self.ROW * len(labels))
        self.setMinimumWidth(150)

    def set_state(self, labels: list[str], current: int) -> None:
        self.labels = labels
        self.current = current
        self.done = set(range(current))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(170, self.ROW * len(self.labels))

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        for i, label in enumerate(self.labels):
            cy = i * self.ROW + self.ROW / 2
            cx = 11
            if i < len(self.labels) - 1:
                p.setPen(QPen(QColor(pal.accent if i in self.done else pal.border), 1.5))
                p.drawLine(cx, int(cy + 9), cx, int(cy + self.ROW - 9))
            if i in self.done:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(pal.accent))
                p.drawEllipse(QPointF(cx, cy), 8, 8)
                pen = QPen(QColor("#FFFFFF"), 1.8)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                p.setPen(pen)
                p.drawPolyline([QPointF(cx - 3.2, cy + 0.2), QPointF(cx - 0.8, cy + 2.6), QPointF(cx + 3.4, cy - 2.4)])
            elif i == self.current:
                p.setPen(QPen(QColor(pal.accent), 2))
                p.setBrush(QColor(pal.surface))
                p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(pal.accent))
                p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
            else:
                p.setPen(QPen(QColor(pal.border), 1.5))
                p.setBrush(QColor(pal.surface))
                p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
            font.setWeight(QFont.DemiBold if i == self.current else QFont.Normal)
            p.setFont(font)
            p.setPen(QColor(pal.text if i == self.current else (pal.text2 if i in self.done else pal.text3)))
            p.drawText(QRectF(30, i * self.ROW, self.width() - 30, self.ROW), Qt.AlignVCenter | Qt.AlignLeft, label)


class FlowLayout(QLayout):
    """Lays widgets out left to right and wraps to a new row when the width runs out (keeps button rows from overflowing)."""

    def __init__(self, parent=None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, apply: bool) -> int:
        m = self.contentsMargins()
        x, y = rect.x() + m.left(), rect.y() + m.top()
        right = rect.right() - m.right()
        row_h = 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > right and row_h > 0:
                x = rect.x() + m.left()
                y += row_h + self._spacing
                row_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            row_h = max(row_h, hint.height())
        return y + row_h - rect.y() + m.bottom()
