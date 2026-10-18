from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

DEFAULT_ACCENT = "#2E62FF"  # Waky logo blue
SUCCESS = "#30D158"
ERROR = "#FF453A"
CANCELLED = "#FFD60A"


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


def get_style(key: str | None) -> PillStyle:
    key = LEGACY.get(key or "", key or "")
    return STYLES.get(key, STYLES[DEFAULT_STYLE])


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


def paint(painter: QPainter, area: QRectF, style: PillStyle, status: str, phase: float, status_age: float = 99.0,
          bottom_margin: float = 4.0, scale: float = 1.0, accent: str = DEFAULT_ACCENT, expand: float | None = None) -> None:
    """Draw the pill for a status inside `area`, centred horizontally and anchored to the bottom.

    `expand` (0 idle .. 1 active, may overshoot for a spring) lets the caller animate the size change.
    """
    painter.setRenderHint(QPainter.Antialiasing)
    state = state_for(status, status_age)
    idle = is_idle_state(state)
    t = (0.0 if idle else 1.0) if expand is None else expand
    width = lerp(style.idle_size[0], style.active_size[0], t) * scale
    height = max(2.0, lerp(style.idle_size[1], style.active_size[1], t) * scale)
    rect = QRectF(area.center().x() - width / 2, area.bottom() - height - bottom_margin * scale, width, height)
    color = state_color(style, state, accent)
    radius = rect.height() / 2

    if style.glow and t > 0.05:
        glow = QColor(accent if style.key == "glass" else color)
        for i, alpha in enumerate((14, 26, 42)):
            glow.setAlpha(int(alpha * min(1.0, t)))
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

    if style.wave == "line":
        _draw_line(painter, rect, color, state, phase, scale)
    elif idle and not style.shell:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(rect, radius, radius)
    elif idle:
        _draw_dots(painter, rect, color, scale)
    else:
        _draw_bars(painter, rect, color, state, phase, style.bar_scale * scale)


def _draw_dots(painter: QPainter, rect: QRectF, color: QColor, scale: float) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    count, d, gap = 5, 3.0 * scale, 3.4 * scale
    total = count * d + (count - 1) * gap
    x = rect.center().x() - total / 2
    for i in range(count):
        painter.drawEllipse(QRectF(x + i * (d + gap), rect.center().y() - d / 2, d, d))


def _draw_bars(painter: QPainter, rect: QRectF, color: QColor, state: str, phase: float, bs: float) -> None:
    painter.setPen(Qt.NoPen)
    count = 7
    bar_width, gap = 3.4 * bs, 2.0 * bs
    total = count * bar_width + (count - 1) * gap
    base_x = rect.center().x() - total / 2
    dim = state in ("error", "cancelled")
    max_height = max(3.0, rect.height() - 4)
    for index in range(count):
        if state == "listening":
            wave = (math.sin(phase * math.tau * 1.7 - index * 0.58) + 1) / 2
        elif state in ("transcribing", "processing"):
            travel = (phase * (count + 2) * 1.8) % (count + 2)
            wave = max(0.10, 1.0 - abs(travel - index) / 2.0)
        else:
            wave = 0.64
        height = min((3.4 + wave * 9.6) * (bs if bs < 1.2 else 1 + (bs - 1) * 0.7), max_height)
        if index in (0, count - 1):
            height *= 0.74
        bar = QColor(color)
        bar.setAlpha(130 if dim else int(125 + wave * 130))
        painter.setBrush(QBrush(bar))
        capsule = QRectF(base_x + index * (bar_width + gap), rect.center().y() - height / 2, bar_width, height)
        painter.drawRoundedRect(capsule, bar_width / 2, bar_width / 2)


def _draw_flat(painter: QPainter, rect: QRectF, color: QColor, scale: float) -> None:
    pen = QPen(color, 1.4 * scale)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    inset = rect.height() * 0.8
    painter.drawLine(QPointF(rect.left() + inset, rect.center().y()), QPointF(rect.right() - inset, rect.center().y()))


def _draw_line(painter: QPainter, rect: QRectF, color: QColor, state: str, phase: float, scale: float) -> None:
    if state in ("idle", "paused"):
        _draw_flat(painter, rect, color, scale)
        return
    inner = rect.adjusted(rect.height() * 0.7, 0, -rect.height() * 0.7, 0)
    max_amp = rect.height() / 2 - 3.5 * scale
    steps = 28
    path = QPainterPath()
    for i in range(steps + 1):
        u = i / steps
        x = inner.left() + u * inner.width()
        envelope = math.sin(u * math.pi)
        if state == "listening":
            amp = max_amp * envelope * (0.35 + 0.65 * (math.sin(phase * math.tau * 1.7) + 1) / 2)
            y = rect.center().y() + amp * math.sin(u * math.tau * 3 - phase * math.tau * 2)
        elif state in ("transcribing", "processing"):
            bump = math.exp(-(((u - (phase * 1.3) % 1.0) * 5) ** 2))
            y = rect.center().y() + max_amp * bump * math.sin(u * math.tau * 4)
        else:
            y = rect.center().y() + max_amp * 0.25 * envelope * math.sin(u * math.tau * 3)
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    pen = QPen(color, 1.6 * scale)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
