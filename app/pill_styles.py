from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

DEFAULT_ACCENT = "#2E62FF"  # Waky logo blue
SUCCESS = "#30D158"
ERROR = "#FF453A"
CANCELLED = "#FFD60A"
BARS = 7


@dataclass(frozen=True)
class PillStyle:
    key: str
    label: str
    blurb: str
    shell: bool
    shell_bg: str            # #AARRGGBB; ignored when shell_mix > 0
    shell_border: str
    shell_mix: float         # >0: shell is tinted with the accent colour (glass look)
    wave: str                # "bars" or "line"
    idle_size: tuple[float, float]
    active_size: tuple[float, float]
    glow: bool
    bar_scale: float         # thickness multiplier for bars
    idle_color: str
    active_color: str | None  # None = use the accent colour


STYLES: dict[str, PillStyle] = {
    "minimal": PillStyle("minimal", "Minimal", "Just the bars", False, "#00000000", "#00000000", 0, "bars", (26, 3), (46, 14), False, 1.0, "#9A9AA6", None),
    "bold": PillStyle("bold", "Bold", "Thick, easy to spot", False, "#00000000", "#00000000", 0, "bars", (36, 6), (66, 24), False, 1.7, "#8E8E98", None),
    "island": PillStyle("island", "Island", "Solid capsule", True, "#FF000000", "#FF24252B", 0, "bars", (44, 14), (84, 26), False, 1.1, "#6E6F78", None),
    "glass": PillStyle("glass", "Glass", "Frosted, tinted", True, "#00000000", "#00000000", 0.34, "bars", (42, 13), (80, 26), True, 1.1, "#FFFFFF", "#FFFFFF"),
    "line": PillStyle("line", "Line glow", "Thin waveform", True, "#F2101116", "#3A3D45", 0, "line", (40, 11), (64, 22), True, 1.0, "#A1A1AA", None),
    "light": PillStyle("light", "Light", "Clean white", True, "#F5FFFFFF", "#D2D5DD", 0, "bars", (44, 14), (84, 26), False, 1.1, "#8A8F9C", None),
}
LEGACY = {"dark_pill": "line", "amber_bars": "bold", "light_pill": "light"}
DEFAULT_STYLE = "island"


@dataclass(frozen=True)
class Motion:
    key: str
    label: str
    blurb: str
    bounce: float      # 0 = settles dead still, 1 = springy
    speed: float       # how fast the waves travel
    reach: float       # how tall the bars get
    flourish: bool     # pop, shake and ring on results


MOTIONS: dict[str, Motion] = {
    "fluid": Motion("fluid", "Fluid", "Smooth and alive. The bars follow your voice.", 0.55, 1.0, 1.0, True),
    "playful": Motion("playful", "Playful", "Bouncy, with a pop on every result.", 0.95, 1.25, 1.12, True),
    "calm": Motion("calm", "Calm", "Slow, soft and quiet.", 0.15, 0.7, 0.8, False),
    "minimal": Motion("minimal", "Minimal", "Direct changes, no bounce.", 0.0, 1.0, 0.9, False),
}
DEFAULT_MOTION = "fluid"
DEFAULT_SMOOTHNESS = 65


def get_style(key: str | None) -> PillStyle:
    key = LEGACY.get(key or "", key or "")
    return STYLES.get(key, STYLES[DEFAULT_STYLE])


def get_motion(key: str | None) -> Motion:
    return MOTIONS.get(key or "", MOTIONS[DEFAULT_MOTION])


def state_for(status: str, status_age: float) -> str:
    if status == "Paused":
        return "paused"
    if status in ("Listening", "Recording"):
        return "listening"
    if status == "Transcribing":
        return "transcribing"
    if status in ("Processing", "Pasting"):
        return "transcribing" if status_age < 1.35 else "processing"
    if status in ("Pasted", "Copied"):
        return "success"
    if status == "Cancelled":
        return "cancelled"
    if status == "Error":
        return "error"
    return "idle"


def is_idle_state(state: str) -> bool:
    return state in ("idle", "paused")


