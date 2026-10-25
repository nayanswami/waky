"""What Waky knows about how you talk: your vocabulary and the corrections you taught it.

The same facts are used three times: as a hint to the speech model (so names are heard right in the first place),
as context for the writing model, and to spell your words your way afterwards.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .utils import CONFIG_DIR

LOGGER = logging.getLogger("waky")

# Seeds from older Waky versions that described the author's own project, not the user's vocabulary.
LEGACY_VOCAB = {
    "wispr flow", "whisperflow", "codex", "notion", "selected text rewrite", "floating bar", "command processor", "groq api",
    "prompt mode", "rewrite and humanizer", "openai", "openrouter",
}

LANGUAGE_HINTS = {
    "hinglish": "Kal main office jaunga, meeting hai. Then I will send you the file, theek hai?",
    "hindi": "",
    "english": "",
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def vocabulary(limit: int = 60) -> list[str]:
    """Words the user chose (Settings > Vocabulary, voice 'remember vocabulary', taught words). Auto-detected junk is skipped."""
    terms: list[str] = []
    terms.extend(str(w).strip() for w in _read_json(CONFIG_DIR / "vocabulary.json").get("words", []))
    try:
        from . import local_memory

        memory = local_memory.load_memory()
        sources = [memory.get("custom_vocabulary", {}), memory.get("active_project_data", {}).get("vocabulary", {})]
        for data in sources:
            for item in data.get("items", []):
                if isinstance(item, dict) and "auto-detected" not in str(item.get("notes", "")).lower():
                    terms.append(str(item.get("term", "")).strip())
            terms.extend(str(w).strip() for w in data.get("words", []))
    except Exception:
        LOGGER.info("[HINTS] memory vocabulary unavailable", exc_info=True)
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = term.lower()
        if term and key not in seen and key not in LEGACY_VOCAB and len(term) <= 40:
            seen.add(key)
            out.append(term)
    return out[:limit]


def corrections(limit: int = 40) -> list[tuple[str, str]]:
    """(heard, meant) pairs the user taught Waky."""
    pairs: list[tuple[str, str]] = []
    try:
        from . import local_memory

        memory = local_memory.load_memory()
        for data in (memory.get("corrections", {}), memory.get("active_project_data", {}).get("corrections", {})):
            for item in data.get("corrections", []):
                if isinstance(item, dict):
                    wrong, right = str(item.get("wrong", "")).strip(), str(item.get("correct", "")).strip()
                    if wrong and right and wrong.lower() != right.lower():
                        pairs.append((wrong, right))
    except Exception:
        LOGGER.info("[HINTS] corrections unavailable", exc_info=True)
    return pairs[-limit:]


def stt_prompt(settings: dict | None) -> str:
    """A short prompt for Whisper: it spells names from the prompt and copies its language and style."""
    transcription = (settings or {}).get("transcription", {}) if isinstance(settings, dict) else {}
    parts: list[str] = []
    hint = LANGUAGE_HINTS.get(str(transcription.get("language_mode", "english")), "")
    if hint:
        parts.append(hint)
    words = vocabulary(40) + [right for _wrong, right in corrections(20)]
    unique = list(dict.fromkeys(words))
    if unique:
        parts.append("Names and terms: " + ", ".join(unique) + ".")
    return " ".join(parts)[:700]


def llm_block() -> str:
    """Vocabulary and corrections as a compact block for the writing model."""
    lines: list[str] = []
    words = vocabulary(60)
    if words:
        lines.append("Vocabulary (spell exactly like this): " + ", ".join(words))
    pairs = corrections(30)
    if pairs:
        lines.append("Often misheard, fix them: " + "; ".join(f"'{w}' means '{r}'" for w, r in pairs))
    return "\n".join(lines)
