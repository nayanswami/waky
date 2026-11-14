"""How you like your sentences: learned from what you keep or change after Waky pastes. Counts only, on this PC."""
from __future__ import annotations

import json
import logging
import re
import threading

from .utils import DATA_DIR

LOGGER = logging.getLogger("waky")
MIN_SAMPLES = 5      # edits needed before Waky changes anything
MIN_SHARE = 0.8      # how consistent you must be

_FLAGS = ("end_period", "start_capital", "comma")
_lock = threading.Lock()
_path = DATA_DIR / "style.json"


def _load() -> dict:
    try:
        data = json.loads(_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"samples": 0, **{f: 0 for f in _FLAGS}}


def _save(data: dict) -> None:
    try:
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        LOGGER.warning("[STYLE] could not save", exc_info=True)


def observe(text: str) -> None:
    """Record the style of a sentence you finished editing by hand."""
    text = text.strip()
    if len(text.split()) < 3:
        return
    last_line = text.splitlines()[-1].strip()
    with _lock:
        data = _load()
        data["samples"] = int(data.get("samples", 0)) + 1
        data["end_period"] = int(data.get("end_period", 0)) + (1 if last_line.endswith((".", "!", "?")) else 0)
        data["start_capital"] = int(data.get("start_capital", 0)) + (1 if text[:1].isupper() else 0)
        data["comma"] = int(data.get("comma", 0)) + (1 if "," in text else 0)
        _save(data)


def _habit(data: dict, flag: str) -> bool | None:
    n = int(data.get("samples", 0))
    if n < MIN_SAMPLES:
        return None
    share = int(data.get(flag, 0)) / n
    if share >= MIN_SHARE:
        return True
    if share <= 1 - MIN_SHARE:
        return False
    return None


def apply(text: str) -> str:
    """Nudge a single finished sentence toward your habits (final full stop, first capital)."""
    stripped = text.strip()
    if not stripped or "\n" in stripped or len(stripped.split()) > 40:
        return text
    data = _load()
    if _habit(data, "end_period") is False:
        stripped = re.sub(r"(?<![.!?])\.$", "", stripped)
    if _habit(data, "start_capital") is False and stripped[:1].isupper() and not stripped[:2].isupper():
        stripped = stripped[:1].lower() + stripped[1:]
    return stripped


def llm_hint() -> str:
    data = _load()
    bits = []
    if _habit(data, "end_period") is False:
        bits.append("no full stop at the end of a short message")
    if _habit(data, "start_capital") is False:
        bits.append("starts sentences in lower case")
    if _habit(data, "comma") is True:
        bits.append("uses commas")
    return ("The user's writing style: " + ", ".join(bits) + ".") if bits else ""


def reset() -> None:
    with _lock:
        _save({"samples": 0, **{f: 0 for f in _FLAGS}})