def state_color(style: PillStyle, state: str, accent: str) -> QColor:
    if state == "idle":
        return QColor(style.idle_color)
    if state == "paused":
        c = QColor(style.idle_color)
        c.setAlpha(110)
        return c
    if state == "success":
        return QColor(SUCCESS)
    if state == "error":
        return QColor(ERROR)
    if state == "cancelled":
        return QColor(CANCELLED)
    base = QColor(style.active_color) if style.active_color else QColor(accent)
    if state in ("transcribing", "processing") and not style.active_color:
        base = base.lighter(130 if state == "transcribing" else 150)
    return base


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class PillEngine:
    """Everything that moves: the open/close spring, the bar heights, the pop, shake and ring on results.

    One engine drives the real pill and the preview in Settings, so both look the same. Call `step()` every frame
    with the current microphone level (0..1) and then `paint()`.
    """

    def __init__(self) -> None:
        self.status = "Idle"
        self.t0 = time.monotonic()
        self.motion = MOTIONS[DEFAULT_MOTION]
        self.smooth = DEFAULT_SMOOTHNESS / 100.0
        self.react = True
        self.expand = 0.0
        self.vel = 0.0
        self.phase = 0.0
        self.levels = [0.15] * BARS
        self.voice = 0.0
        self._last = time.monotonic()

    # ---- configuration ----
    def configure(self, motion: str | None, smoothness: float | int | None, react: bool = True) -> None:
        self.motion = get_motion(motion)
        try:
            self.smooth = max(0.0, min(1.0, float(smoothness if smoothness is not None else DEFAULT_SMOOTHNESS) / 100.0))
        except (TypeError, ValueError):
            self.smooth = DEFAULT_SMOOTHNESS / 100.0
        self.react = bool(react)

    def set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            self.t0 = time.monotonic()

    def kick(self, amount: float = 3.2) -> None:
        self.vel += amount

    @property
    def age(self) -> float:
        return time.monotonic() - self.t0

    @property
    def state(self) -> str:
        return state_for(self.status, self.age)

    # ---- physics ----
    def _spring(self) -> tuple[float, float]:
        k = lerp(1050.0, 300.0, self.smooth)
        zeta = 1.0 - 0.55 * self.motion.bounce
        return k, 2.0 * math.sqrt(k) * zeta

    def _targets(self, state: str) -> tuple[list[float], float]:
        m, ph = self.motion, self.phase
        out: list[float] = []
        v = self.voice
        for i in range(BARS):
            if state == "listening":
                wave = 0.5 + 0.5 * math.sin(ph * math.tau * 1.7 * m.speed - i * 0.72)
                env = 1.0 - 0.18 * abs(i - (BARS - 1) / 2) / ((BARS - 1) / 2)
                out.append(min(1.0, 0.14 + m.reach * (0.22 * wave * (0.4 + 0.6 * v) + 0.62 * v * env * (0.5 + 0.5 * wave))))
            elif state == "transcribing":
                pos = (ph * 1.5 * m.speed % 1.0) * (BARS + 1.5) - 0.75
                g = math.exp(-(((i - pos) / 1.15) ** 2))
                out.append(0.14 + 0.62 * g * m.reach)
            elif state == "processing":
                out.append(0.2 + 0.34 * (0.5 + 0.5 * math.sin(ph * math.tau * 0.9 * m.speed - i * 0.25)))
            else:
                out.append(0.08)
        return out, 0.0

    def step(self, level: float = 0.0) -> bool:
        """Advance one frame. Returns True while anything is still moving."""
        now = time.monotonic()
        dt = max(0.001, min(0.05, now - self._last))
        self._last = now
        state = self.state
        idle = is_idle_state(state)
        # open / close spring
        target = 0.0 if idle else 1.0
        k, c = self._spring()
        self.vel += (k * (target - self.expand) - c * self.vel) * dt
        self.expand += self.vel * dt
        moving = abs(target - self.expand) > 0.002 or abs(self.vel) > 0.02
        if not moving:
            self.expand, self.vel = target, 0.0
        # voice level: quick to rise, slow to fall, shaped so quiet speech still shows
        shaped = min(1.0, max(0.0, level) * 9.0) ** 0.6 if self.react else 0.55 + 0.25 * math.sin(self.phase * math.tau * 2.3)
        tau = 0.045 if shaped > self.voice else 0.16
        self.voice += (shaped - self.voice) * (1 - math.exp(-dt / tau))
        self.phase = (self.phase + dt * 1.1) % 1.0
        # bar heights follow their targets with a VU-style ballistic: rise fast, fall slower
        base_tau = lerp(0.03, 0.15, self.smooth)
        targets, _ = self._targets(state)
        for i, goal in enumerate(targets):
            tau_i = base_tau * (0.6 if goal > self.levels[i] else 1.35)
            self.levels[i] += (goal - self.levels[i]) * (1 - math.exp(-dt / tau_i))
        return moving or not idle or self.age < 1.2

    # ---- drawing ----
    def paint(self, painter: QPainter, area: QRectF, style: PillStyle, accent: str = DEFAULT_ACCENT, scale: float = 1.0,
              bottom_margin: float = 4.0) -> None:
        paint(painter, area, style, self.status, self.phase, self.age, bottom_margin, scale, accent, self.expand, fx=self)


