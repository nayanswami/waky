from __future__ import annotations

import os
import re
import sys
from pathlib import Path


FROZEN = bool(getattr(sys, "frozen", False))

# Where the code lives (the install folder when packaged).
PROJECT_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]

# Where user data lives. Packaged installs may sit in a read-only folder, so use %APPDATA%\Waky there.
# WAKY_DATA_DIR overrides both (portable installs, tests).
if os.environ.get("WAKY_DATA_DIR"):
    DATA_DIR = Path(os.environ["WAKY_DATA_DIR"])
elif FROZEN:
    DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "Waky"
else:
    DATA_DIR = PROJECT_ROOT

try:  # a read-only or missing profile folder must not stop the app from starting
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    import tempfile

    DATA_DIR = Path(tempfile.gettempdir()) / "Waky"

CONFIG_DIR = DATA_DIR / "config"
LOG_DIR = DATA_DIR / "logs"
MEMORY_DIR = DATA_DIR / "memory"
RUNTIME_DIR = DATA_DIR / "runtime"


MODE_LABELS = {
    "raw": "Raw",
    "clean_casual": "Clean Casual",
    "professional": "Professional",
    "bullet_points": "Bullet Points",
    "prompt": "Prompt",
    "whatsapp": "WhatsApp",
    "email": "Email",
    "translate_english": "Translate to English",
}

LANGUAGE_LABELS = {
    "auto": "Auto",
    "english": "English",
    "hindi": "Hindi",
    "hinglish": "Hinglish",
    "translate_english": "Translate to English",
}


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sentence_case(text: str) -> str:
    text = normalize_spaces(text)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def ensure_terminal_punctuation(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?":
        return text + "."
    return text


def safe_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


def asset_path(name: str) -> Path:
    """Bundled read-only asset (logo, icon). Works from source and from the PyInstaller build."""
    return RESOURCE_DIR / "assets" / name
