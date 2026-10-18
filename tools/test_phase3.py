"""Offline checks: keyring migration and Groq 429 -> local fallback (no network, no real model)."""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app import llm_engine, secret_store
from app.config_manager import ConfigManager
from app.transcriber import FasterWhisperTranscriber, GroqRateLimited, TranscriptionResult

# --- keys leave settings.json and live in the credential store (fake in-memory store)
store: dict[str, str] = {}
with mock.patch.object(secret_store, "get", lambda n: store.get(n, "")), mock.patch.object(
    secret_store, "set", lambda n, v: (store.__setitem__(n, v) if v else store.pop(n, None)) or True
):
    d = Path(tempfile.mkdtemp())
    (d / "settings.json").write_text(json.dumps({"providers": {"groq": {"api_key": "gsk_test123"}}}))
    cfg = ConfigManager(d)
    assert cfg.settings["providers"]["groq"]["api_key"] == "gsk_test123", "runtime keeps the key"
    assert store["groq"] == "gsk_test123"
    assert "gsk_test123" not in (d / "settings.json").read_text(), "key must not be on disk"
    cfg2 = ConfigManager(d)
    assert cfg2.settings["providers"]["groq"]["api_key"] == "gsk_test123", "key reloads from store"

# --- 429 -> cooldown -> local fallback, then skip Groq while cooling down
settings = {"providers": {"groq": {"api_key": "k"}}, "transcription": {"backend": "auto_fallback", "model": "base"}}
tr = FasterWhisperTranscriber(settings, logging.getLogger("t"))
notices: list[str] = []
tr.on_notice = notices.append
audio = np.zeros(16000, dtype="float32")
local = TranscriptionResult("local text", "en", "CPU", "base")
calls = {"groq": 0}


def groq_429(*a, **k):
    calls["groq"] += 1
    llm_engine.STT_STATUS.cooldown_until = time.time() + 30
    raise GroqRateLimited(30)


with mock.patch.object(tr, "_transcribe_groq", groq_429), mock.patch.object(tr, "_transcribe_local", lambda *a, **k: local), mock.patch.object(
    tr, "_require_local_model", lambda: None
):
    assert tr.transcribe(audio, 16000, "j1").text == "local text"
    assert tr.transcribe(audio, 16000, "j2").text == "local text"
assert calls["groq"] == 1, "second call must skip Groq during cooldown"
assert len(notices) == 2 and "local Whisper" in notices[0], notices

# --- missing local model fails fast with an actionable message
llm_engine.STT_STATUS.cooldown_until = 0
tr2 = FasterWhisperTranscriber(settings, logging.getLogger("t"))
with mock.patch.object(tr2, "faster_whisper_installed", lambda: True), mock.patch("app.model_manager.is_downloaded", lambda m: False):
    try:
        tr2._require_local_model()
        raise SystemExit("expected RuntimeError")
    except RuntimeError as exc:
        assert "Download local model" in str(exc)
print("phase 3 checks passed")
