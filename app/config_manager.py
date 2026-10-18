from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from . import secret_store
from .utils import CONFIG_DIR


DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {
        "launch_on_startup": False,
        "start_minimized": False,
        "start_hidden_no_terminal": True,
        "show_floating_bar_on_startup": True,
        "sound_effects": False,
        "always_on_top": True,
        "theme": "black_white_minimal",
        "paused": False,
        "onboarding_done": False,
        "appearance": "light",
    },
    "floating_bar": {
        "x": None,
        "y": None,
        "position": {"x": None, "y": None},
        "remember_position": True,
        "style": "island",
        "accent": "#2E62FF",
        "size": 100,
        "position_mode": "preset",
        "anchor": "bottom_center",
        "margin": 40,
        "alt_drag_only": True,
        "visible": True,
        "hidden": False,
    },
    "hotkeys": {
        "push_to_talk": "<ctrl>+<win>",
        "push_to_talk_backup": "<f8>",
        "toggle_recording": "<f9>",
        "cancel": "<esc>",
        "alternatives": ["<ctrl>+<cmd>", "<ctrl>+<shift>+<space>"],
    },
    "audio": {
        "microphone": None,
        "sample_rate": 16000,
        "channels": 1,
        "silence_trimming": True,
        "min_record_seconds": 0.25,
        "keep_ready": True,
        "tail_ms": 350,
    },
    "transcription": {
        "backend": "auto_fallback",
        "groq_model": "whisper-large-v3-turbo",
        "model": "base",
        "language_mode": "english",
        "speed_mode": "balanced",
        "engine_mode": "auto",
        "safe_mode_implementation": "in_process_cpu",
        "device_preference": "cpu",
        "compute_type_gpu": "float16",
        "compute_type_cpu": "int8",
    },
    "output": {
        "default_mode": "clean_casual",
        "auto_paste": True,
        "preserve_clipboard": True,
        "never_press_enter": True,
    },
    "command_processing": {
        "voice_commands_enabled": True,
        "auto_translate_to_english": True,
        "auto_fix_grammar": True,
        "command_rewrite_engine": "cloud_if_available",
        "groq_text_model": "llama-3.3-70b-versatile",
        "groq_fast_model": "llama-3.1-8b-instant",
        "custom_instructions": "",
        "llm_temperature": 0.3,
        "local_memory_enabled": True,
        "memory_auto_save_useful_vocabulary": True,
        "memory_save_full_transcripts": False,
        "memory_save_transcript_summaries": True,
        "memory_save_command_outputs": True,
        "memory_save_selected_rewrite_examples": False,
        "memory_save_manual_remember_commands": True,
        "memory_auto_detect_corrections": True,
        "memory_use_cloud_for_summarization": True,
        "memory_cloud_summary_provider": "auto",
        "memory_use_current_project_context": True,
        "memory_use_writing_preferences": True,
        "memory_use_custom_vocabulary": True,
        "memory_sensitive_storage_mode": "local_allowed",
        "memory_active_project": "general",
        "store_full_transcripts_for_learning": False,
        "store_selected_text_history": False,
        "store_rewrite_examples": False,
        "save_only_manual_corrections": True,
        "smart_selected_rewrite_enabled": True,
        "selected_rewrite_ai_mode": "auto",
        "preserve_clipboard_after_selected_rewrite": True,
        "selected_capture_timeout_ms": 250,
        "selected_text_rewrite_enabled": False,
        "capture_selected_text_before_recording": True,
        "replace_selected_text_automatically": True,
        "selected_text_preserve_clipboard": True,
        "command_prompt_mode_enabled": True,
        "command_bullet_points_enabled": True,
        "command_rewrite_humanizer_enabled": True,
        "command_call_caps_small_enabled": True,
        "command_professional_tone_enabled": True,
        "command_casual_tone_enabled": True,
        "command_write_email_enabled": True,
        "command_extend_enabled": True,
    },
    "privacy": {
        "save_recordings": False,
        "cloud_cleanup": False,
        "provider": "local_basic",
        "logs_level": "warning",
        "include_transcript_in_logs": False,
    },
    "providers": {
        "groq": {"enabled": False, "api_key": ""},
        "openai": {"enabled": False, "api_key": ""},
        "openrouter": {"enabled": False, "api_key": ""},
        "gemini": {"enabled": False, "api_key": ""},
    },
}

