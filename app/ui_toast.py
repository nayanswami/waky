"""Waky's own notifications: a small dark card that springs in from the corner, instead of a plain Windows balloon."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from . import pill_styles

KINDS = {
    "info": ("#2E62FF", "#7CA2FF"),
    "learned": ("#7C4DFF", "#C2A8FF"),
    "success": ("#1FB85A", "#7BE9A4"),
    "error": ("#E5483D", "#FF9A91"),
    "update": ("#2E62FF", "#7CA2FF"),
}
WIDTH, MARGIN, SHADOW, GAP = 344, 18, 22, 8
SHOW_SECONDS = 6.0


def kind_for(title: str, message: str = "") -> str:
    text = f"{title} {message}".lower()
    if "learned" in text:
        return "learned"
    if "error" in text or "failed" in text or "could not" in text or "unavailable" in text:
        return "error"
    if "update" in text:
        return "update"
    if "copied" in text or "pasted" in text or "done" in text:
        return "success"
    return "info"


class Toast(QWidget):
    def __init__(self, title: str, message: str, kind: str, on_click, manager, seconds: float = SHOW_SECONDS) -> None:
        super().__init__(None)
        self.title, self.message, self.kind = title, message, kind if kind in KINDS else "info"
        self.on_click, self.manager, self.seconds = on_click, manager, seconds
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.title_font = QFont("Segoe UI Variable Display", 10)
        self.title_font.setWeight(QFont.DemiBold)
        self.body_font = QFont("Segoe UI Variable Text", 9)
        self.body_height = self._measure_body()
        self.card_h = 20 + 18 + 4 + self.body_height + 18
        self.card_h = max(self.card_h, 72)
        self.setFixedSize(WIDTH + SHADOW * 2, int(self.card_h) + SHADOW * 2)
        self.anim = 0.0           # 0 hidden .. 1 shown (spring)
        self.vel = 0.0
        self.closing = False
        self.hover = 0.0
        self.hovered = False
        self.born = time.monotonic()
        self.paused_for = 0.0
        self._last = time.monotonic()
        self.slot_y = 0.0         # where this toast wants to sit (stacking), eased toward
        self.cur_y = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)

    def _measure_body(self) -> float:
        fm = QFontMetricsF(self.body_font)
        rect = fm.boundingRect(QRectF(0, 0, WIDTH - 20 - 52 - 18, 1000), Qt.TextWordWrap, self.message)
        return min(rect.height(), fm.lineSpacing() * 4)

    # ---- lifecycle ----
    def present(self, y: float) -> None:
        self.slot_y = y
        self.cur_y = y + 16
        screen = QApplication.primaryScreen().availableGeometry()
        self._x = screen.right() - WIDTH - MARGIN - SHADOW + 1
        self.move(int(self._x), int(self.cur_y))
        self.show()
        self.timer.start(16)

    def dismiss(self) -> None:
        self.closing = True

    def _tick(self) -> None:
        now = time.monotonic()
        dt = max(0.001, min(0.05, now - self._last))
        self._last = now
        if self.hovered:
            self.paused_for += dt
        elapsed = now - self.born - self.paused_for
        if elapsed > self.seconds and not self.closing:
            self.closing = True
        target = 0.0 if self.closing else 1.0
        k, c = (520.0, 2 * math.sqrt(520.0) * 0.72) if not self.closing else (700.0, 2 * math.sqrt(700.0) * 1.0)
        self.vel += (k * (target - self.anim) - c * self.vel) * dt
        self.anim += self.vel * dt
        self.hover += ((1.0 if self.hovered else 0.0) - self.hover) * min(1.0, dt * 12)
        if self.cur_y is not None:
            self.cur_y += (self.slot_y - self.cur_y) * min(1.0, dt * 10)
        shown = max(0.0, min(1.2, self.anim))
        lift = (1 - min(1.0, shown)) * 26
        self.move(int(self._x), int(self.cur_y + lift))
        self.setWindowOpacity(max(0.0, min(1.0, shown * 1.6)))
        if self.closing and self.anim < 0.02 and abs(self.vel) < 0.5:
            self.timer.stop()
            self.manager.remove(self)
            self.close()
            return
        self.update()

    # ---- input ----
    def enterEvent(self, _e) -> None:   # noqa: N802
        self.hovered = True

    def leaveEvent(self, _e) -> None:   # noqa: N802
        self.hovered = False

    def mousePressEvent(self, event) -> None:   # noqa: N802
        if event.button() == Qt.LeftButton:
            if self.on_click is not None:
                try:
                    self.on_click()
                except Exception:
                    pass
            self.dismiss()

    # ---- painting ----
    def paintEvent(self, _e) -> None:   # noqa: N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.TextAntialiasing)
            main, light = (QColor(c) for c in KINDS[self.kind])
            card = QRectF(SHADOW, SHADOW, WIDTH, self.card_h)
            scale = 0.96 + 0.04 * max(0.0, min(1.0, self.anim))
            p.translate(card.center())
            p.scale(scale, scale)
            p.translate(-card.center())
            # soft shadow
            for i in range(9):
                grow = i * 2.2
                shade = QColor(0, 0, 0, int(15 * (1 - i / 9)))
                path = QPainterPath()
                path.addRoundedRect(card.adjusted(-grow, -grow + 6, grow, grow + 6), 20 + grow, 20 + grow)
                p.fillPath(path, shade)
            body = QPainterPath()
            body.addRoundedRect(card, 20, 20)
            grad = QLinearGradient(card.topLeft(), card.bottomRight())
            grad.setColorAt(0, QColor(31, 32, 40, 246))
            grad.setColorAt(1, QColor(16, 17, 22, 248))
            p.fillPath(body, grad)
            glow = QColor(main)
            glow.setAlpha(int(34 + 30 * self.hover))
            wash = QLinearGradient(card.topLeft(), QPointF(card.left() + 160, card.top()))
            wash.setColorAt(0, glow)
            wash.setColorAt(1, QColor(main.red(), main.green(), main.blue(), 0))
            p.save()
            p.setClipPath(body)
            p.fillRect(card, wash)
            p.restore()
            p.setPen(QPen(QColor(255, 255, 255, int(34 + 30 * self.hover)), 1))
            p.setBrush(Qt.NoBrush)
            p.drawPath(body)
            # icon chip
            chip = QRectF(card.left() + 16, card.top() + 16, 38, 38)
            cg = QLinearGradient(chip.topLeft(), chip.bottomRight())
            cg.setColorAt(0, light)
            cg.setColorAt(1, main)
            chip_path = QPainterPath()
            chip_path.addRoundedRect(chip, 12, 12)
            p.fillPath(chip_path, cg)
            self._glyph(p, chip, self.kind)
            # text
            left = chip.right() + 14
            p.setPen(QColor(255, 255, 255, 245))
            p.setFont(self.title_font)
            p.drawText(QRectF(left, card.top() + 14, card.right() - left - 18, 20), Qt.AlignLeft | Qt.AlignVCenter, self.title)
            p.setPen(QColor(205, 208, 220, 215))
            p.setFont(self.body_font)
            p.drawText(QRectF(left, card.top() + 36, card.right() - left - 18, self.body_height + 2), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.message)
            # time bar
            remaining = max(0.0, 1.0 - (time.monotonic() - self.born - self.paused_for) / self.seconds)
            bar = QRectF(card.left() + 18, card.bottom() - 7, (card.width() - 36) * remaining, 2.2)
            bar_color = QColor(light)
            bar_color.setAlpha(150)
            p.setPen(Qt.NoPen)
            p.setBrush(bar_color)
            p.drawRoundedRect(bar, 1.1, 1.1)
        finally:
            if p.isActive():
                p.end()

    @staticmethod
    def _glyph(p: QPainter, chip: QRectF, kind: str) -> None:
        c = chip.center()
        pen = QPen(QColor(255, 255, 255), 2.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if kind == "success":
            path = QPainterPath(QPointF(c.x() - 7, c.y() + 0.5))
            path.lineTo(c.x() - 2, c.y() + 6)
            path.lineTo(c.x() + 8, c.y() - 6)
            p.drawPath(path)
        elif kind == "error":
            p.drawLine(QPointF(c.x(), c.y() - 7), QPointF(c.x(), c.y() + 1.5))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(QPointF(c.x(), c.y() + 7), 1.7, 1.7)
        elif kind == "learned":   # a four-point spark
            star = QPainterPath()
            r, q = 9.5, 2.6
            star.moveTo(c.x(), c.y() - r)
            for ang in (45, 90, 135, 180, 225, 270, 315, 360):
                rad = math.radians(ang - 90)
                rr = q if (ang // 45) % 2 == 1 else r
                star.lineTo(c.x() + rr * math.cos(rad), c.y() + rr * math.sin(rad))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            p.drawPath(star)
        elif kind == "update":
            p.drawLine(QPointF(c.x(), c.y() + 7), QPointF(c.x(), c.y() - 7))
            p.drawLine(QPointF(c.x() - 6, c.y() - 1), QPointF(c.x(), c.y() - 7.5))
            p.drawLine(QPointF(c.x() + 6, c.y() - 1), QPointF(c.x(), c.y() - 7.5))
        else:   # info: Waky's own bars
            for i, h in enumerate((5, 11, 16, 11, 5)):
                p.drawLine(QPointF(c.x() - 8 + i * 4, c.y() - h / 2), QPointF(c.x() - 8 + i * 4, c.y() + h / 2))


class ToastManager:
    """Keeps up to three cards stacked above the taskbar, newest at the bottom."""

    MAX = 3

    def __init__(self) -> None:
        self.toasts: list[Toast] = []

    def show(self, title: str, message: str = "", kind: str | None = None, on_click=None, seconds: float = SHOW_SECONDS) -> None:
        kind = kind or kind_for(title, message)
        for old in list(self.toasts):
            if old.title == title and old.message == message and not old.closing:
                old.born = time.monotonic()
                old.paused_for = 0.0
                return
        toast = Toast(title, message, kind, on_click, self, seconds)
        while len([t for t in self.toasts if not t.closing]) >= self.MAX:
            next(t for t in self.toasts if not t.closing).dismiss()
        self.toasts.append(toast)
        screen = QApplication.primaryScreen().availableGeometry()
        toast.present(screen.bottom() - MARGIN - toast.card_h - SHADOW)
        self.layout()

    def remove(self, toast: Toast) -> None:
        if toast in self.toasts:
            self.toasts.remove(toast)
        self.layout()

    def layout(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        bottom = screen.bottom() - MARGIN          # bottom edge of the newest card
        for toast in reversed([t for t in self.toasts if not t.closing]):
            toast.slot_y = bottom - toast.card_h - SHADOW
            if toast.cur_y is None:
                toast.cur_y = toast.slot_y
            bottom -= toast.card_h + GAP
