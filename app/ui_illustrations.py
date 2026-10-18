"""Original line-art illustrations for the onboarding flow, drawn and animated with QPainter."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import ios_theme, pill_styles
from .utils import asset_path


def smooth(a: float, b: float, t: float) -> float:
    x = max(0.0, min(1.0, (t - a) / (b - a) if b != a else 1.0))
    return x * x * (3 - 2 * x)


class Illustration(QWidget):
    """One widget, several scenes. `set_kind` crossfades between them; everything loops on a 4 second phase."""

    HEIGHTS = {"welcome": 340, "engine": 250, "key": 230, "hotkey": 300, "pill": 200, "try": 200, "done": 300}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.kind = "welcome"
        self._prev: str | None = None
        self._fade = 1.0
        self.phase = 0.0
        self.engine = "cloud"
        self.keys = ["Ctrl", "Win"]
        self.pill_style = "island"
        self.accent = pill_styles.DEFAULT_ACCENT
        self.pill_scale = 1.0
        self._icon = QPixmap(str(asset_path("waky-icon.png")))
        self.setFixedHeight(self.HEIGHTS["welcome"])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self._h_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._h_anim.setDuration(420)
        self._h_anim.setEasingCurve(QEasingCurve.OutCubic)

    # ---------- control ----------
    def set_kind(self, kind: str, animate: bool = True) -> None:
        if kind == self.kind:
            return
        self._prev, self.kind, self._fade = self.kind, kind, 0.0 if animate else 1.0
        target = self.HEIGHTS.get(kind, 190)
        if animate and self.isVisible():
            self.setMinimumHeight(0)
            self._h_anim.stop()
            self._h_anim.setStartValue(self.height())
            self._h_anim.setEndValue(target)
            self._h_anim.finished.connect(lambda: self.setFixedHeight(target))
            self._h_anim.start()
        else:
            self.setFixedHeight(target)

    def configure(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)
        self.update()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        self.phase = (self.phase + 0.016 / 4.0) % 1.0
        if self._fade < 1.0:
            self._fade = min(1.0, self._fade + 0.07)
        self.update()

    # ---------- painting ----------
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            area = QRectF(self.rect())
            # soft tinted stage behind the scene
            pal = ios_theme.current()
            stage = QPainterPath()
            stage.addRoundedRect(area.adjusted(0, 0, 0, -2), 22, 22)
            tint = QColor(pal.accent)
            tint.setAlpha(26 if pal.is_dark else 20)
            p.fillPath(stage, tint)
            if self._prev and self._fade < 1.0:
                p.setOpacity(1.0 - self._fade)
                self._scene(p, self._prev, area)
                p.setOpacity(self._fade)
            else:
                p.setOpacity(1.0)
            self._scene(p, self.kind, area)
        finally:
            if p.isActive():
                p.end()

    def _scene(self, p: QPainter, kind: str, area: QRectF) -> None:
        getattr(self, f"_draw_{kind}", self._draw_welcome)(p, area)

    # ---------- helpers ----------
    def _ink(self, alpha: int = 255) -> QColor:
        c = QColor(ios_theme.current().text)
        c.setAlpha(alpha)
        return c

    def _pen(self, width: float = 2.6, color: QColor | None = None) -> QPen:
        pen = QPen(color or self._ink(), width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _accent(self, alpha: int = 255) -> QColor:
        c = QColor(ios_theme.current().accent)
        c.setAlpha(alpha)
        return c

    def _surface(self) -> QColor:
        return QColor(ios_theme.current().surface)

    # ---------- scenes ----------
    def _draw_welcome(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        for i in range(3):
            q = (self.phase + i / 3) % 1.0
            ring = self._accent(int((1 - q) * 110))
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.NoBrush)
            r = 58 + q * 74
            p.drawEllipse(QPointF(cx, cy), r, r)
        bob = math.sin(self.phase * math.tau) * 4
        size = 96
        if not self._icon.isNull():
            p.drawPixmap(QRectF(cx - size / 2, cy - size / 2 + bob, size, size).toRect(), self._icon)
        # little floating "words"
        for dx, dy, w, ph in ((-150, -52, 62, 0.0), (140, -30, 74, 0.33), (-120, 56, 52, 0.66), (120, 62, 58, 0.5)):
            off = math.sin((self.phase + ph) * math.tau) * 5
            r = QRectF(cx + dx - w / 2, cy + dy + off, w, 24)
            path = QPainterPath()
            path.addRoundedRect(r, 12, 12)
            p.fillPath(path, self._surface())
            p.setPen(self._pen(1.6, self._ink(90)))
            p.drawPath(path)
            p.setPen(self._pen(2.4, self._accent(200)))
            p.drawLine(QPointF(r.left() + 12, r.center().y()), QPointF(r.right() - 12, r.center().y()))

    def _cloud_path(self, cx: float, cy: float, s: float) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QPointF(cx - 18 * s, cy + 4 * s), 17 * s, 17 * s)
        path.addEllipse(QPointF(cx + 2 * s, cy - 8 * s), 22 * s, 22 * s)
        path.addEllipse(QPointF(cx + 24 * s, cy + 4 * s), 17 * s, 17 * s)
        path.addRoundedRect(QRectF(cx - 34 * s, cy + 2 * s, 76 * s, 19 * s), 9 * s, 9 * s)
        return path.simplified()

    def _draw_engine(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        lx, rx = cx - 112, cx + 112
        cloud_on = self.engine == "cloud"
        # connector
        pen = self._pen(2.2, self._ink(110))
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([2, 5])
        pen.setDashOffset(-self.phase * 28)
        p.setPen(pen)
        p.drawLine(QPointF(lx + 54, cy), QPointF(rx - 46, cy))
        dot = (self.phase * 1.4) % 1.0
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent())
        p.drawEllipse(QPointF(lx + 54 + (rx - 46 - lx - 54) * dot, cy), 5, 5)
        # cloud
        cloud = self._cloud_path(lx, cy, 1.25)
        p.setBrush(Qt.NoBrush)
        if cloud_on:
            p.fillPath(cloud, self._accent(70))
        p.setPen(self._pen(2.8, self._accent() if cloud_on else self._ink(150)))
        p.drawPath(cloud)
        # chip
        chip = QRectF(rx - 34, cy - 34, 68, 68)
        path = QPainterPath()
        path.addRoundedRect(chip, 14, 14)
        if not cloud_on:
            p.fillPath(path, self._accent(70))
        col = self._accent() if not cloud_on else self._ink(150)
        p.setPen(self._pen(2.8, col))
        p.drawPath(path)
        for i in range(3):
            o = -16 + i * 16
            p.drawLine(QPointF(chip.left() - 9, cy + o), QPointF(chip.left(), cy + o))
            p.drawLine(QPointF(chip.right(), cy + o), QPointF(chip.right() + 9, cy + o))
            p.drawLine(QPointF(cx + 112 + o, chip.top() - 9), QPointF(cx + 112 + o, chip.top()))
            p.drawLine(QPointF(cx + 112 + o, chip.bottom()), QPointF(cx + 112 + o, chip.bottom() + 9))
        inner = chip.adjusted(18, 18, -18, -18)
        p.drawRoundedRect(inner, 5, 5)

    def _draw_key(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        slide = smooth(0.05, 0.5, t) * (1 - smooth(0.85, 1.0, t))
        # lock
        lx = cx + 70
        body = QRectF(lx - 34, cy - 4, 68, 56)
        shackle_lift = smooth(0.5, 0.7, t) * (1 - smooth(0.85, 1.0, t)) * 12
        sh = QPainterPath()
        sh.moveTo(lx - 18, cy - 4)
        sh.lineTo(lx - 18, cy - 20 - shackle_lift)
        sh.arcTo(QRectF(lx - 18, cy - 38 - shackle_lift, 36, 36), 180, -180)
        sh.lineTo(lx + 18, cy - 4)
        p.setPen(self._pen(2.8))
        p.setBrush(Qt.NoBrush)
        p.drawPath(sh)
        bp = QPainterPath()
        bp.addRoundedRect(body, 14, 14)
        p.fillPath(bp, self._surface())
        p.setPen(self._pen(2.8))
        p.drawPath(bp)
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent())
        p.drawEllipse(QPointF(lx, cy + 20), 6, 6)
        p.drawRoundedRect(QRectF(lx - 2.5, cy + 22, 5, 14), 2.5, 2.5)
        # key
        kx = cx - 120 + slide * 62
        p.setBrush(Qt.NoBrush)
        p.setPen(self._pen(2.8, self._accent()))
        p.drawEllipse(QPointF(kx, cy + 20), 17, 17)
        p.drawEllipse(QPointF(kx - 4, cy + 20), 4, 4)
        p.drawLine(QPointF(kx + 17, cy + 20), QPointF(kx + 82, cy + 20))
        p.drawLine(QPointF(kx + 62, cy + 20), QPointF(kx + 62, cy + 31))
        p.drawLine(QPointF(kx + 74, cy + 20), QPointF(kx + 74, cy + 28))

    def _draw_hotkey(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        font = QFont("Segoe UI", 12)
        font.setBold(True)
        p.setFont(font)
        fm = QFontMetrics(font)
        widths = [max(66.0, fm.horizontalAdvance(k) + 34.0) for k in self.keys]
        gap = 14.0
        total = sum(widths) + gap * (len(widths) - 1)
        x = cx - total / 2
        press = smooth(0.2, 0.4, self.phase) * (1 - smooth(0.72, 0.9, self.phase))
        # sound bars above while pressed
        for i in range(9):
            h = (6 + 26 * abs(math.sin(self.phase * math.tau * 3 + i * 0.7))) * press
            bx = cx - 40 + i * 10
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent(int(70 + 185 * press)))
            p.drawRoundedRect(QRectF(bx, cy - 52 - h / 2, 5, max(3, h)), 2.5, 2.5)
        for label, w in zip(self.keys, widths):
            dy = 6 * press
            edge = QRectF(x, cy - 24 + 8, w, 52)
            ep = QPainterPath()
            ep.addRoundedRect(edge, 14, 14)
            p.fillPath(ep, self._ink(40))
            top = QRectF(x, cy - 24 + dy, w, 52 - 6 + (6 - dy) * 0)
            tp = QPainterPath()
            tp.addRoundedRect(top, 14, 14)
            p.fillPath(tp, self._accent(55) if press > 0.5 else self._surface())
            p.setPen(self._pen(2.6, self._accent() if press > 0.5 else self._ink()))
            p.drawPath(tp)
            p.setPen(self._ink())
            p.drawText(top, Qt.AlignCenter, label)
            x += w + gap

    def _draw_pill(self, p: QPainter, a: QRectF) -> None:
        t = self.phase
        if t < 0.18:
            status = "Idle"
        elif t < 0.55:
            status = "Listening"
        elif t < 0.75:
            status = "Processing"
        elif t < 0.93:
            status = "Pasted"
        else:
            status = "Idle"
        expand = smooth(0.12, 0.25, t) * (1 - smooth(0.9, 0.98, t))
        style = pill_styles.get_style(self.pill_style)
        stage = QRectF(a.x(), a.y(), a.width(), a.height())
        pill_styles.paint(
            p, stage, style, status, self.phase * 6.0 % 1.0, 99.0, bottom_margin=(a.height() - 28 * self.pill_scale * 2.0) / 2 / (self.pill_scale * 2.0),
            scale=2.0 * self.pill_scale, accent=self.accent, expand=expand,
        )

    def _draw_try(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        # microphone
        mx = cx - 100
        cap = QRectF(mx - 17, cy - 46, 34, 62)
        path = QPainterPath()
        path.addRoundedRect(cap, 17, 17)
        listening = 0.1 < t < 0.8
        if listening:
            p.fillPath(path, self._accent(70))
        p.setPen(self._pen(2.8, self._accent() if listening else self._ink()))
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        arc = QPainterPath()
        arc.arcMoveTo(QRectF(mx - 30, cy - 34, 60, 62), 200)
        arc.arcTo(QRectF(mx - 30, cy - 34, 60, 62), 200, 140)
        p.drawPath(arc)
        p.drawLine(QPointF(mx, cy + 28), QPointF(mx, cy + 44))
        p.drawLine(QPointF(mx - 14, cy + 44), QPointF(mx + 14, cy + 44))
        # text appearing
        for i, w in enumerate((130, 100, 74)):
            prog = smooth(0.25 + i * 0.16, 0.45 + i * 0.16, t) * (1 - smooth(0.92, 1.0, t))
            y = cy - 30 + i * 30
            p.setPen(self._pen(6, self._ink(60)))
            p.drawLine(QPointF(cx - 40, y), QPointF(cx - 40 + w, y))
            p.setPen(self._pen(6, self._accent() if i == 0 else self._ink(190)))
            p.drawLine(QPointF(cx - 40, y), QPointF(cx - 40 + w * prog, y))

    def _draw_done(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        for i in range(2):
            q = (t + i / 2) % 1.0
            p.setPen(QPen(self._accent(int((1 - q) * 90)), 2))
            p.setBrush(Qt.NoBrush)
            r = 52 + q * 70
            p.drawEllipse(QPointF(cx, cy), r, r)
        sweep = smooth(0.0, 0.35, min(t * 3.0, 1.0)) if t < 0.34 else 1.0
        p.setPen(self._pen(4, self._accent()))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - 46, cy - 46, 92, 92), 90 * 16, int(-360 * 16 * sweep))
        pts = [QPointF(cx - 20, cy + 2), QPointF(cx - 6, cy + 17), QPointF(cx + 22, cy - 14)]
        prog = smooth(0.08, 0.3, t) if t < 0.5 else 1.0
        if prog > 0:
            seg1, seg2 = math.dist((pts[0].x(), pts[0].y()), (pts[1].x(), pts[1].y())), math.dist((pts[1].x(), pts[1].y()), (pts[2].x(), pts[2].y()))
            reach = prog * (seg1 + seg2)
            path = QPainterPath(pts[0])
            if reach <= seg1:
                f = reach / seg1
                path.lineTo(pts[0] + (pts[1] - pts[0]) * f)
            else:
                path.lineTo(pts[1])
                f = (reach - seg1) / seg2
                path.lineTo(pts[1] + (pts[2] - pts[1]) * f)
            p.setPen(self._pen(6, self._accent()))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