DEFAULT_VOCABULARY = {
    "words": [
        "Waky",
        "Groq",
        "OpenAI",
        "OpenRouter",
        "ChatGPT",
        "Codex",
        "Notion",
        "Gmail",
        "WhatsApp",
        "Wispr Flow",
        "WhisperFlow",
        "selected text rewrite",
        "floating bar",
        "command processor",
        "UX Design",
        "UI Design",
    ],
    "replacements": {
        "chat gpt": "ChatGPT",
        "charge gpt": "ChatGPT",
        "code x": "Codex",
        "what's app": "WhatsApp",
        "waki": "Waky",
        "wakey": "Waky",
        "whacky": "Waky",
        "groq": "Groq",
        "open router": "OpenRouter",
        "wispr flow": "Wispr Flow",
        "whisper flow": "WhisperFlow",
        "ux design": "UX Design",
        "ui design": "UI Design",
    },
}

DEFAULT_SNIPPETS = {
    "enabled": True,
    "snippets": [
        {"trigger": "my linkedin", "value": "", "enabled": True, "triggers": ["my linkedin", "linkedin profile", "paste my linkedin"], "name": "linkedin"},
        {"trigger": "my email", "value": "", "enabled": True, "triggers": ["my email", "email address", "paste my email"], "name": "email"},
        {"trigger": "my LinkedIn", "value": "https://www.linkedin.com/in/your-profile", "enabled": False},
        {"trigger": "my email", "value": "your.email@example.com", "enabled": False},
        {"trigger": "my portfolio", "value": "https://your-portfolio.example.com", "enabled": False},
        {"trigger": "my phone number", "value": "+91-0000000000", "enabled": False},
    ],
}

DEFAULT_CUSTOM_COMMANDS = {
    "commands": [
        {
            "command_id": "write_email",
            "display_name": "Write Email",
            "enabled": True,
            "triggers": ["write email", "write an email", "email mode", "make email", "draft email"],
            "instruction": "Rewrite the input as a polite email. Fix grammar, improve clarity, and do not invent details.",
            "output_format": "Subject: <short subject>\\n\\nHi <recipient>,\\n\\n<body>\\n\\nRegards,",
            "priority": 1,
            "built_in": True,
        },
        {
            "command_id": "prompt_mode",
            "display_name": "Prompt Mode",
            "enabled": True,
            "triggers": ["prompt mode", "make this prompt", "convert into prompt", "turn this into prompt", "ai prompt"],
            "instruction": "Convert the input into a complete, structured AI prompt with task, context, requirements, and expected output.",
            "output_format": "Task:\\n...\\n\\nContext:\\n...\\n\\nRequirements:\\n- ...\\n\\nExpected Output:\\n...",
            "priority": 2,
            "built_in": True,
        },
        {
            "command_id": "bullet_points",
            "display_name": "Bullet Points",
            "enabled": True,
            "triggers": ["bullet points", "bullet point", "make bullet points", "convert into bullet points", "turn this into points"],
            "instruction": "Rewrite the input into clear bullet points with one short heading.",
            "output_format": "<Short Heading>\\n\\n- Point 1\\n- Point 2\\n- Point 3",
            "priority": 3,
            "built_in": True,
        },
        {
            "command_id": "rewrite_humanizer",
            "display_name": "Rewrite & Humanizer",
            "enabled": True,
            "triggers": ["rewrite and humanizer", "rewrite and humanize", "humanizer", "humanize this", "rewrite this", "rewrite"],
            "instruction": "Rewrite the input so it sounds natural, human, clear, and polished while preserving meaning.",
            "output_format": "",
            "priority": 4,
            "built_in": True,
        },
        {
            "command_id": "extend",
            "display_name": "Extend",
            "enabled": True,
            "triggers": ["extend this", "expand this", "make it longer", "elaborate", "extend"],
            "instruction": "Expand the input with more clarity and useful detail without inventing facts.",
            "output_format": "",
            "priority": 5,
            "built_in": True,
        },
        {
            "command_id": "professional_tone",
            "display_name": "Professional Tone",
            "enabled": True,
            "triggers": [
                "professional tone",
                "make professional",
                "make it professional",
                "make this professional",
                "professionally",
                "formal tone",
                "make this formal",
                "make it formal",
                "professional",
                "convert to professional tone"
            ],
            "instruction": "Rewrite the input in a concise, professional, polished tone.",
            "output_format": "",
            "priority": 6,
            "built_in": True,
        },
        {
            "command_id": "casual_tone",
            "display_name": "Casual Tone",
            "enabled": True,
            "triggers": ["casual tone", "make casual", "casually", "friendly tone"],
            "instruction": "Rewrite the input in a casual, natural, friendly tone without emojis.",
            "output_format": "",
            "priority": 7,
            "built_in": True,
        },
        {
            "command_id": "call_caps_small",
            "display_name": "Call Caps Small",
            "enabled": True,
            "triggers": ["call caps small", "all caps small", "caps small", "lowercase", "small letters"],
            "instruction": "Convert the final output to lowercase while preserving URLs, emails, and code as much as possible.",
            "output_format": "",
            "priority": 10,
            "built_in": True,
        },
    ]
}


