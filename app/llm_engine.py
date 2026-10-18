from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("waky")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
# Groq sits behind Cloudflare, which rejects the default "Python-urllib" agent with HTTP 403.
USER_AGENT = "Waky/1.0"

SYSTEM_PROMPT = """You are the writing engine inside Waky, a desktop dictation app. The user speaks; you turn the speech into the exact text they would have written if they had typed it carefully.

You receive: the raw transcript, optionally selected text to be rewritten, the modes the user asked for (with their instructions and output formats), the user's standing preferences, and local memory.

How to work:
1. Understand the intent first: who the text is for, what it is (email, note, update, request, prompt, post, list), and which details matter.
2. Spoken instructions may be mixed into the transcript, for example "convert this into a mail", "make it bullet points", "write a blog about this". Treat such phrases as instructions, never as content, and follow them. Modes listed under "Requested modes" are authoritative; apply all of them together.
3. If selected text is provided, the transcript is the instruction for it: transform the selected text accordingly and output the replacement text.
4. If no mode or instruction is present, produce clean dictation: fix grammar, remove filler and false starts, keep the speaker's meaning and voice.
5. Rewrite from meaning, not word by word. A mode like blog, email or summary may restructure and reword everything, and may expand a short idea into a full piece, but never invent facts, names, dates, numbers or attachments.
6. Translate Hindi, Hinglish or mixed speech into natural English unless the user's preferences say otherwise.
7. Honour the user's vocabulary spellings and forbidden phrases from memory.

Output rules:
- Return only the final text, ready to paste. No preface, no explanation, no surrounding quotes, no markdown fences unless a mode asks for them.
- Follow a mode's output format exactly when one is given."""


class LLMError(RuntimeError):
    """Rewrite request failed; caller should fall back to the rule-based engine."""


class LLMRateLimited(LLMError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


@dataclass
class ModeInstruction:
    key: str
    instruction: str = ""
    output_format: str = ""


@dataclass
class RewriteRequest:
    transcript: str
    selected_text: str = ""
    modes: Sequence[ModeInstruction] = field(default_factory=tuple)
    custom_instructions: str = ""
    memory_context: str = ""
    auto_translate: bool = True


@dataclass
class EngineStatus:
    cooldown_until: float = 0.0
    last_error: str = ""
    last_ok: float = 0.0

    @property
    def rate_limited(self) -> bool:
        return time.time() < self.cooldown_until


STATUS = EngineStatus()
STT_STATUS = EngineStatus()  # Groq speech-to-text has its own rate limit


def get_api_key(settings: dict | None) -> str:
    if isinstance(settings, dict):
        providers = settings.get("providers", {})
        if isinstance(providers, dict):
            key = str(providers.get("groq", {}).get("api_key", "")).strip()
            if key:
                return key
    return os.environ.get("GROQ_API_KEY", "").strip()


def get_model(settings: dict | None) -> str:
    if isinstance(settings, dict):
        commands = settings.get("command_processing", {})
        if isinstance(commands, dict):
            model = str(commands.get("groq_text_model", "")).strip()
            if model:
                return model
    return DEFAULT_MODEL


def build_user_prompt(req: RewriteRequest) -> str:
    parts: list[str] = []
    if req.modes:
        lines = []
        for mode in req.modes:
            line = f"- {mode.key}: {mode.instruction or 'apply this mode sensibly'}"
            if mode.output_format:
                line += f"\n  Output format: {mode.output_format}"
            lines.append(line)
        parts.append("Requested modes:\n" + "\n".join(lines))
    else:
        parts.append("Requested modes:\nnone detected (check the transcript for spoken instructions)")
    if req.custom_instructions.strip():
        parts.append("User's standing preferences:\n" + req.custom_instructions.strip())
    if req.memory_context.strip():
        parts.append("Local memory:\n" + req.memory_context.strip())
    if not req.auto_translate:
        parts.append("Do not translate; keep the language the user spoke.")
    if req.selected_text.strip():
        parts.append("Selected text to rewrite:\n" + req.selected_text.strip())
        parts.append("Spoken instruction:\n" + req.transcript.strip())
    else:
        parts.append("Transcript:\n" + req.transcript.strip())
    parts.append("Return only the final text.")
    return "\n\n".join(parts)


def _strip_wrapping(text: str) -> str:
    result = text.strip()
    if len(result) >= 2 and result[0] == result[-1] and result[0] in "\"'":
        result = result[1:-1].strip()
    if result.startswith("```") and result.endswith("```"):
        inner = result.strip("`").split("\n", 1)
        result = inner[1].strip() if len(inner) == 2 else inner[0].strip()
    return result


def chat(api_key: str, model: str, messages: list[dict[str, str]], temperature: float = 0.3, timeout: float = 20) -> str:
    """One Groq chat completion. Raises LLMRateLimited on 429, LLMError otherwise."""
    payload = {"model": model, "temperature": temperature, "messages": messages}
    last_exc: Exception | None = None
    for attempt in range(2):
        request = Request(
            GROQ_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            STATUS.last_ok = time.time()
            STATUS.last_error = ""
            return text
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if exc.code == 429:
                try:
                    retry_after = float(exc.headers.get("retry-after", "60"))
                except (TypeError, ValueError):
                    retry_after = 60.0
                STATUS.cooldown_until = time.time() + retry_after
                STATUS.last_error = "rate limited"
                raise LLMRateLimited(retry_after) from exc
            STATUS.last_error = f"HTTP {exc.code}"
            if exc.code in (401, 403):
                raise LLMError(f"Groq rejected the request (HTTP {exc.code}). Check your API key. {body}") from exc
            last_exc = exc
            if exc.code < 500:
                break
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            STATUS.last_error = str(exc)
            last_exc = exc
        time.sleep(0.4)
    raise LLMError(f"Groq request failed: {last_exc}") from last_exc


def rewrite(req: RewriteRequest, settings: dict | None) -> str:
    """Run the LLM rewrite. Returns final text; raises LLMError / LLMRateLimited."""
    api_key = get_api_key(settings)
    if not api_key:
        raise LLMError("no Groq API key configured")
    if STATUS.rate_limited:
        raise LLMRateLimited(STATUS.cooldown_until - time.time())
    options = (settings or {}).get("command_processing", {}) if isinstance(settings, dict) else {}
    model = get_model(settings)
    LOGGER.info("[LLM] model=%s modes=%s selected=%s", model, [m.key for m in req.modes], bool(req.selected_text))
    text = chat(
        api_key,
        model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(req)},
        ],
        temperature=float(options.get("llm_temperature", 0.3) or 0.3),
    )
    result = _strip_wrapping(text)
    if not result:
        raise LLMError("empty response from model")
    return result


def verify_key(api_key: str, timeout: float = 10) -> tuple[bool, str]:
    """Cheap check that a Groq key is accepted (lists models; does not use quota)."""
    request = Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key.strip()}", "User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=timeout):
            return True, "Key works."
    except HTTPError as exc:
        if exc.code in (401, 403):
            return False, "Groq rejected this key. Copy it again from console.groq.com/keys."
        return False, f"Groq returned HTTP {exc.code}."
    except (URLError, TimeoutError, OSError) as exc:
        return False, f"Could not reach Groq (check your internet): {exc}"
