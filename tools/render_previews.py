"""Render design previews (wizard, settings, floating bar, logo) to PNG for review. Dev tool, not shipped.

Windows are placed far off-screen and grabbed, so nothing flashes on the monitor and real Windows fonts are used.
Usage: python tools/render_previews.py <output_dir>
"""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from app import ios_theme, pill_styles, secret_store

secret_store.get = lambda name: ""  # never touch the real credential store
secret_store.set = lambda name, value: True

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "design-preview")
OUT.mkdir(parents=True, exist_ok=True)
app = QApplication([])

from app.config_manager import ConfigManager
from app.ui_onboarding import OnboardingWizard
from app.ui_settings import SettingsWindow
from app.utils import asset_path


class Stub:
    def __getattr__(self, name):
        return lambda *a, **k: ""


def settle(widget, ms=450):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def shoot(widget, name, w, h):
    widget.resize(w, h)
    widget.move(-6000, 0)
    widget.show()
    settle(widget)
    widget.grab().save(str(OUT / name))
    widget.hide()


def make(appearance):
    theme = ios_theme.ThemeManager(app, appearance)
    cfg = ConfigManager(Path(tempfile.mkdtemp()))
    cfg.settings["floating_bar"].update({"style": "island", "accent": "#2E62FF"})
    return theme, cfg


# ---------- wizard (light) ----------
theme, cfg = make("light")
wiz = OnboardingWizard(cfg)
wiz.key_edit.setText("gsk_example_key_value")
wiz.move(-6000, 0)
wiz.show()
settle(wiz, 600)
for i, name in enumerate(["welcome", "engine", "key", "hotkey", "style", "check", "try", "done"]):
    wiz.jump(i)
    settle(wiz, 1100 if i in (3, 4) else 700)  # let the illustration reach its pressed / listening frame
    wiz.grab().save(str(OUT / f"wizard_{name}.png"))
wiz.hide()

# ---------- settings (dark + light) ----------
for appearance in ("light", "dark"):
    theme, cfg = make(appearance)
    win = SettingsWindow(cfg, Stub(), Stub(), Stub(), logging.getLogger("preview"))
    win.resize(1180, 780)
    win.move(-6000, 0)
    win.show()
    settle(win, 600)
    for title in ("General", "Hotkeys", "Floating Bar", "Commands", "Transcription"):
        idx = win.tabs.index_of(title)
        win.tabs.setCurrentIndex(idx)
        settle(win, 200)
        win.grab().save(str(OUT / f"settings_{appearance}_{title.lower().replace(' ', '_')}.png"))
    win.hide()

# ---------- floating bar styles on desktop-like backdrops ----------
accent = "#2E62FF"
states = ["Idle", "Listening", "Processing", "Pasted", "Error"]
backs = [("Dark wallpaper", QColor("#14151A"), QColor("#2B2E3A")), ("Light wallpaper", QColor("#DCE3F2"), QColor("#F4F6FB")), ("Photo", QColor("#1E3C72"), QColor("#B5489B"))]
cell_w, cell_h, label_w = 150, 74, 170
img = QImage(label_w + len(states) * cell_w, 50 + len(pill_styles.STYLES) * len(backs) * cell_h // 1, QImage.Format_ARGB32)
img.fill(QColor("#0B0C0F"))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
font = QFont("Segoe UI", 10)
p.setFont(font)
y = 40
p.setPen(QColor("#F4F5F8"))
for i, s in enumerate(states):
    p.drawText(QRectF(label_w + i * cell_w, 8, cell_w, 28), Qt.AlignCenter, s)
for style in pill_styles.STYLES.values():
    for bname, c1, c2 in backs:
        grad = QLinearGradient(label_w, y, label_w + len(states) * cell_w, y + cell_h)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(QRectF(label_w, y, len(states) * cell_w, cell_h - 2), grad)
        p.setPen(QColor("#F4F5F8"))
        p.drawText(QRectF(10, y, label_w - 14, cell_h - 2), Qt.AlignVCenter | Qt.AlignLeft, f"{style.label}\n{bname}")
        for i, st in enumerate(states):
            pill_styles.paint(p, QRectF(label_w + i * cell_w, y, cell_w, cell_h - 2), style, st, 0.3, 5.0, bottom_margin=(cell_h - 2 - 28) / 2, accent=accent)
        y += cell_h
p.end()
img.save(str(OUT / "floating_bar_styles.png"))

# ---------- floating bar sizes + colours ----------
img = QImage(900, 260, QImage.Format_ARGB32)
img.fill(QColor("#14151A"))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setFont(QFont("Segoe UI", 10))
p.setPen(QColor("#A3A7B3"))
for i, scale in enumerate((0.6, 0.8, 1.0, 1.4, 1.8)):
    p.drawText(QRectF(i * 180, 10, 180, 24), Qt.AlignCenter, f"{int(scale * 100)}%")
    pill_styles.paint(p, QRectF(i * 180, 30, 180, 80), pill_styles.get_style("island"), "Listening", 0.3, 5.0, bottom_margin=26, scale=scale, accent=accent)
for i, (name, col) in enumerate((("Waky blue", "#2E62FF"), ("Sky", "#32ADE6"), ("Indigo", "#5E5CE6"), ("Pink", "#FF375F"), ("Green", "#30D158"))):
    p.drawText(QRectF(i * 180, 130, 180, 24), Qt.AlignCenter, name)
    pill_styles.paint(p, QRectF(i * 180, 150, 180, 80), pill_styles.get_style("glass"), "Listening", 0.3, 5.0, bottom_margin=26, accent=col)
p.end()
img.save(str(OUT / "floating_bar_sizes_colors.png"))

# ---------- logo board ----------
board = QImage(1000, 420, QImage.Format_ARGB32)
board.fill(QColor("#F2F3F7"))
p = QPainter(board)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.SmoothPixmapTransform)
icon = QPixmap(str(asset_path("waky-icon.png")))
mark = QPixmap(str(asset_path("waky-mark.png")))
p.drawPixmap(40, 40, icon.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
p.fillRect(QRectF(260, 40, 330, 200), QColor("#0B0C0F"))
ms = mark.scaled(250, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
p.drawPixmap(260 + (330 - ms.width()) // 2, 40 + (200 - ms.height()) // 2, ms)
tinted = QImage(mark.size(), QImage.Format_ARGB32)
tinted.fill(QColor("#2E62FF"))
tp = QPainter(tinted)
tp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
tp.drawPixmap(0, 0, mark)
tp.end()
ts = QPixmap.fromImage(tinted).scaled(250, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
p.fillRect(QRectF(610, 40, 350, 200), QColor("#FFFFFF"))
p.drawPixmap(610 + (350 - ts.width()) // 2, 40 + (200 - ts.height()) // 2, ts)
for i, s in enumerate((16, 24, 32, 48, 64)):
    p.drawPixmap(40 + i * 80, 280, icon.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation))
p.setPen(QColor("#5F6470"))
p.setFont(QFont("Segoe UI", 10))
p.drawText(40, 262, "App icon (and sizes)")
p.drawText(260, 262, "Mark on dark")
p.drawText(610, 262, "Mark on light")
p.end()
board.save(str(OUT / "logo_board.png"))
print("rendered to", OUT)
