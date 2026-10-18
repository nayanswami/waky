"""Original illustrations for the onboarding flow: soft widget tiles in the same iOS language as the website."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import ios_theme, pill_styles
from .utils import asset_path


def smooth(a: float, b: float, t: float) -> float:
    x = max(0.0, min(1.0, (t - a) / (b - a) if b != a else 1.0))
    return x * x * (3 - 2 * x)


class Illustration(QWidget):
    """One widget, several scenes. `set_kind` crossfades between them; everything loops on a 4 second phase."""

    HEIGHTS = {"welcome": 340, "engine": 250, "key": 230, "hotkey": 300, "pill": 200, "check": 190, "try": 200, "done": 300}

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
            pal = ios_theme.current()
            stage = QPainterPath()
            stage.addRoundedRect(area.adjusted(0, 0, 0, -2), 26, 26)
            p.fillPath(stage, QColor(pal.surface2))
            tint = QColor(pal.accent)
            tint.setAlpha(30 if pal.is_dark else 18)
            p.fillPath(stage, tint)
            p.setClipPath(stage)
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
    def _pal(self):
        return ios_theme.current()

    def _color(self, hexv: str, alpha: int = 255) -> QColor:
        c = QColor(hexv)
        c.setAlpha(alpha)
        return c

    def _accent(self, alpha: int = 255) -> QColor:
        return self._color(self._pal().accent, alpha)

    def _muted(self, alpha: int = 255) -> QColor:
        return self._color(self._pal().text3, alpha)

    def _pen(self, width: float = 2.6, color: QColor | None = None) -> QPen:
        pen = QPen(color or self._muted(), width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _tile(self, p: QPainter, r: QRectF, radius: float = 22, lift: float = 1.0, ring: QColor | None = None) -> None:
        """A soft white widget tile with a layered shadow and a hairline edge."""
        pal = self._pal()
        base = 26 if pal.is_dark else 12
        for dy, grow, alpha in ((14, 12, base * 0.45), (7, 6, base * 0.7), (2, 1, base)):
            path = QPainterPath()
            path.addRoundedRect(r.adjusted(-grow, -grow + dy * lift, grow, grow + dy * lift), radius + grow, radius + grow)
            p.fillPath(path, QColor(0, 0, 0, int(alpha)))
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        p.fillPath(path, QColor(pal.surface))
        p.setPen(QPen(ring or QColor(pal.sep), 1.6 if ring else 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    def _text(self, p: QPainter, r: QRectF, text: str, size: int = 11, bold: bool = True, color: QColor | None = None, align=Qt.AlignCenter) -> None:
        font = QFont("Segoe UI Variable Text", 10)
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(color or QColor(self._pal().text))
        p.drawText(r, align, text)

    def _cloud_path(self, cx: float, cy: float, s: float) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QPointF(cx - 18 * s, cy + 4 * s), 17 * s, 17 * s)
        path.addEllipse(QPointF(cx + 2 * s, cy - 8 * s), 22 * s, 22 * s)
        path.addEllipse(QPointF(cx + 24 * s, cy + 4 * s), 17 * s, 17 * s)
        path.addRoundedRect(QRectF(cx - 34 * s, cy + 2 * s, 76 * s, 19 * s), 9 * s, 9 * s)
        return path.simplified()

    # ---------- scenes ----------
    def _draw_welcome(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        pal = self._pal()
        t = self.phase
        for i in range(3):
            q = (t + i / 3) % 1.0
            p.setPen(QPen(self._accent(int((1 - q) * 60)), 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 62 + q * 96, 62 + q * 96)
        bob = math.sin(t * math.tau) * 3
        size = 104
        icon_rect = QRectF(cx - size / 2, cy - size / 2 + bob, size, size)
        for dy, grow, alpha in ((16, 14, 10), (8, 7, 16), (3, 2, 24)):
            sp = QPainterPath()
            sp.addRoundedRect(icon_rect.adjusted(-grow, -grow + dy, grow, grow + dy), 26 + grow, 26 + grow)
            p.fillPath(sp, QColor(46, 98, 255, alpha))
        if not self._icon.isNull():
            p.drawPixmap(icon_rect.toRect(), self._icon)

        def float_off(ph: float) -> float:
            return math.sin((t + ph) * math.tau) * 5

        r = QRectF(cx - 232, cy - 98 + float_off(0.0), 140, 74)
        self._tile(p, r, 18)
        self._text(p, QRectF(r.left() + 14, r.top() + 8, 100, 18), "Email", 11, True, self._accent(), Qt.AlignLeft | Qt.AlignVCenter)
        p.setPen(self._pen(5, self._color(pal.sep)))
        p.drawLine(QPointF(r.left() + 14, r.top() + 36), QPointF(r.right() - 14, r.top() + 36))
        p.drawLine(QPointF(r.left() + 14, r.top() + 52), QPointF(r.left() + 82, r.top() + 52))

        r = QRectF(cx + 94, cy - 112 + float_off(0.33), 146, 66)
        self._tile(p, r, 18)
        self._text(p, QRectF(r.left() + 14, r.top(), 80, r.height()), "Auto English", 11, True, None, Qt.AlignLeft | Qt.AlignVCenter)
        on = smooth(0.1, 0.3, t) * (1 - smooth(0.8, 0.95, t))
        tr = QRectF(r.right() - 56, r.center().y() - 13, 42, 26)
        tp = QPainterPath()
        tp.addRoundedRect(tr, 13, 13)
        off_c, on_c = QColor(pal.sep), QColor(pal.accent)
        mixed = QColor(int(off_c.red() + (on_c.red() - off_c.red()) * on), int(off_c.green() + (on_c.green() - off_c.green()) * on), int(off_c.blue() + (on_c.blue() - off_c.blue()) * on))
        p.fillPath(tp, mixed)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(tr.left() + 13 + 16 * on, tr.center().y()), 10, 10)

        r = QRectF(cx - 226, cy + 36 + float_off(0.66), 134, 78)
        self._tile(p, r, 18)
        for i in range(3):
            y = r.top() + 18 + i * 20
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent())
            p.drawEllipse(QPointF(r.left() + 18, y), 3.5, 3.5)
            p.setPen(self._pen(5, self._color(pal.sep)))
            p.drawLine(QPointF(r.left() + 30, y), QPointF(r.left() + 30 + (74, 56, 66)[i], y))

        r = QRectF(cx + 98, cy + 52 + float_off(0.5), 130, 40)
        for dy, grow, alpha in ((8, 6, 20), (3, 2, 34)):
            sp = QPainterPath()
            sp.addRoundedRect(r.adjusted(-grow, -grow + dy, grow, grow + dy), 20 + grow, 20 + grow)
            p.fillPath(sp, QColor(0, 0, 0, alpha))
        ip = QPainterPath()
        ip.addRoundedRect(r, 20, 20)
        p.fillPath(ip, QColor("#000000"))
        for i in range(7):
            h = 6 + 14 * abs(math.sin(t * math.tau * 2 + i * 0.7))
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent())
            p.drawRoundedRect(QRectF(r.center().x() - 24 + i * 7.5, r.center().y() - h / 2, 4, h), 2, 2)

    def _icon_tile(self, p: QPainter, r: QRectF, active: bool) -> None:
        self._tile(p, r, 26, 1.0 if active else 0.6, self._accent() if active else None)
        if active:
            glow = QPainterPath()
            glow.addRoundedRect(r, 26, 26)
            p.fillPath(glow, self._accent(24))

    def _draw_engine(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        cloud_on = self.engine == "cloud"
        lt = QRectF(cx - 190, cy - 56, 112, 112)
        rt = QRectF(cx + 78, cy - 56, 112, 112)
        pen = self._pen(2.4, self._muted(120))
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([1.2, 4.5])
        pen.setDashOffset(-self.phase * 26)
        p.setPen(pen)
        p.drawLine(QPointF(lt.right() + 10, cy), QPointF(rt.left() - 10, cy))
        dot = (self.phase * 1.3) % 1.0
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent())
        p.drawEllipse(QPointF(lt.right() + 10 + (rt.left() - lt.right() - 20) * dot, cy), 5, 5)
        self._icon_tile(p, lt, cloud_on)
        self._icon_tile(p, rt, not cloud_on)
        p.setBrush(Qt.NoBrush)
        p.setPen(self._pen(3, self._accent() if cloud_on else self._muted()))
        p.drawPath(self._cloud_path(lt.center().x() - 2, lt.center().y() - 4, 0.95))
        chip = QRectF(rt.center().x() - 24, rt.center().y() - 24, 48, 48)
        p.setPen(self._pen(3, self._accent() if not cloud_on else self._muted()))
        p.drawRoundedRect(chip, 10, 10)
        p.drawRoundedRect(chip.adjusted(14, 14, -14, -14), 4, 4)
        for i in range(3):
            o = -12 + i * 12
            p.drawLine(QPointF(chip.left() - 7, chip.center().y() + o), QPointF(chip.left(), chip.center().y() + o))
            p.drawLine(QPointF(chip.right(), chip.center().y() + o), QPointF(chip.right() + 7, chip.center().y() + o))
            p.drawLine(QPointF(chip.center().x() + o, chip.top() - 7), QPointF(chip.center().x() + o, chip.top()))
            p.drawLine(QPointF(chip.center().x() + o, chip.bottom()), QPointF(chip.center().x() + o, chip.bottom() + 7))
        self._text(p, QRectF(lt.left(), lt.bottom() + 12, lt.width(), 18), "Groq cloud", 12, True, self._accent() if cloud_on else self._muted())
        self._text(p, QRectF(rt.left(), rt.bottom() + 12, rt.width(), 18), "On this PC", 12, True, self._accent() if not cloud_on else self._muted())

    def _draw_key(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        slide = smooth(0.05, 0.5, t) * (1 - smooth(0.88, 1.0, t))
        opened = smooth(0.5, 0.68, t) * (1 - smooth(0.88, 1.0, t))
        lt = QRectF(cx - 190, cy - 52, 104, 104)
        rt = QRectF(cx + 86, cy - 52, 104, 104)
        self._tile(p, lt, 26)
        self._tile(p, rt, 26, ring=self._accent(int(255 * opened)) if opened > 0.05 else None)
        kx = lt.center().x() - 24 + slide * 12
        p.setBrush(Qt.NoBrush)
        p.setPen(self._pen(3.2, self._accent()))
        p.drawEllipse(QPointF(kx, cy), 13, 13)
        p.drawLine(QPointF(kx + 13, cy), QPointF(kx + 50, cy))
        p.drawLine(QPointF(kx + 38, cy), QPointF(kx + 38, cy + 9))
        p.drawLine(QPointF(kx + 48, cy), QPointF(kx + 48, cy + 6))
        lx, ly = rt.center().x(), rt.center().y()
        lift = opened * 9
        sh = QPainterPath()
        sh.moveTo(lx - 13, ly - 2)
        sh.lineTo(lx - 13, ly - 11 - lift)
        sh.arcTo(QRectF(lx - 13, ly - 24 - lift, 26, 26), 180, -180)
        sh.lineTo(lx + 13, ly - 2)
        p.setPen(self._pen(3.2, self._muted()))
        p.drawPath(sh)
        body = QPainterPath()
        body.addRoundedRect(QRectF(lx - 21, ly - 2, 42, 32), 9, 9)
        p.fillPath(body, QColor(self._pal().surface))
        p.setPen(self._pen(3.2, self._accent() if opened > 0.3 else self._muted()))
        p.drawPath(body)
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent())
        p.drawEllipse(QPointF(lx, ly + 14), 4, 4)
        pen = self._pen(2.4, self._muted(110))
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([1.2, 4.5])
        pen.setDashOffset(-t * 26)
        p.setPen(pen)
        p.drawLine(QPointF(lt.right() + 12, cy), QPointF(rt.left() - 12, cy))
        if opened > 0.4:
            br = QPointF(rt.right() - 4, rt.top() + 4)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self._pal().success))
            p.drawEllipse(br, 13 * opened, 13 * opened)
            p.setPen(self._pen(2.6, QColor("#FFFFFF")))
            p.drawLine(QPointF(br.x() - 5, br.y()), QPointF(br.x() - 1.5, br.y() + 4))
            p.drawLine(QPointF(br.x() - 1.5, br.y() + 4), QPointF(br.x() + 5, br.y() - 4))

    def _draw_hotkey(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        font = QFont("Segoe UI Variable Text", 10)
        font.setPixelSize(17)
        font.setBold(True)
        fm = QFontMetrics(font)
        widths = [max(92.0, fm.horizontalAdvance(k) + 44.0) for k in self.keys]
        gap = 16.0
        total = sum(widths) + gap * (len(widths) - 1)
        x = cx - total / 2
        press = smooth(0.2, 0.4, self.phase) * (1 - smooth(0.72, 0.9, self.phase))
        for i in range(9):
            h = (6 + 26 * abs(math.sin(self.phase * math.tau * 3 + i * 0.7))) * press
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent(int(60 + 195 * press)))
            p.drawRoundedRect(QRectF(cx - 44 + i * 11, cy - 74 - h / 2, 6, max(4, h)), 3, 3)
        for label, w in zip(self.keys, widths):
            dy = 7 * press
            r = QRectF(x, cy - 34 + dy, w, 72)
            self._tile(p, r, 22, 1.0 - 0.7 * press, self._accent() if press > 0.5 else None)
            if press > 0.5:
                gp = QPainterPath()
                gp.addRoundedRect(r, 22, 22)
                p.fillPath(gp, self._accent(26))
            self._text(p, r, label, 17, True, self._accent() if press > 0.5 else None)
            x += w + gap

    def _draw_pill(self, p: QPainter, a: QRectF) -> None:
        t = self.phase
        status = "Idle" if t < 0.18 else "Listening" if t < 0.55 else "Processing" if t < 0.75 else "Pasted" if t < 0.93 else "Idle"
        expand = smooth(0.12, 0.25, t) * (1 - smooth(0.9, 0.98, t))
        scr = QRectF(a.center().x() - 190, a.center().y() - 62, 380, 124)
        self._tile(p, scr, 26)
        style = pill_styles.get_style(self.pill_style)
        p.setPen(self._pen(5, self._color(self._pal().sep)))
        p.drawLine(QPointF(scr.left() + 34, scr.bottom() - 34), QPointF(scr.left() + 34 + 170, scr.bottom() - 34))
        p.drawLine(QPointF(scr.left() + 34, scr.bottom() - 18), QPointF(scr.left() + 34 + 110, scr.bottom() - 18))
        pill_styles.paint(
            p, QRectF(scr.left(), scr.top(), scr.width(), 74), style, status, self.phase * 6.0 % 1.0, 99.0, bottom_margin=14,
            scale=1.6 * self.pill_scale, accent=self.accent, expand=expand,
        )

    def _draw_check(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        card = QRectF(cx - 170, cy - 64, 340, 128)
        self._tile(p, card, 24)
        for i in range(3):
            y = card.top() + 28 + i * 36
            done = smooth(0.1 + i * 0.22, 0.25 + i * 0.22, t) * (1 - smooth(0.92, 1.0, t))
            circle = QPointF(card.left() + 34, y)
            p.setPen(Qt.NoPen)
            p.setBrush(self._color(self._pal().success, int(255 * done)) if done > 0.02 else self._color(self._pal().sep))
            p.drawEllipse(circle, 11, 11)
            if done > 0.5:
                p.setPen(self._pen(2.6, QColor("#FFFFFF")))
                p.drawLine(QPointF(circle.x() - 4.5, circle.y()), QPointF(circle.x() - 1.2, circle.y() + 3.6))
                p.drawLine(QPointF(circle.x() - 1.2, circle.y() + 3.6), QPointF(circle.x() + 5, circle.y() - 3.6))
            p.setPen(self._pen(6, self._color(self._pal().sep)))
            p.drawLine(QPointF(card.left() + 58, y), QPointF(card.left() + 58 + (170, 130, 150)[i], y))

    def _draw_try(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        listening = 0.1 < t < 0.8
        mic = QRectF(cx - 190, cy - 56, 112, 112)
        self._tile(p, mic, 28, ring=self._accent() if listening else None)
        circle = QRectF(mic.center().x() - 28, mic.center().y() - 28, 56, 56)
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent() if listening else self._accent(40))
        p.drawEllipse(circle)
        cap = QRectF(circle.center().x() - 8, circle.center().y() - 17, 16, 26)
        cp = QPainterPath()
        cp.addRoundedRect(cap, 8, 8)
        p.fillPath(cp, QColor("#FFFFFF") if listening else self._accent())
        p.setPen(self._pen(2.6, QColor("#FFFFFF") if listening else self._accent()))
        p.setBrush(Qt.NoBrush)
        arc = QPainterPath()
        arc.arcMoveTo(QRectF(circle.center().x() - 14, circle.center().y() - 12, 28, 28), 200)
        arc.arcTo(QRectF(circle.center().x() - 14, circle.center().y() - 12, 28, 28), 200, 140)
        p.drawPath(arc)
        doc = QRectF(cx - 56, cy - 56, 250, 112)
        self._tile(p, doc, 24)
        for i, w in enumerate((190, 150, 108)):
            prog = smooth(0.25 + i * 0.16, 0.45 + i * 0.16, t) * (1 - smooth(0.92, 1.0, t))
            y = doc.top() + 30 + i * 26
            p.setPen(self._pen(6, self._color(self._pal().sep)))
            p.drawLine(QPointF(doc.left() + 22, y), QPointF(doc.left() + 22 + w, y))
            p.setPen(self._pen(6, self._accent() if i == 0 else self._muted(200)))
            p.drawLine(QPointF(doc.left() + 22, y), QPointF(doc.left() + 22 + w * prog, y))

    def _draw_done(self, p: QPainter, a: QRectF) -> None:
        cx, cy = a.center().x(), a.center().y()
        t = self.phase
        for i in range(2):
            q = (t + i / 2) % 1.0
            p.setPen(QPen(self._accent(int((1 - q) * 70)), 1.6))
            p.setBrush(Qt.NoBrush)
            r = 56 + q * 84
            p.drawEllipse(QPointF(cx, cy), r, r)
        colors = ("#2E62FF", "#32ADE6", "#5E5CE6", "#34C759", "#FF9F0A")
        for i in range(14):
            ang = i / 14 * math.tau + 0.3
            q = (t * 1.2 + (i % 5) * 0.08) % 1.0
            dist = 70 + 70 * smooth(0, 0.7, q)
            p.setPen(Qt.NoPen)
            p.setBrush(self._color(colors[i % 5], int(220 * (1 - smooth(0.6, 1.0, q)))))
            p.drawEllipse(QPointF(cx + math.cos(ang) * dist, cy + math.sin(ang) * dist), 3.2, 3.2)
        grad = QLinearGradient(cx, cy - 50, cx, cy + 50)
        grad.setColorAt(0, QColor("#5C8BFF"))
        grad.setColorAt(1, QColor("#2E62FF"))
        for dy, grow, alpha in ((14, 12, 14), (6, 5, 22)):
            sp = QPainterPath()
            sp.addEllipse(QPointF(cx, cy + dy), 50 + grow, 50 + grow)
            p.fillPath(sp, QColor(46, 98, 255, alpha))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), 50, 50)
        pts = [QPointF(cx - 20, cy + 2), QPointF(cx - 6, cy + 16), QPointF(cx + 22, cy - 14)]
        prog = smooth(0.05, 0.28, t) if t < 0.5 else 1.0
        if prog > 0:
            s1 = math.dist((pts[0].x(), pts[0].y()), (pts[1].x(), pts[1].y()))
            s2 = math.dist((pts[1].x(), pts[1].y()), (pts[2].x(), pts[2].y()))
            reach = prog * (s1 + s2)
            path = QPainterPath(pts[0])
            if reach <= s1:
                path.lineTo(pts[0] + (pts[1] - pts[0]) * (reach / s1))
            else:
                path.lineTo(pts[1])
                path.lineTo(pts[1] + (pts[2] - pts[1]) * ((reach - s1) / s2))
            p.setPen(self._pen(6.5, QColor("#FFFFFF")))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
