from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["WAKY_DATA_DIR"] = tempfile.mkdtemp()   # never touch the real AppData memory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_memory import (
    add_correction,
    add_memory_note,
    add_vocabulary_item,
    ensure_project,
    get_rewrite_context,
    load_memory,
    set_active_project,
)


def main() -> None:
    memory = load_memory()
    assert "custom_vocabulary" in memory

    ensure_project("Waky")
    set_active_project("Waky")
    add_correction("Gopher", "Groq", "test correction", "Waky")
    add_vocabulary_item("Wispr Flow", "dictation app reference", "Waky")
    add_memory_note("Waky is my Windows dictation tool project", "Waky")

    context = get_rewrite_context("Waky")
    lowered = context.lower()
    assert "gopher -> groq" in lowered
    assert "wispr flow" in lowered
    assert "windows dictation tool project" in lowered
    print("Memory tests passed.")


if __name__ == "__main__":
    main()