class ConfigManager:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.settings_path = config_dir / "settings.json"
        self.vocabulary_path = config_dir / "vocabulary.json"
        self.snippets_path = config_dir / "snippets.json"
        self.custom_commands_path = config_dir / "commands.json"
        self.legacy_custom_commands_path = config_dir / "custom_commands.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = self._load_json(self.settings_path, DEFAULT_SETTINGS)
        self.vocabulary = self._load_json(self.vocabulary_path, DEFAULT_VOCABULARY)
        self.snippets = self._load_json(self.snippets_path, DEFAULT_SNIPPETS)
        if not self.custom_commands_path.exists() and self.legacy_custom_commands_path.exists():
            self.custom_commands = self._load_json(self.legacy_custom_commands_path, DEFAULT_CUSTOM_COMMANDS)
        else:
            self.custom_commands = self._load_json(self.custom_commands_path, DEFAULT_CUSTOM_COMMANDS)
        self._repair_hotkey_conflicts()
        self._load_secrets()
        self.save_all()

    def _load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return copy.deepcopy(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self._deep_merge(copy.deepcopy(default), data)
        except Exception:
            corrupt = path.with_suffix(path.suffix + ".corrupt")
            try:
                shutil.copy2(path, corrupt)
            except Exception:
                pass
            return copy.deepcopy(default)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _repair_hotkey_conflicts(self) -> None:
        hotkeys = self.settings.setdefault("hotkeys", {})
        commands = self.settings.setdefault("command_processing", {})
        had_selected_rewrite = "selected_text_rewrite" in hotkeys or commands.get("selected_text_rewrite_enabled", False)
        if had_selected_rewrite or not hotkeys.get("push_to_talk"):
            hotkeys["push_to_talk"] = "<ctrl>+<win>"
        hotkeys.setdefault("push_to_talk_backup", "<f8>")
        hotkeys.pop("selected_text_rewrite", None)
        commands["selected_text_rewrite_enabled"] = False

    def save_all(self) -> None:
        self.save_settings()
        self.save_vocabulary()
        self.save_snippets()
        self.save_custom_commands()

    def _load_secrets(self) -> None:
        """Move provider API keys out of settings.json into Windows Credential Manager."""
        for name, entry in self.settings.get("providers", {}).items():
            if not isinstance(entry, dict):
                continue
            file_key = str(entry.get("api_key", "")).strip()
            stored = secret_store.get(name)
            if file_key and file_key != stored:
                secret_store.set(name, file_key)
            entry["api_key"] = file_key or stored

    def save_settings(self) -> None:
        data = copy.deepcopy(self.settings)
        for name, entry in data.get("providers", {}).items():
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("api_key", "")).strip()
            if secret_store.set(name, key):
                entry["api_key"] = ""  # keep the key only in the credential store
        self._write_json(self.settings_path, data)

    def save_vocabulary(self) -> None:
        self._write_json(self.vocabulary_path, self.vocabulary)

    def save_snippets(self) -> None:
        self._write_json(self.snippets_path, self.snippets)

    def save_custom_commands(self) -> None:
        self._write_json(self.custom_commands_path, self.custom_commands)

    def reload_custom_commands(self) -> None:
        self.custom_commands = self._load_json(self.custom_commands_path, DEFAULT_CUSTOM_COMMANDS)

    def reset_custom_commands(self) -> None:
        self.custom_commands = copy.deepcopy(DEFAULT_CUSTOM_COMMANDS)
        self.save_custom_commands()

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(path)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        current: Any = self.settings
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def set(self, dotted_key: str, value: Any) -> None:
        current: dict[str, Any] = self.settings
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
        self.save_settings()
