"""Tiny UI sound cues (start / stop / done / error), generated once as WAV files and played with winsound."""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

from .utils import DATA_DIR

RATE = 44100
CUES = {
    "start": [(660, 0.050), (990, 0.070)],
    "stop": [(880, 0.045), (587, 0.075)],
    "done": [(784, 0.050), (1175, 0.110)],
    "error": [(247, 0.090), (196, 0.140)],
    "lock": [(880, 0.035), (1320, 0.035), (1760, 0.070)],
}
_ready: dict[str, Path] = {}


def _render(cue: str, path: Path) -> None:
    samples: list[int] = []
    for freq, length in CUES[cue]:
        n = int(RATE * length)
        for i in range(n):
            t = i / RATE
            env = min(1.0, i / (RATE * 0.006)) * (1.0 - i / n) ** 1.6   # quick attack, soft decay
            value = math.sin(2 * math.pi * freq * t) + 0.18 * math.sin(2 * math.pi * freq * 2 * t)
            samples.append(int(max(-1.0, min(1.0, value * env * 0.22)) * 32767))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def _path_for(cue: str) -> Path | None:
    if cue in _ready:
        return _ready[cue]
    try:
        folder = DATA_DIR / "cache" / "sounds"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{cue}.wav"
        if not path.exists():
            _render(cue, path)
        _ready[cue] = path
        return path
    except Exception:
        return None


def play(cue: str) -> None:
    if sys.platform != "win32" or cue not in CUES:
        return
    path = _path_for(cue)
    if not path:
        return
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
