"""Render assets/waky.ico: dark rounded square with the Waky pill and an amber waveform."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1]


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    p.fillPath(bg, QBrush(QColor("#0B0B0D")))
    pill = QRectF(size * 0.13, size * 0.35, size * 0.74, size * 0.30)
    for grow, alpha in ((0.05, 30), (0.03, 55), (0.015, 90)):
        glow = QColor("#FF7A1A")
        glow.setAlpha(alpha)
        g = QPainterPath()
        r = pill.adjusted(-size * grow, -size * grow, size * grow, size * grow)
        g.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(g, QBrush(glow))
    body = QPainterPath()
    body.addRoundedRect(pill, pill.height() / 2, pill.height() / 2)
    p.fillPath(body, QBrush(QColor("#16171A")))
    p.setPen(QPen(QColor("#3A3D45"), max(1.0, size * 0.012)))
    p.drawPath(body)
    wave = QPainterPath()
    left, right = pill.left() + pill.height() * 0.6, pill.right() - pill.height() * 0.6
    for i in range(41):
        u = i / 40
        x = left + u * (right - left)
        y = pill.center().y() + pill.height() * 0.30 * math.sin(u * math.pi) * math.sin(u * math.tau * 3)
        wave.moveTo(x, y) if i == 0 else wave.lineTo(x, y)
    pen = QPen(QColor("#FF7A1A"), max(1.5, size * 0.03))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(wave)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication([])
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    ok = render(256).save(str(out / "waky.ico"), "ICO")
    render(256).save(str(out / "waky-icon.png"), "PNG")
    print("wrote", out / "waky.ico", ok)
    sys.exit(0 if ok else 1)
