"""iOS-flavoured widgets with spring-like motion: switch, step dots, style cards, animated page stack."""
from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QCheckBox, QFrame, QGraphicsOpacityEffect, QLabel, QLayout, QStackedWidget, QVBoxLayout, QWidget

from . import ios_theme, pill_styles


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class IOSSwitch(QCheckBox):
    """Drop-in QCheckBox that paints as an iOS toggle with a springy knob."""

    TRACK_W, TRACK_H, KNOB = 52, 31, 27

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._t = 1.0 if self.isChecked() else 0.0
        self._pressed = False
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self.toggled.connect(self._on_toggled)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(38)
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
        return QRectF(0, 0, max(40, width - self.TRACK_W - 16), 10000)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        bound = QFontMetrics(self.font()).boundingRect(self._text_rect(w).toRect(), Qt.TextWordWrap, self.text())
        return max(self.minimumHeight(), bound.height() + 14)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + self.TRACK_W + 28, self.minimumHeight())

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
        # label
        p.setPen(QColor(pal.text if enabled else pal.text3))
        p.drawText(QRectF(0, 0, self.width() - self.TRACK_W - 16, self.height()), Qt.AlignVCenter | Qt.TextWordWrap, self.text())
        # track
        tx = self.width() - self.TRACK_W - 2
        ty = (self.height() - self.TRACK_H) / 2
        off = QColor("#787880") if not pal.is_dark else QColor("#4A4C57")
        off.setAlpha(150 if not pal.is_dark else 255)
        on = QColor(pal.accent)
        track_c = mix(off, on, min(1.0, max(0.0, self._t)))
        if not enabled:
            track_c.setAlpha(100)
        track = QPainterPath()
        track.addRoundedRect(QRectF(tx, ty, self.TRACK_W, self.TRACK_H), self.TRACK_H / 2, self.TRACK_H / 2)
        p.fillPath(track, track_c)
        # knob (widens a little while pressed, like iOS)
        kw = self.KNOB + (5 if self._pressed else 0)
        span = self.TRACK_W - 4 - kw
        kx = tx + 2 + max(-3, min(span + 3, span * self._t))
        ky = ty + (self.TRACK_H - self.KNOB) / 2
        shadow = QPainterPath()
        shadow.addRoundedRect(QRectF(kx, ky + 1.5, kw, self.KNOB), self.KNOB / 2, self.KNOB / 2)
        p.fillPath(shadow, QColor(0, 0, 0, 45))
        knob = QPainterPath()
        knob.addRoundedRect(QRectF(kx, ky, kw, self.KNOB), self.KNOB / 2, self.KNOB / 2)
        p.fillPath(knob, QColor("#FFFFFF"))
        if self.hasFocus():
            p.setPen(QPen(QColor(pal.accent), 2))
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
            path.addRoundedRect(area, 12, 12)
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
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.preview = PillPreview(style.key, accent)
        title = QLabel(style.label)
        title.setStyleSheet("font-weight:600;")
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
    """Settings pages: each added widget is wrapped in a title, subtitle and an inset card, inside a scroll area."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.titles: list[str] = []
        self.describe = None

    def addTab(self, widget: QWidget, title: str, subtitle: str | None = None) -> int:  # noqa: N802 (QTabWidget-compatible name)
        from PySide6.QtWidgets import QScrollArea

        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(34, 30, 34, 30)
        v.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        sub = QLabel(subtitle if subtitle is not None else (self.describe(title) if self.describe else ""))
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.addWidget(widget)
        v.addWidget(heading)
        v.addWidget(sub)
        v.addSpacing(14)
        v.addWidget(card)
        v.addStretch()
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
