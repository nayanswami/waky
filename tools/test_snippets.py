from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["WAKY_DATA_DIR"] = tempfile.mkdtemp()   # never touch the real AppData memory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.command_processor import process_text
from app.local_memory import MEMORY_DIR


SETTINGS = {
    "command_processing": {
        "voice_commands_enabled": True,
        "auto_translate_to_english": True,
        "auto_fix_grammar": True,
        "command_rewrite_engine": "rule_based_only",
        "local_memory_enabled": True,
    },
    "providers": {"groq": {"api_key": ""}},
}


def main() -> None:
    snippets_path = MEMORY_DIR / "snippets.json"
    old_content = snippets_path.read_text(encoding="utf-8") if snippets_path.exists() else None
    test_snippets = {
        "enabled": True,
        "snippets": [
            {
                "name": "linkedin",
                "triggers": ["my linkedin", "linkedin profile", "paste my linkedin"],
                "value": "https://linkedin.com/in/example",
                "enabled": True,
            }
        ],
    }
    try:
        snippets_path.parent.mkdir(parents=True, exist_ok=True)
        snippets_path.write_text(json.dumps(test_snippets, indent=2), encoding="utf-8")
        output = process_text("my linkedin", SETTINGS)
        if output != "https://linkedin.com/in/example":
            raise AssertionError(f"Snippet did not return exact value.\n\nOutput:\n{output}")
        phone_snippets = {
            "enabled": True,
            "snippets": [
                {
                    "name": "phone",
                    "triggers": ["my phone number", "paste my phone number"],
                    "value": "+91 79743 70328",
                    "enabled": True,
                }
            ],
        }
        snippets_path.write_text(json.dumps(phone_snippets, indent=2), encoding="utf-8")
        output = process_text("You can contact me on my phone number.", SETTINGS)
        expected = "You can contact me on +91 79743 70328"
        if output != expected:
            raise AssertionError(f"Snippet did not expand inside sentence.\nExpected: {expected}\nOutput: {output}")
        print("Snippet tests passed.")
    finally:
        if old_content is None:
            snippets_path.unlink(missing_ok=True)
        else:
            snippets_path.write_text(old_content, encoding="utf-8")


if __name__ == "__main__":
    main()
