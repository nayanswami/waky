"""Building blocks for the setup assistant: two-tone headlines with inline chips, soft cards, a gradient toggle."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

INK = "#111114"
GRAY = "#9C9CA3"


def _icon_family() -> str | None:
    families = QFontDatabase.families()
    return next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)


def tile_pixmap(glyph: str, bg: str, fg: str, size: int = 44, radius: float = 0.28, shadow: bool = True) -> QPixmap:
    """A rounded app tile with a glyph and a soft shadow, like the icon chips in the reference."""
    scale = 2
    pad = 10 if shadow else 0
    total = (size + pad * 2) * scale
    pm = QPixmap(total, total)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    px = size * scale
    off = pad * scale
    if shadow:
        for grow, alpha in ((18, 3), (14, 4), (10, 5), (7, 6), (4, 7), (2, 8)):
            path = QPainterPath()
            path.addRoundedRect(QRectF(off - grow, off - grow + 12, px + grow * 2, px + grow * 2), px * radius + grow, px * radius + grow)
            p.fillPath(path, QColor(0, 0, 0, alpha))
    path = QPainterPath()
    path.addRoundedRect(QRectF(off, off, px, px), px * radius, px * radius)
    grad = QLinearGradient(0, off, 0, off + px)
    base = QColor(bg)
    grad.setColorAt(0, base.lighter(106) if base.lightness() < 200 else base)
    grad.setColorAt(1, base if base.lightness() < 200 else base.darker(103))
    p.fillPath(path, grad)
    family = _icon_family()
    if family and glyph:
        font = QFont(family)
        font.setPixelSize(int(px * 0.5))
        p.setFont(font)
        p.setPen(QColor(fg))
        p.drawText(QRectF(off, off, px, px), Qt.AlignCenter, glyph)
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def tile_label(glyph: str, bg: str = "#FFFFFF", fg: str = INK, size: int = 44, shadow: bool = True) -> QLabel:
    label = QLabel()
    pm = tile_pixmap(glyph, bg, fg, size, shadow=shadow)
    label.setPixmap(pm)
    label.setFixedSize(QSize(int(pm.width() / pm.devicePixelRatio()), int(pm.height() / pm.devicePixelRatio())))
    label.setStyleSheet("background: transparent; border: none;")
    return label


class ToggleChip(QWidget):
    """The gradient switch from the reference. It flips by itself every couple of seconds."""

    def __init__(self, width: int = 70, height: int = 40, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(width + 16, height + 20)
        self._w, self._h = width, height
        self._t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on)
        self._on_state = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flip)
        self._timer.start(2400)

    def _on(self, v) -> None:
        self._t = float(v)
        self.update()

    def _flip(self) -> None:
        if not self.isVisible():
            return
        self._on_state = not self._on_state
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0 if self._on_state else 0.0)
        self._anim.start()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x, y = 8, 6
        for grow, alpha in ((12, 6), (8, 10), (4, 14)):
            path = QPainterPath()
            path.addRoundedRect(QRectF(x - grow / 2, y - grow / 2 + 7, self._w + grow, self._h + grow), (self._h + grow) / 2, (self._h + grow) / 2)
            p.fillPath(path, QColor(70, 90, 255, alpha))
        track = QPainterPath()
        track.addRoundedRect(QRectF(x, y, self._w, self._h), self._h / 2, self._h / 2)
        grad = QLinearGradient(x, 0, x + self._w, 0)
        grad.setColorAt(0, QColor("#4C8DFF"))
        grad.setColorAt(0.55, QColor("#8E7BFF"))
        grad.setColorAt(1, QColor("#FF86C8"))
        p.fillPath(track, grad)
        k = self._h - 8
        t = max(-0.05, min(1.05, self._t))
        kx = x + 4 + (self._w - k - 8) * t
        shadow = QPainterPath()
        shadow.addEllipse(QRectF(kx, y + 5, k, k))
        p.fillPath(shadow, QColor(0, 0, 0, 40))
        knob = QPainterPath()
        knob.addEllipse(QRectF(kx, y + 4, k, k))
        p.fillPath(knob, QColor("#FFFFFF"))


class PillChip(QWidget):
    """A tiny dark capsule with moving bars, standing in for the Waky pill inside a headline."""

    def __init__(self, accent: str = "#2E62FF", parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(92, 56)
        self._accent = accent
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def _tick(self) -> None:
        if self.isVisible():
            self._phase = (self._phase + 0.05) % 1.0
            self.update()

    def paintEvent(self, _e) -> None:
        import math

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(8, 10, 76, 34)
        for grow, alpha in ((12, 6), (8, 10), (4, 14)):
            path = QPainterPath()
            rr = r.adjusted(-grow / 2, -grow / 2 + 7, grow / 2, grow / 2 + 7)
            path.addRoundedRect(rr, rr.height() / 2, rr.height() / 2)
            p.fillPath(path, QColor(0, 0, 0, alpha))
        body = QPainterPath()
        body.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(body, QColor("#0B0B0E"))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._accent))
        for i in range(7):
            wave = (math.sin(self._phase * math.tau * 1.7 - i * 0.6) + 1) / 2
            h = 4 + wave * 15
            p.drawRoundedRect(QRectF(r.x() + 15 + i * 7.6, r.center().y() - h / 2, 3.6, h), 1.8, 1.8)


class Headline(QWidget):
    """Big two-tone headline. Parts are ('g', 'grey words'), ('k', 'black words') or ('c', chip_widget); it wraps like text."""

    def __init__(self, parts: list, size: int = 38, parent=None) -> None:
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._gap = 11
        self._row_gap = 2
        font = QFont(self.font())
        for family in ("Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI"):
            font.setFamily(family)
            if QFont(family).family() == family:
                break
        font.setPixelSize(size)
        font.setWeight(QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, -1.1)
        for kind, value in parts:
            if kind in ("g", "k"):
                for word in str(value).split():
                    label = QLabel(word, self)
                    label.setFont(font)
                    label.setStyleSheet(
                        f"color: {GRAY if kind == 'g' else INK}; background: transparent; font-size: {size}px; font-weight: 600;"
                        " font-family: 'Segoe UI Variable Display', 'Segoe UI Variable', 'Segoe UI';"
                    )
                    label.ensurePolished()
                    label.adjustSize()
                    self._items.append(label)
            else:
                value.setParent(self)
                self._items.append(value)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(sp)

    def _flow(self, width: int, apply: bool) -> int:
        rows: list[list[QWidget]] = [[]]
        x = 0
        for item in self._items:
            w = item.width()
            if x + w > width and rows[-1]:
                rows.append([])
                x = 0
            rows[-1].append(item)
            x += w + self._gap
        y = 0
        for row in rows:
            heights = [i.height() for i in row]
            row_h = max(heights) if heights else 0
            x = 0
            for item, h in zip(row, heights):
                w = item.width()
                if apply:
                    item.setGeometry(int(x), int(y + (row_h - h) / 2), int(w), int(h))
                    item.show()
                x += w + self._gap
            y += row_h + self._row_gap
        return int(y)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return self._flow(w, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(560, self._flow(560, False))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, self._flow(560, False))

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._flow(self.width(), True)
        super().resizeEvent(event)


def soft_shadow(widget: QWidget, blur: int = 36, dy: int = 10, alpha: int = 22) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class Card(QFrame):
    """A soft white card with a very light shadow."""

    def __init__(self, parent=None, shadow: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("wcard")


class PlanCard(Card):
    """A choice card (cloud or local) in the style of the pricing cards: tile, name, meta, a wide button, then a tick list."""

    chosen = Signal()

    def __init__(self, glyph: str, title: str, meta: str, button: str, bullets: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._button_text = button
        self._checked = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(tile_label(glyph, "#18181B", "#FFFFFF", 42, shadow=False), 0, Qt.AlignVCenter)
        name = QLabel(title)
        name.setStyleSheet("font-size:20px;font-weight:600;")
        top.addWidget(name)
        top.addStretch()
        tag = QLabel(meta)
        tag.setStyleSheet(f"font-size:15px;color:{GRAY};")
        top.addWidget(tag)
        lay.addLayout(top)
        self.button = QPushButton(button)
        self.button.setObjectName("choose")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setMinimumHeight(46)
        self.button.clicked.connect(self.chosen.emit)
        lay.addWidget(self.button)
        for text in bullets:
            row = QLabel(f"✓   {text}")
            row.setStyleSheet(f"font-size:13px;color:#5A5A61;")
            row.setWordWrap(True)
            lay.addWidget(row)
        lay.addStretch()
        self.setProperty("selected", False)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, on: bool) -> None:
        self._checked = on
        self.button.setText("Selected  ✓" if on else self._button_text)
        self.setProperty("selected", on)
        for w in (self, self.button):
            w.style().unpolish(w)
            w.style().polish(w)

    def mousePressEvent(self, event) -> None:
        self.chosen.emit()
        super().mousePressEvent(event)


class ProgressLine(QWidget):
    """Thin segmented progress: filled segments are ink, the rest light grey."""

    def __init__(self, count: int = 9, parent=None) -> None:
        super().__init__(parent)
        self.count, self.index = count, 0
        self.setFixedHeight(4)
        self._v = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on)

    def _on(self, v) -> None:
        self._v = float(v)
        self.update()

    def set_progress(self, index: int, count: int) -> None:
        self.count, self.index = count, index
        if not self.isVisible():
            self._v = float(index + 1)
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._v)
        self._anim.setEndValue(float(index + 1))
        self._anim.start()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        gap = 5
        seg = (self.width() - gap * (self.count - 1)) / max(1, self.count)
        for i in range(self.count):
            x = i * (seg + gap)
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, 0, seg, self.height()), 2, 2)
            p.fillPath(path, QColor("#D8D8DC"))
            fill = max(0.0, min(1.0, self._v - i))
            if fill > 0:
                inner = QPainterPath()
                inner.addRoundedRect(QRectF(x, 0, seg * fill, self.height()), 2, 2)
                p.fillPath(inner, QColor(INK))


WIZARD_QSS = f"""
QDialog#wizard {{ background: #EEEEEF; }}
#wizard QLabel {{ color: {INK}; background: transparent; }}
#wizard QLabel#sub {{ color: #7C7C83; font-size: 15px; }}
#wizard QLabel#cap, #wizard QLabel#caption {{ color: #8A8A91; font-size: 12px; }}
#wizard QLabel#tag {{ color: #55555C; font-family: Consolas, "Cascadia Mono", monospace; font-size: 10px; border: 1px solid #C9C9CE; border-radius: 3px; padding: 1px 5px; }}
#wizard QLabel#step {{ color: #8A8A91; font-family: Consolas, "Cascadia Mono", monospace; font-size: 11px; }}
#wizard QLabel#ok {{ color: #1E9E4A; font-weight: 600; }}
#wizard QLabel#bad {{ color: #D33A30; font-weight: 600; }}
#wizard QFrame#wcard, #wizard QFrame#group {{ background: #FFFFFF; border: 2px solid #EDEDF0; border-radius: 22px; }}
#wizard QFrame#wcard[selected="true"] {{ border: 2px solid {INK}; }}
#wizard QFrame#hairline {{ background: #EFEFF1; }}
#wizard QFrame#styleCard {{ background: #FFFFFF; border: 2px solid #EDEDF0; border-radius: 18px; }}
#wizard QFrame#styleCard[selected="true"] {{ border: 2px solid {INK}; background: #FFFFFF; }}
#wizard QFrame#styleCard:hover {{ border-color: #BDBDC4; }}
#wizard QFrame#footer {{ background: transparent; border: none; }}
#wizard QPushButton {{ background: #FAFAFA; color: #26262B; border: 1px solid #E1E1E5; border-radius: 14px; padding: 9px 18px; font-weight: 500; min-height: 22px; }}
#wizard QPushButton:hover {{ background: #F2F2F4; }}
#wizard QPushButton:pressed {{ background: #E9E9EC; }}
#wizard QPushButton:disabled {{ background: #F3F3F4; color: #B0B0B6; border-color: #EAEAEC; }}
#wizard QPushButton#ink {{ background: {INK}; color: #FFFFFF; border: none; border-radius: 17px; padding: 12px 28px; font-weight: 600; font-size: 14px; }}
#wizard QPushButton#ink:hover {{ background: #2B2B31; }}
#wizard QPushButton#ink:disabled {{ background: #D6D6DA; color: #9C9CA3; }}
#wizard QPushButton#plain {{ background: transparent; border: none; color: #6F6F76; padding: 6px 4px; }}
#wizard QPushButton#plain:hover {{ color: {INK}; background: transparent; }}
#wizard QPushButton#link {{ background: transparent; border: none; color: #3C4BFF; padding: 4px; }}
#wizard QPushButton#choose {{ background: #FAFAFA; color: #3A3A40; border: 1px solid #E4E4E8; border-radius: 15px; font-size: 14px; }}
#wizard QFrame#wcard[selected="true"] QPushButton#choose {{ background: {INK}; color: #FFFFFF; border: none; }}
#wizard QPushButton#swatch {{ border: 2px solid #E1E1E5; }}
#wizard QPushButton#swatch:checked {{ border: 2px solid {INK}; }}
#wizard QLineEdit, #wizard QPlainTextEdit {{ background: #FFFFFF; color: {INK}; border: 1px solid #E1E1E5; border-radius: 14px; padding: 10px 14px; selection-background-color: {INK}; }}
#wizard QLineEdit:focus, #wizard QPlainTextEdit:focus {{ border: 1px solid {INK}; }}
#wizard QLineEdit#hotkeyBig {{ font-size: 24px; font-weight: 600; padding: 12px 16px; border-radius: 18px; background: #FFFFFF; }}
#wizard QLineEdit#hotkeyBig:focus {{ border: 2px solid {INK}; }}
#wizard QSlider::groove:horizontal {{ height: 4px; background: #D8D8DC; border-radius: 2px; }}
#wizard QSlider::sub-page:horizontal {{ background: {INK}; border-radius: 2px; }}
#wizard QSlider::handle:horizontal {{ background: #FFFFFF; border: 1px solid #BDBDC4; width: 18px; height: 18px; margin: -8px 0; border-radius: 10px; }}
"""