def procedural_levels(state: str, phase: float) -> list[float]:
    """Bar heights for callers that have no engine (small style cards)."""
    out = []
    for i in range(BARS):
        if state == "listening":
            out.append((math.sin(phase * math.tau * 1.7 - i * 0.58) + 1) / 2 * 0.8 + 0.1)
        elif state in ("transcribing", "processing"):
            travel = (phase * (BARS + 2) * 1.8) % (BARS + 2)
            out.append(max(0.10, 1.0 - abs(travel - i) / 2.0))
        else:
            out.append(0.64)
    return out


def paint(painter: QPainter, area: QRectF, style: PillStyle, status: str, phase: float, status_age: float = 99.0,
          bottom_margin: float = 4.0, scale: float = 1.0, accent: str = DEFAULT_ACCENT, expand: float | None = None,
          fx: PillEngine | None = None) -> None:
    """Draw the pill for a status inside `area`, centred horizontally and anchored to the bottom."""
    painter.setRenderHint(QPainter.Antialiasing)
    state = state_for(status, status_age)
    idle = is_idle_state(state)
    t = (0.0 if idle else 1.0) if expand is None else expand
    flourish = False   # no pop, shake, ring or coloured rim on results: only the dots change colour
    width = lerp(style.idle_size[0], style.active_size[0], t) * scale
    height = max(2.0, lerp(style.idle_size[1], style.active_size[1], t) * scale)
    pop = 1.0
    shake = 0.0
    if flourish and state == "success":
        pop = 1.0 + 0.11 * math.exp(-status_age * 7.5) * math.cos(status_age * 15.0)
    if flourish and state == "error":
        shake = math.sin(status_age * 46.0) * 5.0 * scale * math.exp(-status_age * 6.0)
    width *= pop
    height *= 1.0 + (pop - 1.0) * 0.8
    rect = QRectF(area.center().x() - width / 2 + shake, area.bottom() - height - bottom_margin * scale, width, height)
    color = state_color(style, state, accent)
    radius = rect.height() / 2
    result_state = state in ("success", "error", "cancelled")

    if (style.glow and t > 0.05) or (result_state and flourish and status_age < 1.0):
        glow = QColor(accent if style.key == "glass" and not result_state else color)
        strength = min(1.0, t)
        if result_state:
            strength *= max(0.0, 1.0 - status_age / 1.0)
        for i, alpha in enumerate((14, 26, 42)):
            glow.setAlpha(int(alpha * strength))
            grow = (3 - i) * 1.7 * scale
            g = rect.adjusted(-grow, -grow, grow, grow)
            path = QPainterPath()
            path.addRoundedRect(g, g.height() / 2, g.height() / 2)
            painter.fillPath(path, QBrush(glow))

    if style.shell:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        if style.shell_mix > 0:
            bg = QColor(accent)
            bg.setAlphaF(style.shell_mix + 0.1 * t)
            border = QColor(255, 255, 255, 150)
        else:
            bg, border = QColor(style.shell_bg), QColor(style.shell_border)
        painter.fillPath(path, QBrush(bg))
        painter.setPen(QPen(border, max(1.0, 1.0 * scale)))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        if style.shell_mix > 0:  # soft top highlight
            hi = QPainterPath()
            hi.addRoundedRect(rect.adjusted(1.5 * scale, 1.2 * scale, -1.5 * scale, -rect.height() * 0.5), radius * 0.6, radius * 0.6)
            painter.fillPath(hi, QBrush(QColor(255, 255, 255, 46)))

    if result_state and flourish and state == "success" and status_age < 0.7:   # a ring that breathes out
        p = ease_out(status_age / 0.7)
        ring = QColor(color)
        ring.setAlphaF(0.55 * (1 - p))
        painter.setPen(QPen(ring, 1.6 * scale))
        painter.setBrush(Qt.NoBrush)
        grow = 3 * scale + 11 * scale * p
        rr = rect.adjusted(-grow, -grow, grow, grow)
        painter.drawRoundedRect(rr, rr.height() / 2, rr.height() / 2)

    levels = fx.levels if fx else procedural_levels(state, phase)
    if result_state:
        _draw_result(painter, rect, color, state, status_age, scale)
    elif style.wave == "line":
        _draw_line(painter, rect, color, state, phase, scale, levels)
    elif idle and not style.shell:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(rect, radius, radius)
    elif idle:
        _draw_dots(painter, rect, color, scale)
    else:
        _draw_bars(painter, rect, color, state, levels, style.bar_scale * scale)


def _draw_dots(painter: QPainter, rect: QRectF, color: QColor, scale: float) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    count, d, gap = 5, 3.0 * scale, 3.4 * scale
    total = count * d + (count - 1) * gap
    x = rect.center().x() - total / 2
    for i in range(count):
        painter.drawEllipse(QRectF(x + i * (d + gap), rect.center().y() - d / 2, d, d))


