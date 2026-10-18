from __future__ import annotations

import logging
import re

from .cleanup_providers import CleanupContext, LocalBasicProvider, provider_from_settings
from .utils import normalize_spaces


COMMAND_TO_MODE = {
    "make it better": "clean_casual",
    "make it professional": "professional",
    "make it casual": "whatsapp",
    "make it shorter": "whatsapp",
    "make it detailed": "professional",
    "convert to bullet points": "bullet_points",
    "fix grammar": "clean_casual",
    "write as email": "email",
    "write as whatsapp message": "whatsapp",
    "write as chatgpt prompt": "prompt",
    "write as codex prompt": "prompt",
    "translate to english": "translate_english",
}


class TextProcessor:
    def __init__(self, config_manager, logger: logging.Logger) -> None:
        self.config_manager = config_manager
        self.logger = logger
        self.local_provider = LocalBasicProvider()

    def process(self, transcript: str, selected_mode: str | None = None) -> str:
        text = normalize_spaces(transcript)
        if not text:
            return ""
        mode = selected_mode or self.config_manager.get("output.default_mode", "clean_casual")
        command_mode, cleaned = self._extract_voice_command(text)
        if command_mode:
            mode = command_mode
            text = cleaned
        text = self._apply_vocabulary(text)
        text = self._apply_snippets(text)

        provider = provider_from_settings(self.config_manager.settings)
        context = CleanupContext(mode=mode, language_mode=self.config_manager.get("transcription.language_mode", "auto"))
        try:
            processed = provider.cleanup(text, context)
        except Exception as exc:
            self.logger.warning("Cleanup provider failed, falling back to local_basic: %s", exc)
            processed = self.local_provider.cleanup(text, context)
        return self._apply_snippets(self._apply_vocabulary(processed))

    def _extract_voice_command(self, text: str) -> tuple[str | None, str]:
        lowered = text.lower().strip(" .,!?")
        for phrase, mode in COMMAND_TO_MODE.items():
            if lowered.startswith(phrase):
                return mode, normalize_spaces(text[len(phrase):].strip(" ,.-"))
            if lowered.endswith(phrase):
                return mode, normalize_spaces(text[: -len(phrase)].strip(" ,.-"))
        return None, text

    def _apply_vocabulary(self, text: str) -> str:
        replacements = self.config_manager.vocabulary.get("replacements", {})
        for source, target in replacements.items():
            text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
        return text

    def _apply_snippets(self, text: str) -> str:
        snippets_config = self.config_manager.snippets
        if not snippets_config.get("enabled", True):
            return text
        for snippet in snippets_config.get("snippets", []):
            if not snippet.get("enabled", True):
                continue
            trigger = snippet.get("trigger", "")
            value = snippet.get("value", "")
            if trigger and value:
                text = re.sub(rf"\b{re.escape(trigger)}\b", value, text, flags=re.IGNORECASE)
        return text
