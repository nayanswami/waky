"""Insights: totals, streaks and your most-used phrases. Counts only, kept on this PC, never audio or full text.

Updated once per finished dictation. Phrase tracking is skipped when "Remember recent dictations" is off.
"""
from __future__ import annotations

import difflib
import json
import logging
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from .utils import DATA_DIR

LOGGER = logging.getLogger("waky")
MAX_WORDS_TRACKED = 3000
MAX_PHRASES_TRACKED = 3000
KEEP_DAYS = 400

STOP_WORDS = frozenset(
    "a an and are as at be but by for from had has have he her his i if in is it its me my of on or our she so that the their them then there they this to us was we were will with you your".split()
)
CATEGORIES = ("Chat", "Email", "Code", "Documents", "Browser", "Other")
APP_CATEGORIES = {
    "Chat": ("slack", "discord", "whatsapp", "telegram", "teams", "signal", "messenger"),
    "Email": ("outlook", "olk", "thunderbird", "mail"),
    "Code": ("code", "cursor", "devenv", "pycharm", "idea", "windowsterminal", "cmd", "powershell", "pwsh", "wt"),
    "Documents": ("notion", "winword", "onenote", "obsidian", "notepad", "excel", "powerpnt"),
    "Browser": ("chrome", "msedge", "firefox", "brave", "opera", "arc", "vivaldi"),
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w][\w'\-]*", text.lower())


def category_for(exe: str) -> str:
    stem = (exe or "").lower().removesuffix(".exe")
    for name, stems in APP_CATEGORIES.items():
        if stem in stems:
            return name
    return "Other"


def corrected_words(heard: str, written: str) -> list[str]:
    """Words Waky changed or removed between the raw transcript and the final text (fillers, wrong words)."""
    a, b = _tokens(heard), _tokens(written)
    out: list[str] = []
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            out.extend(a[i1:i2])
    return out


def _trim(counter: dict[str, int], limit: int) -> None:
    if len(counter) > limit * 1.25:
        keep = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        counter.clear()
        counter.update(keep)


class Stats:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA_DIR / "stats.json")
        self._lock = threading.RLock()
        self.data: dict = {}
        self._load()

    # ---------- storage ----------
    @staticmethod
    def _blank() -> dict:
        return {
            "total_words": 0, "dictations": 0, "seconds": 0.0, "fixes": 0, "taught": 0, "best_wpm": 0,
            "since": date.today().isoformat(), "days": {}, "apps": {}, "words": {}, "phrases": {}, "corrected": {},
        }

    def _load(self) -> None:
        self.data = self._blank()
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key, value in loaded.items():
                    if key in self.data and type(value) is type(self.data[key]):
                        self.data[key] = value
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            LOGGER.warning("[STATS] could not save", exc_info=True)

    # ---------- recording ----------
    def record(self, heard: str, written: str, seconds: float, app_exe: str = "", track_phrases: bool = True, when: date | None = None) -> None:
        words = _tokens(written)
        if not words:
            return
        today = (when or date.today()).isoformat()
        with self._lock:
            d = self.data
            d["total_words"] += len(words)
            d["dictations"] += 1
            if seconds and seconds >= 1.0:
                d["seconds"] += float(seconds)
                d["best_wpm"] = max(int(d["best_wpm"]), min(400, int(len(words) * 60 / seconds))) if len(words) >= 5 else d["best_wpm"]
            d["days"][today] = d["days"].get(today, 0) + len(words)
            if len(d["days"]) > KEEP_DAYS:
                for old in sorted(d["days"])[: len(d["days"]) - KEEP_DAYS]:
                    del d["days"][old]
            category = category_for(app_exe)
            d["apps"][category] = d["apps"].get(category, 0) + 1
            changed = corrected_words(heard, written) if heard else []
            d["fixes"] += len(changed)
            if track_phrases:
                for w in words:
                    d["words"][w] = d["words"].get(w, 0) + 1
                for i in range(len(words) - 2):
                    gram = " ".join(words[i : i + 3])
                    if not all(w in STOP_WORDS for w in words[i : i + 3]):
                        d["phrases"][gram] = d["phrases"].get(gram, 0) + 1
                for w in changed:
                    d["corrected"][w] = d["corrected"].get(w, 0) + 1
                _trim(d["words"], MAX_WORDS_TRACKED)
                _trim(d["phrases"], MAX_PHRASES_TRACKED)
                _trim(d["corrected"], 500)
            self._save()

    def add_taught(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self.data["taught"] += count
            self._save()

    def reset(self) -> None:
        with self._lock:
            self.data = self._blank()
            self._save()

    # ---------- reading ----------
    def streak(self, today: date | None = None) -> tuple[int, int]:
        """(current streak in days, longest streak). Today does not break a streak that is still alive from yesterday."""
        days = {date.fromisoformat(k) for k in self.data["days"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)}
        if not days:
            return 0, 0
        today = today or date.today()
        cursor = today if today in days else today - timedelta(days=1)
        current = 0
        while cursor in days:
            current += 1
            cursor -= timedelta(days=1)
        longest = run = 0
        previous = None
        for day in sorted(days):
            run = run + 1 if previous and day - previous == timedelta(days=1) else 1
            longest = max(longest, run)
            previous = day
        return current, longest

    def wpm(self) -> int:
        seconds = float(self.data["seconds"])
        return int(self.data["total_words"] * 60 / seconds) if seconds >= 30 else 0

    def top_word(self) -> tuple[str, int] | None:
        words = self.data["words"]
        ranked = [kv for kv in words.items() if kv[0] not in STOP_WORDS]
        return max(ranked, key=lambda kv: kv[1]) if ranked else None

    def top_phrase(self, minimum: int = 2) -> tuple[str, int] | None:
        phrases = self.data["phrases"]
        if not phrases:
            return None
        best = max(phrases.items(), key=lambda kv: kv[1])
        return best if best[1] >= minimum else None

    def top_corrected(self) -> tuple[str, int] | None:
        corrected = self.data["corrected"]
        return max(corrected.items(), key=lambda kv: kv[1]) if corrected else None

    def top_phrases(self, limit: int = 5, minimum: int = 2) -> list[tuple[str, int]]:
        ranked = sorted(self.data["phrases"].items(), key=lambda kv: kv[1], reverse=True)
        return [kv for kv in ranked if kv[1] >= minimum][:limit]

    def app_share(self) -> list[tuple[str, int, float]]:
        apps = self.data["apps"]
        total = sum(apps.values()) or 1
        rows = [(name, apps[name], apps[name] * 100 / total) for name in CATEGORIES if apps.get(name)]
        return sorted(rows, key=lambda r: r[1], reverse=True)

    def heatmap(self, weeks: int = 14, today: date | None = None) -> list[list[tuple[date, int]]]:
        """Columns of 7 days (Mon..Sun), oldest week first, ending with the current week."""
        today = today or date.today()
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=weeks - 1)
        days = self.data["days"]
        grid: list[list[tuple[date, int]]] = []
        for w in range(weeks):
            col = []
            for d in range(7):
                day = start + timedelta(weeks=w, days=d)
                col.append((day, days.get(day.isoformat(), 0) if day <= today else -1))
            grid.append(col)
        return grid

    def books_written(self) -> float:
        return self.data["total_words"] / 90000
