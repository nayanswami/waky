from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.command_processor import process_text


SETTINGS = {
    "command_processing": {
        "voice_commands_enabled": True,
        "auto_translate_to_english": True,
        "auto_fix_grammar": True,
        "command_rewrite_engine": "rule_based_only",
        "selected_rewrite_ai_mode": "rule_based_only",
        "local_memory_enabled": True,
        "command_write_email_enabled": True,
        "command_bullet_points_enabled": True,
        "command_extend_enabled": True,
        "command_professional_tone_enabled": True,
        "command_casual_tone_enabled": True,
        "command_rewrite_humanizer_enabled": True,
        "command_call_caps_small_enabled": True,
        "command_prompt_mode_enabled": True,
    },
    "providers": {"groq": {"api_key": ""}},
}


def fail(message: str, output: str) -> None:
    raise AssertionError(f"{message}\n\nOutput:\n{output}")


def test_email() -> None:
    output = process_text(
        "write email tell sir I am not feeling well so I cannot attend tomorrow exam please help",
        SETTINGS,
    )
    lowered = output.lower()
    if "subject:" not in lowered:
        fail("Email output is missing Subject.", output)
    if "tell sir" in lowered:
        fail("Email body still contains raw trigger wording.", output)
    if "please help" in lowered:
        fail("Email body copied rough request wording exactly.", output)
    if "tomorrow exam" in lowered:
        fail("Email output still contains messy grammar.", output)
    subject_line = output.splitlines()[0].lower()
    if "tell sir" in subject_line or "i am not feeling" in subject_line:
        fail("Email subject appears copied from raw speech.", output)


def test_professional_command() -> None:
    output = process_text("make it professional I will send you the file tonight", SETTINGS)
    lowered = output.lower()
    if "make it professional" in lowered:
        fail("Professional trigger phrase was not removed.", output)
    if "file" not in lowered:
        fail("Professional rewrite lost the original meaning.", output)
    if "send you" in lowered:
        fail("Professional rewrite did not polish the casual wording.", output)


def test_selected_rewrite_professional() -> None:
    output = process_text(
        "make it professional",
        SETTINGS,
        selected_text="i cant come tomorrow urgent work came",
    )
    lowered = output.lower()
    if "make it professional" in lowered:
        fail("Selected rewrite kept the professional trigger phrase.", output)
    if "tomorrow" not in lowered:
        fail("Selected rewrite lost the timing from the selected text.", output)
    if "urgent" not in lowered:
        fail("Selected rewrite lost the urgent-work context.", output)


def test_professional_email() -> None:
    output = process_text(
        "write email make it professional tell sir I will submit the file tonight",
        SETTINGS,
    )
    lowered = output.lower()
    if "subject:" not in lowered:
        fail("Professional email output is missing Subject.", output)
    if "make it professional" in lowered:
        fail("Professional email kept the command trigger.", output)
    if "file" not in lowered:
        fail("Professional email lost the file-submission context.", output)


def test_bullets() -> None:
    output = process_text(
        "bullet points the rewrite option is not working it only converts commands extend adds generic line email does not understand context",
        SETTINGS,
    )
    lines = [line for line in output.splitlines() if line.strip().startswith("-")]
    if not output.splitlines() or output.splitlines()[0].strip().startswith("-"):
        fail("Bullet output is missing a heading.", output)
    if len(lines) > 6:
        fail("Bullet output created too many bullets for a short input.", output)
    if any(len(line.strip("- ").split()) < 4 for line in lines):
        fail("Bullet output contains fragment bullets.", output)


def test_extend() -> None:
    output = process_text(
        "extend I cannot attend the meeting tomorrow because I have urgent work",
        SETTINGS,
    )
    forbidden = [
        "Please treat this as the current update from my side",
        "I wanted to explain this more clearly",
        "I wanted to share this with a little more clarity",
        "so the message is easy to understand",
        "so the situation is easy to understand",
        "so the next step is clear",
    ]
    for phrase in forbidden:
        if phrase.lower() in output.lower():
            fail(f"Extend output contains forbidden generic filler: {phrase}", output)
    if "urgent work" not in output.lower() and "work commitment" not in output.lower():
        fail("Extend output lost the actual reason/context.", output)


def test_selected_rewrite_with_memory() -> None:
    output = process_text(
        "professional tone and extend",
        SETTINGS,
        selected_text="the rewrite command is not working it just formats text and adds generic lines",
    )
    lowered = output.lower()
    if "generic lines" not in lowered and "generic filler" not in lowered:
        fail("Selected rewrite lost the specific selected-text context.", output)
    if "current update from my side" in lowered:
        fail("Selected rewrite contains forbidden generic filler.", output)


def test_prompt_mode_is_structured() -> None:
    output = process_text("prompt mode make me a tool that cleans my PC safely", SETTINGS)
    lowered = output.lower()
    for section in ("task:", "context:", "requirements:", "expected output:"):
        if section not in lowered:
            fail(f"Prompt mode missing section: {section}", output)


def test_memory_correction() -> None:
    output = process_text("professional tone Gopher API is working", SETTINGS)
    if "Groq" not in output:
        fail("Memory correction did not convert Gopher to Groq.", output)


def test_waky_vocabulary() -> None:
    output = process_text("Waky supports selected text rewrite", SETTINGS)
    if "Waky" not in output:
        fail("Vocabulary did not preserve Waky.", output)


def test_openrouter_vocabulary() -> None:
    output = process_text("open router can be an optional provider", SETTINGS)
    if "OpenRouter" not in output:
        fail("Vocabulary correction did not convert open router to OpenRouter.", output)


def main() -> None:
    test_email()
    test_professional_command()
    test_selected_rewrite_professional()
    test_professional_email()
    test_bullets()
    test_extend()
    test_selected_rewrite_with_memory()
    test_prompt_mode_is_structured()
    test_memory_correction()
    test_waky_vocabulary()
    test_openrouter_vocabulary()
    print("Command rewrite tests passed.")


if __name__ == "__main__":
    main()
