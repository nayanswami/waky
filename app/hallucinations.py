"""Whisper invents text for silence and breath: most often "Thank you." Drop it before it reaches the page."""
from __future__ import annotations

import re

import numpy as np

PHANTOMS = (
    "thank you", "thank you very much", "thank you so much", "thanks", "thanks a lot", "thank you for watching",
    "thanks for watching", "thank you for listening", "thanks for listening", "thank you all", "thank you everyone",
    "please subscribe", "like and subscribe", "subscribe to my channel", "see you next time", "see you in the next video",
    "bye", "bye bye", "goodbye", "you", "okay", "ok", "so", "um", "uh", "hmm", "mm", "mhm", "amara org",
    "subtitles by the amara org community", "transcribed by", "dhanyavad", "shukriya",
)
_PHANTOM_SET = frozenset(PHANTOMS)
_TAIL = re.compile(r"(?is)[\s,.!?;:-]*\b(?:thank you(?: very much| so much| all| everyone)?|thanks(?: a lot)?|thank you for (?:watching|listening)|thanks for (?:watching|listening))[\s.!?]*$")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def is_phantom(text: str, prompt: str = "") -> bool:
    """True when the whole transcript is one of Whisper's silence phrases, or an echo of the hint prompt."""
    cleaned = _norm(text)
    if not cleaned:
        return True
    if cleaned in _PHANTOM_SET:
        return True
    if prompt and len(cleaned) > 3 and cleaned in _norm(prompt):
        return True
    return False


def tail_is_quiet(audio: np.ndarray, sample_rate: int, seconds: float = 1.0, threshold: float = 0.012) -> bool:
    """The last second of the clip is quiet: a spoken "thank you" would be loud there."""
    if audio is None or not getattr(audio, "size", 0) or not sample_rate:
        return True
    tail = audio[-int(sample_rate * seconds):].astype(np.float32)
    if tail.dtype.kind in "iu":
        tail = tail / 32768.0
    return float(np.sqrt(np.mean(np.square(tail)))) < threshold


def strip_trailing_phantom(text: str, audio: np.ndarray | None = None, sample_rate: int = 16000) -> str:
    """Remove a trailing 'Thank you.' that Whisper adds after real speech, when the audio does not end in speech."""
    match = _TAIL.search(text)
    if not match or match.start() == 0:
        return text
    if audio is not None and not tail_is_quiet(audio, sample_rate, 0.8, 0.02):
        return text   # the user really said it
    return text[: match.start()].rstrip(" ,;:-")


def clean(text: str, audio: np.ndarray | None, sample_rate: int, prompt: str = "") -> str:
    """Returns "" when the transcript is only a phantom phrase, else the text without a phantom ending."""
    text = (text or "").strip()
    if is_phantom(text, prompt):
        return ""
    result = strip_trailing_phantom(text, audio, sample_rate).strip()
    if result and result != text and result[-1] not in ".!?":
        result += "."
    return "" if is_phantom(result, prompt) else result
