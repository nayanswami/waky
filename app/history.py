"""Recent dictations: what Waky heard and what it wrote. Local text only, never audio.

Used for three things: a review list in Settings, teaching Waky from your corrections, and short context
for the writing model ("what did the user just write in this conversation?").
"""
from __future__ import annotations

import difflib
import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from .utils import DATA_DIR

LOGGER = logging.getLogger("waky")
MAX_SAVED = 200
CONTEXT_MINUTES = 10


def _words(text: str) -> list[str]:
    return re.findall(r"[\w'@.\-]+|[^\w\s]", text)


def _core(word: str) -> str:
    return re.sub(r"[^\w]", "", word).lower()


def word_changes(before: str, after: str) -> list[tuple[str, str]]:
    """Small replacements between two versions of a text: [('rahool', 'Rahul'), ...]. Insertions and deletions are ignored."""
    a, b = _words(before), _words(after)
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=[_core(w) or w for w in a], b=[_core(w) or w for w in b], autojunk=False).get_opcodes():
        if tag != "replace":
            continue
        old = [w.strip(".,;:!?\"'()") for w in a[i1:i2] if _core(w)]
        new = [w.strip(".,;:!?\"'()") for w in b[j1:j2] if _core(w)]
        if 0 < len(old) <= 3 and 0 < len(new) <= 3:
            out.append((" ".join(old), " ".join(new)))
    # casing-only edits do not show up above because the comparison is case-insensitive
    for x, y in zip(a, b):
        if len(a) == len(b) and _core(x) == _core(y) and x != y and _core(x):
            out.append((x, y))
    seen: set[tuple[str, str]] = set()
    unique = []
    for pair in out:
        if pair not in seen and pair[0] != pair[1]:
            seen.add(pair)
            unique.append(pair)
    return unique


def fix_pairs(heard: str, written: str, final: str) -> list[tuple[str, str]]:
    """What the user changed by hand (written -> final), plus the raw 'sounds like' word Waky originally heard for each one."""
    changed = word_changes(written, final)
    heard_to_written = word_changes(heard, written) if heard else []
    out: list[tuple[str, str]] = []
    for wrong, right in changed:
        out.append((wrong, right))
        for heard_word, written_word in heard_to_written:
            if _core(written_word) == _core(wrong) and _core(heard_word) != _core(wrong):
                out.append((heard_word, right))
    seen: set[tuple[str, str]] = set()
    return [p for p in out if not (p in seen or seen.add(p))]


def learn(pairs: list[tuple[str, str]]) -> int:
    """Save (wrong, right) pairs into Waky's memory. Returns how many were saved."""
    from . import local_memory

    saved = 0
    for wrong, right in pairs:
        wrong, right = wrong.strip(), right.strip()
        if not wrong or not right:
            continue
        if _core(wrong) == _core(right):   # only the casing changed: remember the spelling
            local_memory.add_vocabulary_item(right, "Taught from history")
        else:
            local_memory.add_correction(wrong, right, "Taught from history")
            if any(ch.isupper() for ch in right) or any(ord(ch) > 127 for ch in right):
                local_memory.add_vocabulary_item(right, "Taught from history")
        saved += 1
    return saved


class History:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA_DIR / "history.json")
        self._lock = threading.RLock()
        self.items: list[dict] = []   # oldest first
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [i for i in data.get("items", []) if isinstance(i, dict)][-MAX_SAVED:]
        except Exception:
            self.items = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"items": self.items[-MAX_SAVED:]}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            LOGGER.warning("[HISTORY] could not save", exc_info=True)

    def add(self, heard: str, written: str, app: str = "", persist: bool = True) -> int:
        entry = {"id": int(time.time() * 1000), "time": datetime.now().isoformat(timespec="seconds"), "app": app, "heard": heard, "written": written}
        with self._lock:
            self.items.append(entry)
            if persist:
                self._save()
            else:
                self.items = self.items[-6:]   # context only, kept in memory
        return entry["id"]

    def recent_context(self, app: str = "", count: int = 2, max_chars: int = 500) -> str:
        """The last few things written in the same app within a few minutes, newest last."""
        cutoff = time.time() - CONTEXT_MINUTES * 60
        with self._lock:
            picked: list[str] = []
            for item in reversed(self.items):
                try:
                    when = datetime.fromisoformat(item["time"]).timestamp()
                except Exception:
                    continue
                if when < cutoff:
                    break
                if app and item.get("app") and item["app"] != app:
                    continue
                picked.append(str(item.get("written", "")).strip())
                if len(picked) >= count:
                    break
        text = "\n".join(reversed([p for p in picked if p]))
        return text[-max_chars:]

    def best_match(self, text: str, minimum: float = 0.45) -> dict | None:
        """The recent dictation that `text` (an edited copy of it, or part of it) most resembles."""
        target = [_core(w) for w in _words(text) if _core(w)]
        if not target:
            return None
        best, best_score = None, minimum
        with self._lock:
            for item in reversed(self.items[-25:]):
                words = [_core(w) for w in _words(str(item.get("written", ""))) if _core(w)]
                if not words:
                    continue
                matcher = difflib.SequenceMatcher(a=words, b=target, autojunk=False)
                score = matcher.ratio()
                if len(target) < len(words):   # the selection may be one sentence of a longer dictation
                    score = max(score, sum(b.size for b in matcher.get_matching_blocks()) / len(target) * 0.9)
                if score > best_score:
                    best, best_score = item, score
        return best

    def newest_first(self) -> list[dict]:
        with self._lock:
            return list(reversed(self.items))

    def update_written(self, entry_id: int, text: str) -> None:
        with self._lock:
            for item in self.items:
                if item.get("id") == entry_id:
                    item["written"] = text
            self._save()

    def delete(self, entry_id: int) -> None:
        with self._lock:
            self.items = [i for i in self.items if i.get("id") != entry_id]
            self._save()

    def clear(self) -> None:
        with self._lock:
            self.items = []
            self._save()
