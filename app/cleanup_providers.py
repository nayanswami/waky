from __future__ import annotations

from dataclasses import dataclass

from .utils import ensure_terminal_punctuation, normalize_spaces, sentence_case


@dataclass
class CleanupContext:
    mode: str
    language_mode: str


class CleanupProvider:
    name = "base"

    def cleanup(self, text: str, context: CleanupContext) -> str:
        raise NotImplementedError


class LocalBasicProvider(CleanupProvider):
    name = "local_basic"

    def cleanup(self, text: str, context: CleanupContext) -> str:
        text = normalize_spaces(text)
        if not text:
            return ""
        if context.mode == "raw":
            return text
        if context.mode == "bullet_points":
            return self._bullets(text)
        if context.mode == "prompt":
            return self._prompt(text)
        if context.mode == "professional":
            return self._professional(text)
        if context.mode == "email":
            return self._email(text)
        if context.mode == "whatsapp":
            return self._whatsapp(text)
        if context.mode == "translate_english":
            return self._translate_basic(text)
        return ensure_terminal_punctuation(sentence_case(text))

    def _professional(self, text: str) -> str:
        replacements = {
            "pls": "please",
            "plz": "please",
            "u ": "you ",
            "ur ": "your ",
            "asap": "as soon as possible",
            " i ": " I ",
        }
        lower = f" {text.lower()} "
        for source, target in replacements.items():
            if source.startswith(" ") or source.endswith(" "):
                lower = lower.replace(source, target)
            else:
                lower = lower.replace(f" {source}", f" {target}")
        cleaned = lower.strip()
        cleaned = cleaned.replace("i completed", "I've completed")
        cleaned = cleaned.replace("I completed", "I've completed")
        cleaned = cleaned.replace("i will", "I will")
        return ensure_terminal_punctuation(sentence_case(cleaned))

    def _email(self, text: str) -> str:
        lowered = text.lower().strip()
        recipient = ""
        if lowered.startswith("tell sir "):
            recipient = "Sir"
            text = text[9:].strip()
        elif lowered.startswith("sir "):
            recipient = "Sir"
            text = text[4:].strip()
        body = self._professional(text)
        if body.lower().startswith(("hi ", "hello ", "dear ")):
            return body
        greeting = f"Hi {recipient}," if recipient else "Hi,"
        return f"{greeting}\n\n{body}\n\nRegards,"

    def _whatsapp(self, text: str) -> str:
        text = sentence_case(text)
        return text.rstrip(".")

    def _bullets(self, text: str) -> str:
        parts = [p.strip(" .") for p in text.replace(" and ", ". ").split(".") if p.strip()]
        if len(parts) <= 1:
            parts = [p.strip(" ,") for p in text.split(",") if p.strip()]
        return "\n".join(f"- {sentence_case(part)}" for part in parts if part)

    def _prompt(self, text: str) -> str:
        text = sentence_case(text)
        return (
            "Task:\n"
            f"{text}\n\n"
            "Context:\n"
            "- Use the details provided above.\n\n"
            "Requirements:\n"
            "- Be clear, practical, and complete.\n"
            "- Ask only if a required detail is missing.\n\n"
            "Expected output:\n"
            "- Provide the final answer or implementation steps."
        )

    def _translate_basic(self, text: str) -> str:
        phrase_map = {
            "mujhe": "I need",
            "kar do": "please do it",
            "bhej do": "please send it",
            "aaj": "today",
            "kal": "tomorrow",
            "sir ko": "to sir",
            "complete ho gaya": "is complete",
            "main bhej dunga": "I will send it",
        }
        cleaned = text.lower()
        for source, target in phrase_map.items():
            cleaned = cleaned.replace(source, target)
        return ensure_terminal_punctuation(sentence_case(cleaned))


class PlaceholderCloudProvider(CleanupProvider):
    def __init__(self, name: str, api_key: str = "", enabled: bool = False) -> None:
        self.name = name
        self.api_key = api_key
        self.enabled = enabled

    def cleanup(self, text: str, context: CleanupContext) -> str:
        # TODO: Send transcript text only, never audio, after explicit user opt-in.
        if not self.enabled or not self.api_key:
            raise RuntimeError(f"{self.name} cleanup is not configured. Cloud cleanup is off by default.")
        raise NotImplementedError(f"{self.name} cleanup placeholder is not implemented in Phase 1.")


def provider_from_settings(settings: dict) -> CleanupProvider:
    privacy = settings.get("privacy", {})
    providers = settings.get("providers", {})
    selected = privacy.get("provider", "local_basic")
    if not privacy.get("cloud_cleanup", False) or selected == "local_basic":
        return LocalBasicProvider()
    provider_settings = providers.get(selected, {})
    return PlaceholderCloudProvider(selected, provider_settings.get("api_key", ""), provider_settings.get("enabled", False))
