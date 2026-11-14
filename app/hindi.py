"""Hindi speech: English stays English, Hindi is written as Hinglish (Roman letters), as spoken."""
from __future__ import annotations

import logging
import re

from . import llm_engine

LOGGER = logging.getLogger("waky")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o"}
_MATRAS = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o"}
_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f",
}
_SIGNS = {"ं": "n", "ँ": "n", "ः": "h", "़": "", "।": ".", "॥": ".", "्": ""}
_DIGITS = {ord("०") + i: str(i) for i in range(10)}


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text or ""))


def _translit_word(word: str) -> str:
    """Rule-based fallback: consonant + vowel marks, with the final 'a' dropped the way Hindi is spoken."""
    out: list[str] = []
    chars = list(word)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if i + 1 < len(chars) and chars[i + 1] == "़" and ch + "़" in _CONS:
            ch, i = ch + "़", i + 1
        if ch in _CONS:
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            out.append(_CONS[ch])
            if nxt in _MATRAS:
                out.append(_MATRAS[nxt])
                i += 1
            elif nxt == "्":
                i += 1
            elif i + 1 < len(chars):   # inner consonant keeps its 'a'; the last one is silent
                out.append("a")
        elif ch in _VOWELS:
            out.append(_VOWELS[ch])
        elif ch in _SIGNS:
            out.append(_SIGNS[ch])
        else:
            out.append(ch.translate(_DIGITS))
        i += 1
    return "".join(out)


def romanize_offline(text: str) -> str:
    return re.sub(r"[ऀ-ॿ]+", lambda m: _translit_word(m.group(0)), text).strip()


PROMPT = (
    "Rewrite the text in Hinglish: Hindi written in Roman letters exactly as it is spoken in everyday chat "
    "(for example 'kal main office jaunga', 'theek hai'). Keep any English words in English. "
    "Do not translate, do not add or remove anything, and keep punctuation. Return only the text."
)


def to_hinglish(text: str, settings: dict | None) -> str:
    """Devanagari to Roman. Uses the Groq model when a key is set, else a rule-based transliteration."""
    if not has_devanagari(text):
        return text
    key = llm_engine.get_api_key(settings)
    if key and not llm_engine.STATUS.rate_limited:
        try:
            model = llm_engine.pick_model(llm_engine.get_model(settings, True), True, llm_engine.available_models(key))
            result = llm_engine.chat(key, model, [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}], temperature=0.0, timeout=12)
            result = llm_engine._strip_wrapping(result)
            if result and not has_devanagari(result):
                return result
        except Exception:
            LOGGER.info("[HINDI] model romanization failed; using offline rules", exc_info=True)
    return romanize_offline(text)
