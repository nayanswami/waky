"""Offline checks for the LLM-first rewrite path (Groq call is mocked)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm_engine
import copy

from app.command_processor import process_text
from app.config_manager import DEFAULT_CUSTOM_COMMANDS

SETTINGS = {
    "providers": {"groq": {"api_key": "test-key"}},
    "command_processing": {"local_memory_enabled": False, "custom_instructions": "Sign off as Nayan."},
}
CUSTOM = copy.deepcopy(DEFAULT_CUSTOM_COMMANDS)
CUSTOM["commands"].append({"command_id": "blog", "triggers": ["write a blog", "blog mode"], "instruction": "Write a short blog post with a title.", "output_format": "# Title\n\nParagraphs"})

seen = {}


def fake_chat(api_key, model, messages, temperature=0.3, timeout=20):
    seen["system"], seen["user"] = messages[0]["content"], messages[1]["content"]
    return '"Final output"'


llm_engine.chat = fake_chat
out = process_text("um can you tell sir I will be late write email professional tone", SETTINGS, custom_commands=CUSTOM)
assert out.startswith("Final output"), out
assert "write_email" in seen["user"] and "professional_tone" in seen["user"], seen["user"]
assert "Sign off as Nayan." in seen["user"]
assert "write email" not in seen["user"].split("Transcript:")[1].lower(), "command words must be stripped"

out = process_text("blog mode my trip to Khajuraho was great", SETTINGS, custom_commands=CUSTOM)
assert "blog: Write a short blog post with a title." in seen["user"] and "Output format: # Title" in seen["user"], seen["user"]

selected = process_text("make it bullet points", SETTINGS, selected_text="I am sick so I cannot come.", custom_commands=CUSTOM)
assert "Selected text to rewrite:\nI am sick" in seen["user"]


def limited(*a, **k):
    raise llm_engine.LLMRateLimited(30)


llm_engine.chat = limited
fallback = process_text("write email I am sick", SETTINGS, custom_commands=CUSTOM)
assert fallback and fallback != "Final output", fallback
print("all LLM engine checks passed; fallback sample:", repr(fallback[:60]))
