"""Build assets/waky.ico from the official blue logo (assets/waky-icon.png). Never touches the PNG.

An older version of this script drew an orange waveform icon and overwrote the logo on every build.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


def build_ico(source: Path, target: Path) -> None:
    logo = QImage(str(source))
    if logo.isNull():
        raise SystemExit(f"Cannot read {source}")
    frames = [png_bytes(logo.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries = b""
    for size, frame in zip(SIZES, frames):
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(frame), offset)
        offset += len(frame)
    target.write_bytes(header + entries + b"".join(frames))


if __name__ == "__main__":
    app = QGuiApplication([])
    out = ROOT / "assets"
    build_ico(out / "waky-icon.png", out / "waky.ico")
    print("wrote", out / "waky.ico")
    sys.exit(0)