def _draw_bars(painter: QPainter, rect: QRectF, color: QColor, state: str, levels: list[float], bs: float) -> None:
    painter.setPen(Qt.NoPen)
    count = BARS
    bar_width, gap = 3.4 * bs, 2.0 * bs
    total = count * bar_width + (count - 1) * gap
    base_x = rect.center().x() - total / 2
    max_height = max(3.0, rect.height() - 4)
    for index in range(count):
        wave = max(0.0, min(1.0, levels[index]))
        height = min((3.4 + wave * 9.6) * (bs if bs < 1.2 else 1 + (bs - 1) * 0.7), max_height)
        if index in (0, count - 1):
            height *= 0.74
        bar = QColor(color)
        bar.setAlpha(int(120 + wave * 135))
        painter.setBrush(QBrush(bar))
        capsule = QRectF(base_x + index * (bar_width + gap), rect.center().y() - height / 2, bar_width, height)
        painter.drawRoundedRect(capsule, bar_width / 2, bar_width / 2)


def _draw_result(painter: QPainter, rect: QRectF, color: QColor, state: str, age: float, scale: float) -> None:
    """The result as the pill's own five dots: they light up in a green wave, flash red, or dim to amber."""
    painter.setPen(Qt.NoPen)
    count, d, gap = 5, 3.4 * scale, 3.6 * scale
    total = count * d + (count - 1) * gap
    x = rect.center().x() - total / 2
    for i in range(count):
        if state == "success":
            lit = ease_out((age - i * 0.07) / 0.28)               # a wave runs left to right
            swell = 1.0 + 0.45 * math.sin(min(1.0, max(0.0, (age - i * 0.07) / 0.35)) * math.pi)
            alpha = 70 + 185 * lit
        elif state == "error":
            lit = 1.0
            swell = 1.0 + 0.25 * abs(math.sin(age * 15.0)) * math.exp(-age * 3.0)
            alpha = 120 + 135 * abs(math.sin(age * 12.0 + 0.4)) ** 0.5 * math.exp(-age * 1.6) + 0 * i
        else:
            lit = 1.0
            swell = 1.0
            alpha = 150 * max(0.25, 1.0 - age / 1.2)
        dot = QColor(color)
        dot.setAlpha(int(max(0, min(255, alpha))))
        painter.setBrush(dot)
        size = d * swell
        painter.drawEllipse(QRectF(x + i * (d + gap) + (d - size) / 2, rect.center().y() - size / 2, size, size))


def _stroke(painter: QPainter, pts: list[QPointF], progress: float) -> None:
    """Draw the first `progress` (0..1) of a polyline."""
    if progress <= 0:
        return
    lengths = [math.hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(pts, pts[1:])]
    remaining = sum(lengths) * min(1.0, progress)
    path = QPainterPath(pts[0])
    for (a, b), seg in zip(zip(pts, pts[1:]), lengths):
        if remaining <= 0:
            break
        f = min(1.0, remaining / seg) if seg else 1.0
        path.lineTo(QPointF(lerp(a.x(), b.x(), f), lerp(a.y(), b.y(), f)))
        remaining -= seg
    painter.drawPath(path)


def _draw_flat(painter: QPainter, rect: QRectF, color: QColor, scale: float) -> None:
    pen = QPen(color, 1.4 * scale)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    inset = rect.height() * 0.8
    painter.drawLine(QPointF(rect.left() + inset, rect.center().y()), QPointF(rect.right() - inset, rect.center().y()))


def _draw_line(painter: QPainter, rect: QRectF, color: QColor, state: str, phase: float, scale: float, levels: list[float]) -> None:
    if state in ("idle", "paused"):
        _draw_flat(painter, rect, color, scale)
        return
    inner = rect.adjusted(rect.height() * 0.7, 0, -rect.height() * 0.7, 0)
    max_amp = rect.height() / 2 - 3.5 * scale
    energy = sum(levels) / len(levels)
    steps = 40
    path = QPainterPath()
    for i in range(steps + 1):
        u = i / steps
        x = inner.left() + u * inner.width()
        envelope = math.sin(u * math.pi)
        if state == "listening":
            y = rect.center().y() + max_amp * envelope * min(1.0, energy * 1.5) * math.sin(u * math.tau * 3 - phase * math.tau * 2)
        elif state in ("transcribing", "processing"):
            bump = math.exp(-(((u - (phase * 1.3) % 1.0) * 5) ** 2))
            y = rect.center().y() + max_amp * bump * math.sin(u * math.tau * 4)
        else:
            y = rect.center().y()
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    pen = QPen(color, 1.6 * scale)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
