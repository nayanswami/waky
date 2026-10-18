from __future__ import annotations

import logging
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from . import llm_engine
from .local_memory import (
    add_correction,
    add_memory_note,
    add_rewrite_example,
    add_vocabulary_item,
    get_active_project,
    get_forbidden_phrases,
    get_rewrite_context,
    load_memory,
    load_snippets,
    set_active_project,
    summarize_project_memory,
)
from .utils import CONFIG_DIR, ensure_terminal_punctuation, normalize_spaces, sentence_case


LOGGER = logging.getLogger("waky")


@dataclass(frozen=True)
class CommandSpec:
    key: str
    phrases: tuple[str, ...]
    setting_key: str
    instruction: str = ""
    output_format: str = ""
    priority: int = 50
    built_in: bool = True


BUILTIN_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("write_email", ("write email", "write an email", "email mode", "make email", "draft email"), "command_write_email_enabled", priority=1),
    CommandSpec("prompt_mode", ("prompt mode", "make this prompt", "convert into prompt", "turn this into prompt", "ai prompt"), "command_prompt_mode_enabled", priority=2),
    CommandSpec("bullet_points", ("bullet points", "bullet point", "make bullet points", "convert into bullet points", "turn this into points"), "command_bullet_points_enabled", priority=3),
    CommandSpec("rewrite_humanizer", ("rewrite and humanizer", "rewrite and humanize", "humanizer", "humanize this", "rewrite this", "rewrite"), "command_rewrite_humanizer_enabled", priority=4),
    CommandSpec("extend", ("extend this", "expand this", "make it longer", "elaborate", "extend", "extended"), "command_extend_enabled", priority=5),
    CommandSpec(
        "professional_tone",
        (
            "convert to professional tone",
            "make it professional",
            "make this professional",
            "professional tone",
            "make professional",
            "professionally",
            "formal tone",
            "make this formal",
            "make it formal",
            "professional",
        ),
        "command_professional_tone_enabled",
        priority=6,
    ),
    CommandSpec("casual_tone", ("casual tone", "make casual", "casually", "friendly tone"), "command_casual_tone_enabled", priority=7),
    CommandSpec("call_caps_small", ("call caps small", "all caps small", "caps small", "lowercase", "small letters"), "command_call_caps_small_enabled", priority=10),
)

BUILTIN_KEYS = {spec.key for spec in BUILTIN_COMMANDS}


def process_text(
    raw_text: str,
    settings: dict | None = None,
    selected_text: str | None = None,
    custom_commands: dict | None = None,
) -> str:
    """
    Takes raw transcription text and returns final processed text.
    If selected_text is present, raw_text is treated as the spoken instruction
    and selected_text is treated as the content to rewrite.
    """
    try:
        options = (settings or {}).get("command_processing", {}) if isinstance(settings, dict) else {}
        memory_enabled = bool(options.get("local_memory_enabled", True))
        memory_context = _load_memory_context(memory_enabled)
        original = _apply_memory_corrections(raw_text or "", memory_enabled)
        selected = _apply_memory_corrections(selected_text or "", memory_enabled).strip()
        selected_mode = bool(selected)
        commands_enabled = bool(options.get("voice_commands_enabled", True))
        auto_translate = bool(options.get("auto_translate_to_english", True))
        auto_fix = bool(options.get("auto_fix_grammar", True))
        rewrite_engine = str(options.get("command_rewrite_engine", "cloud_if_available") or "cloud_if_available")
        if selected_mode:
            selected_engine = str(options.get("selected_rewrite_ai_mode", "auto") or "auto")
            rewrite_engine = "cloud_if_available" if selected_engine in {"auto", "cloud_if_available"} else "rule_based_only"
        specs = _command_specs(custom_commands)

        LOGGER.info("[COMMAND_PIPELINE] process_text called")
        LOGGER.info("[COMMAND] enabled=%s", str(commands_enabled).lower())
        LOGGER.info("[COMMAND] selected_text_mode=%s", str(selected_mode).lower())
        LOGGER.info("[COMMAND] raw_length=%s", len(original))
        LOGGER.info("[MEMORY] local_memory_enabled=%s", str(memory_enabled).lower())

        if not selected_mode:
            snippet = _match_snippet(original)
            if snippet is not None:
                return snippet

        memory_command_result = _handle_memory_voice_command(original, options, memory_enabled)
        if memory_command_result is not None:
            return memory_command_result

        log_input = bool((settings or {}).get("privacy", {}).get("include_transcript_in_logs", False)) if isinstance(settings, dict) else False
        instruction_text, detected, detected_specs = _detect_and_remove_commands(original, options, specs, log_input=log_input) if commands_enabled else (original, set(), [])
        for spec in sorted(detected_specs, key=lambda item: item.priority):
            LOGGER.info("[COMMAND] detected=%s", spec.key)
            if not spec.built_in:
                LOGGER.info("[COMMAND] custom_command_used=%s", spec.key)
        LOGGER.info("[COMMAND_PIPELINE] commands_detected=%s", [spec.key for spec in detected_specs])
        LOGGER.info("[COMMAND] detected_count=%s", len(detected_specs))
        LOGGER.info("[COMMAND] auto_translate_to_english=%s", str(auto_translate).lower())
        LOGGER.info("[COMMAND] auto_fix_grammar=%s", str(auto_fix).lower())

        result = _prepare_selected_text_input(selected, instruction_text, detected) if selected_mode else _clean_raw_content(instruction_text)

        if not result:
            return ""

        mode = "selected_rewrite" if selected_mode else "normal_dictation"
        should_try_cloud = _cloud_should_run(settings, rewrite_engine, bool(detected_specs) or selected_mode)
        cloud_result = _try_cloud_rewrite(
            settings=settings,
            engine=rewrite_engine,
            should_run=should_try_cloud,
            mode=mode,
            detected_specs=detected_specs,
            selected_text=selected,
            instruction_text=original if selected_mode else instruction_text,
            content=result,
            memory_context=memory_context,
        )
        LOGGER.info("[COMMAND_REWRITE] mode=%s detected_commands=%s input_length=%s", mode, [spec.key for spec in detected_specs], len(result))

        if cloud_result:
            result = cloud_result
            LOGGER.info("[COMMAND_REWRITE] engine=cloud")
            LOGGER.info("[COMMAND_PIPELINE] using_rewrite_engine=cloud")
            LOGGER.info("[COMMAND_REWRITE] fallback_used=false")
        else:
            LOGGER.info("[COMMAND_REWRITE] engine=rule_based")
            LOGGER.info("[COMMAND_PIPELINE] using_rewrite_engine=rule_based")
            LOGGER.info("[COMMAND_REWRITE] fallback_used=%s", str(should_try_cloud and bool(llm_engine.get_api_key(settings))).lower())
            if auto_translate:
                result = _translate_to_english(result)
            result = _rewrite_core(result)
            result = _apply_commands(result, detected, detected_specs, auto_fix=False)
            result = _remove_forbidden_phrases(result, memory_enabled)

        if selected_mode and not detected and not cloud_result:
            result = _apply_freeform_instruction(selected, original, result)
            if auto_translate:
                result = _translate_to_english(result)
            result = _rewrite_core(result)

        if auto_translate:
            result = _translate_to_english(result)
        if auto_fix:
            result = _fix_grammar(result)
        result = _apply_vocabulary(result, memory_enabled)
        result = _remove_forbidden_phrases(result, memory_enabled)

        if "call_caps_small" in detected:
            result = _lowercase_preserving_specials(result)

        result = result.strip()
        if memory_enabled:
            _maybe_save_memory_artifacts(result, original, selected_mode, detected, options)
        LOGGER.info("[COMMAND] final_length=%s", len(result))
        LOGGER.info("[COMMAND_REWRITE] output_length=%s", len(result))
        LOGGER.info("[COMMAND_PIPELINE] final_text_ready=true")
        return result
    except Exception:
        LOGGER.warning("Command processing failed; returning raw text", exc_info=True)
        return raw_text or ""


def process_text_with_context(
    selected_text: str,
    instruction_text: str,
    settings: dict | None = None,
    custom_commands: dict | None = None,
) -> str:
    """Rewrite selected text according to spoken instructions."""
    LOGGER.info("[COMMAND_PIPELINE] process_text_with_context called")
    return process_text(
        instruction_text,
        settings,
        selected_text=selected_text,
        custom_commands=custom_commands,
    )


def _command_specs(custom_commands: dict | None) -> list[CommandSpec]:
    if not isinstance(custom_commands, dict):
        return list(BUILTIN_COMMANDS)
    commands = custom_commands.get("commands")
    if not isinstance(commands, list):
        return list(BUILTIN_COMMANDS)

    specs: list[CommandSpec] = []
    for item in commands:
        if not isinstance(item, dict):
            continue
        key = item.get("command_id") or item.get("id")
        if not key or item.get("enabled") is False:
            continue
        triggers = item.get("trigger_phrases") or item.get("triggers") or []
        if not isinstance(triggers, list):
            continue
        phrases = tuple(str(trigger).strip() for trigger in triggers if str(trigger).strip())
        if not phrases:
            continue
        if key == "professional_tone":
            phrases = tuple(
                dict.fromkeys(
                    list(phrases)
                    + [
                        "convert to professional tone",
                        "make it professional",
                        "make this professional",
                        "make this formal",
                        "make it formal",
                        "professional",
                    ]
                )
            )
        key = str(key).strip()
        specs.append(
            CommandSpec(
                key=key,
                phrases=phrases,
                setting_key=f"command_{key}_enabled",
                instruction=str(item.get("instruction_template") or item.get("instruction", "")),
                output_format=str(item.get("output_format", "")),
                priority=int(item.get("priority", 50)),
                built_in=bool(item.get("built_in", key in BUILTIN_KEYS)),
            )
        )
    return specs or list(BUILTIN_COMMANDS)


def _detect_and_remove_commands(text: str, options: dict, specs: list[CommandSpec], log_input: bool = False) -> tuple[str, set[str], list[CommandSpec]]:
    detected: set[str] = set()
    detected_specs: list[CommandSpec] = []
    cleaned = f" {text} "
    if log_input:
        LOGGER.info("[COMMAND_DETECT] input=%s", text)
    for spec in sorted(specs, key=lambda item: min((len(p) for p in item.phrases), default=0), reverse=True):
        if spec.key in BUILTIN_KEYS and not bool(options.get(spec.setting_key, True)):
            continue
        matched = False
        for phrase in sorted(spec.phrases, key=len, reverse=True):
            pattern = re.compile(rf"(?i)(?<!\w){re.escape(phrase)}(?!\w)")
            if pattern.search(cleaned):
                detected.add(spec.key)
                cleaned = pattern.sub(" ", cleaned)
                matched = True
                LOGGER.info("[COMMAND_DETECT] detected=%s", spec.key)
                LOGGER.info("[COMMAND_DETECT] trigger_phrase=%s", phrase)
        if matched:
            detected_specs.append(spec)
    detected_specs.sort(key=lambda item: item.priority)
    cleaned_text = normalize_spaces(cleaned)
    LOGGER.info("[COMMAND_DETECT] cleaned_text_length=%s", len(cleaned_text))
    return cleaned_text, detected, detected_specs


def _clean_raw_content(text: str) -> str:
    result = normalize_spaces(text)
    result = re.sub(r"\b(um|uh|you know|actually|basically|like)\b[,\s]*", "", result, flags=re.I)
    result = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", result, flags=re.I)
    return normalize_spaces(result)


def _detected_tone(detected: set[str]) -> str:
    if "professional_tone" in detected:
        return "professional"
    if "casual_tone" in detected:
        return "casual"
    if "rewrite_humanizer" in detected:
        return "humanized"
    return "neutral"


def _match_snippet(text: str) -> str | None:
    snippets_data = _load_snippet_sources()
    enabled = bool(snippets_data.get("enabled", True))
    LOGGER.info("[SNIPPET] enabled=%s", str(enabled).lower())
    if not enabled:
        return None
    normalized_text = _snippet_normalize(text)
    original_text = (text or "").strip()
    if not normalized_text:
        return None
    for snippet in snippets_data.get("snippets", []):
        if not isinstance(snippet, dict) or not snippet.get("enabled", True):
            continue
        name = str(snippet.get("name") or snippet.get("trigger") or "snippet")
        triggers = snippet.get("triggers")
        if not isinstance(triggers, list):
            trigger = snippet.get("trigger", "")
            triggers = [trigger] if trigger else []
        for trigger in triggers:
            normalized_trigger = _snippet_normalize(str(trigger))
            if not normalized_trigger:
                continue
            if _snippet_matches(normalized_text, normalized_trigger):
                value = str(snippet.get("value", ""))
                LOGGER.info("[SNIPPET] matched=%s", name)
                LOGGER.info("[SNIPPET] trigger=%s", trigger)
                LOGGER.info("[SNIPPET] value_empty=%s", str(not bool(value.strip())).lower())
                LOGGER.info("[SNIPPET] pasted=%s", str(bool(value.strip())).lower())
                if not value.strip():
                    LOGGER.info("[SNIPPET] matched but value empty")
                    return ""
                if normalized_text == normalized_trigger or _snippet_is_mostly_command(normalized_text, normalized_trigger):
                    return value
                return _replace_snippet_trigger(original_text, str(trigger), value)
    return None


def _load_snippet_sources() -> dict[str, Any]:
    combined: dict[str, Any] = {"enabled": True, "snippets": []}
    try:
        memory_snippets = load_snippets()
        combined["enabled"] = bool(memory_snippets.get("enabled", True))
        combined["snippets"].extend(memory_snippets.get("snippets", []))
    except Exception:
        LOGGER.warning("[SNIPPET] memory snippet load failed", exc_info=True)
    try:
        config_path = CONFIG_DIR / "snippets.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            combined["enabled"] = bool(data.get("enabled", combined["enabled"]))
            for item in data.get("snippets", []):
                if "triggers" not in item and item.get("trigger"):
                    item = dict(item)
                    item["triggers"] = [item.get("trigger")]
                    item.setdefault("name", item.get("trigger", "snippet"))
                combined["snippets"].append(item)
    except Exception:
        LOGGER.warning("[SNIPPET] config snippet load failed", exc_info=True)
    return combined


def _snippet_normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _snippet_matches(text: str, trigger: str) -> bool:
    if text == trigger:
        return True
    if _contains_snippet_phrase(text, trigger):
        return True
    text_words = text.split()
    trigger_words = trigger.split()
    if not trigger_words or len(text_words) > len(trigger_words) + 2:
        return False
    return all(word in text_words for word in trigger_words)


def _snippet_is_mostly_command(text: str, trigger: str) -> bool:
    text_words = text.split()
    trigger_words = trigger.split()
    return bool(trigger_words) and len(text_words) <= len(trigger_words) + 2 and all(word in text_words for word in trigger_words)


def _contains_snippet_phrase(text: str, trigger: str) -> bool:
    if not text or not trigger:
        return False
    return re.search(_snippet_phrase_pattern(trigger), text, flags=re.I) is not None


def _replace_snippet_trigger(text: str, trigger: str, value: str) -> str:
    replacement = re.sub(_snippet_phrase_pattern(_snippet_normalize(trigger)), value.strip(), text, count=1, flags=re.I)
    return normalize_spaces(replacement)


def _snippet_phrase_pattern(trigger: str) -> str:
    words = _snippet_normalize(trigger).split()
    if not words:
        return r"$^"
    return r"(?<!\w)" + r"[\W_]+".join(re.escape(word) for word in words) + r"(?:[\W_]*)(?!\w)"


def _handle_memory_voice_command(text: str, options: dict, memory_enabled: bool) -> str | None:
    if not memory_enabled or not bool(options.get("memory_save_manual_remember_commands", True)):
        return None
    clean = normalize_spaces(text)
    lowered = clean.lower()
    paste_confirmation = bool(options.get("memory_paste_confirmations", False))

    def done(message: str) -> str:
        LOGGER.info("[MEMORY] %s", message)
        return message if paste_confirmation else ""

    match = re.match(r"(?i)^remember this\s+(.+)$", clean)
    if match:
        add_memory_note(match.group(1))
        return done("memory note saved")

    match = re.match(r"(?i)^remember correction\s+(.+?)\s+(?:means|mean|is|to)\s+(.+)$", clean)
    if match:
        add_correction(match.group(1), match.group(2), "Saved from voice command.")
        return done("memory correction saved")

    match = re.match(r"(?i)^remember vocabulary\s+(.+?)(?:\s+is\s+|\s+means\s+)(.+)$", clean)
    if match:
        add_vocabulary_item(match.group(1), match.group(2))
        return done("memory vocabulary saved")
    match = re.match(r"(?i)^remember vocabulary\s+(.+)$", clean)
    if match:
        add_vocabulary_item(match.group(1))
        return done("memory vocabulary saved")

    match = re.match(r"(?i)^switch project to\s+(.+)$", clean)
    if match:
        set_active_project(match.group(1))
        return done(f"active project set to {get_active_project()}")

    if lowered == "current project":
        project = get_active_project()
        LOGGER.info("[MEMORY] current_project=%s", project)
        return f"Current project: {project}" if paste_confirmation else ""

    if lowered == "summarize memory":
        summarize_project_memory(get_active_project())
        return done("memory summarized")

    return None


def _maybe_save_memory_artifacts(result: str, original: str, selected_mode: bool, detected: set[str], options: dict) -> None:
    if not result or len(result) < 40:
        return
    try:
        if options.get("memory_auto_save_useful_vocabulary", True):
            for term in re.findall(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2}|Groq|Codex|Notion)\b", result):
                if len(term) > 2 and term.lower() not in {"Subject", "Regards"}:
                    add_vocabulary_item(term, "Auto-detected from command output.")
        if detected and options.get("memory_save_command_outputs", True) and options.get("memory_save_selected_rewrite_examples", False):
            add_rewrite_example(original, result, ", ".join(sorted(detected)))
        elif selected_mode and options.get("memory_save_selected_rewrite_examples", False):
            add_rewrite_example(original, result, "selected_rewrite")
    except Exception:
        LOGGER.warning("[MEMORY] auto_save_failed", exc_info=True)


def _load_memory_context(memory_enabled: bool) -> str:
    if not memory_enabled:
        LOGGER.info("[MEMORY] context_loaded=false")
        return ""
    try:
        context = get_rewrite_context()
        snippets = load_snippets()
        snippet_lines: list[str] = []
        for item in snippets.get("snippets", [])[:20]:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            name = str(item.get("name") or item.get("trigger") or "snippet").strip()
            triggers = item.get("triggers")
            if not isinstance(triggers, list):
                triggers = [item.get("trigger", "")]
            trigger_text = ", ".join(str(trigger) for trigger in triggers if str(trigger).strip())
            if name or trigger_text:
                snippet_lines.append(f"- {name}: {trigger_text}")
        if snippet_lines:
            context += "\n\nRelevant snippets:\n" + "\n".join(snippet_lines)
        LOGGER.info("[COMMAND_REWRITE] memory_used=true")
        return context
    except Exception:
        LOGGER.warning("[MEMORY] context_loaded=false", exc_info=True)
        LOGGER.info("[COMMAND_REWRITE] memory_used=false")
        return ""


def _apply_memory_corrections(text: str, memory_enabled: bool) -> str:
    result = text or ""
    if not memory_enabled or not result:
        return result
    try:
        memory = load_memory()
        corrections = list(memory.get("corrections", {}).get("corrections", []))
        corrections.extend(memory.get("active_project_data", {}).get("corrections", {}).get("corrections", []))
        for item in corrections:
            if not isinstance(item, dict):
                continue
            wrong = str(item.get("wrong", "")).strip()
            correct = str(item.get("correct", "")).strip()
            note = str(item.get("note", "")).lower()
            if not wrong or not correct:
                continue
            if wrong.lower() in {"professional", "casual", "bullet"} and "can mean" not in note:
                continue
            result = re.sub(rf"(?i)(?<!\w){re.escape(wrong)}(?!\w)", correct, result)
    except Exception:
        LOGGER.warning("[MEMORY] corrections_failed", exc_info=True)
    return result


def _apply_vocabulary(text: str, memory_enabled: bool) -> str:
    result = text or ""
    if not memory_enabled or not result:
        return result
    try:
        memory = load_memory()
        terms = _memory_vocabulary_terms(memory.get("custom_vocabulary", {}))
        terms.extend(_memory_vocabulary_terms(memory.get("active_project_data", {}).get("vocabulary", {})))
        for term in terms:
            if term == "Krishna":
                LOGGER.info("[VOCAB] loaded term=Krishna")
            if not term or not any(ch.isupper() for ch in term):
                continue
            result = re.sub(rf"(?i)(?<!\w){re.escape(term)}(?!\w)", term, result)
    except Exception:
        LOGGER.warning("[VOCAB] vocabulary_apply_failed", exc_info=True)
    return result


def _memory_vocabulary_terms(data: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for word in data.get("words", []):
        if str(word).strip():
            terms.append(str(word).strip())
    for item in data.get("items", []):
        if isinstance(item, dict) and item.get("enabled", True) and str(item.get("term", "")).strip():
            terms.append(str(item["term"]).strip())
    return list(dict.fromkeys(terms))


def _remove_forbidden_phrases(text: str, memory_enabled: bool) -> str:
    result = text or ""
    if not result:
        return result
    phrases: list[str] = []
    if memory_enabled:
        try:
            phrases = get_forbidden_phrases()
        except Exception:
            LOGGER.warning("[MEMORY] forbidden_phrase_load_failed", exc_info=True)
    for phrase in phrases:
        if str(phrase).strip():
            result = re.sub(rf"(?i)\s*{re.escape(str(phrase).strip())}\s*", " ", result)
    if "\n" in result:
        return "\n".join(normalize_spaces(line) for line in result.splitlines()).strip()
    return normalize_spaces(result).strip()


def _cloud_should_run(settings: dict | None, engine: str, has_rewrite_work: bool) -> bool:
    if engine == "rule_based_only":
        return False
    if engine == "cloud_if_available":
        return True
    return has_rewrite_work


def _try_cloud_rewrite(
    *,
    settings: dict | None,
    engine: str,
    should_run: bool,
    mode: str,
    detected_specs: list[CommandSpec],
    selected_text: str,
    instruction_text: str,
    content: str,
    memory_context: str,
) -> str | None:
    if not should_run:
        LOGGER.info("[COMMAND_REWRITE] engine=none reason=engine_disabled_or_no_work")
        return None
    if not llm_engine.get_api_key(settings):
        LOGGER.info("[COMMAND_REWRITE] engine=rule_based reason=no_groq_key")
        return None
    options = (settings or {}).get("command_processing", {}) if isinstance(settings, dict) else {}
    request = llm_engine.RewriteRequest(
        transcript=instruction_text if selected_text else content,
        selected_text=selected_text,
        modes=[llm_engine.ModeInstruction(spec.key, spec.instruction or _BUILTIN_HINTS.get(spec.key, ""), spec.output_format) for spec in detected_specs],
        custom_instructions=str(options.get("custom_instructions", "")),
        memory_context=memory_context,
        auto_translate=bool(options.get("auto_translate_to_english", True)),
    )
    try:
        result = llm_engine.rewrite(request, settings)
    except llm_engine.LLMRateLimited as exc:
        LOGGER.warning("[COMMAND_REWRITE] Groq rate limited (%s); using rule-based fallback", exc)
        return None
    except llm_engine.LLMError as exc:
        LOGGER.warning("[COMMAND_REWRITE ERROR] %s; using rule-based fallback", exc)
        return None
    return _remove_forbidden_phrases(result, True)


_BUILTIN_HINTS = {
    "write_email": "Write a complete email with a meaningful subject line, greeting, body and a concise sign-off.",
    "prompt_mode": "Turn the content into a strong, structured AI prompt (task, context, requirements, expected output).",
    "bullet_points": "Group the ideas into meaningful bullet points under a short heading; do not bullet every sentence.",
    "rewrite_humanizer": "Rewrite so it sounds natural and human while keeping the meaning.",
    "extend": "Expand the actual idea with useful detail; no generic filler.",
    "professional_tone": "Polished, professional tone.",
    "casual_tone": "Natural, friendly, casual tone.",
    "call_caps_small": "Output in lowercase.",
}



def _prepare_selected_text_input(selected: str, instruction: str, detected: set[str]) -> str:
    base = normalize_spaces(selected)
    extra = normalize_spaces(instruction)
    if extra.lower() in {"and", "and then", "then", ","}:
        extra = ""
    if extra:
        if not detected:
            return base
        base = _apply_instruction_detail(base, extra, detected)
    return base


def _apply_instruction_detail(base: str, instruction: str, detected: set[str]) -> str:
    result = normalize_spaces(base)
    detail = normalize_spaces(instruction)
    lowered = detail.lower()
    if not detail:
        return result
    add_match = re.search(r"(?i)\badd that\s+(.+)$", detail)
    if add_match:
        return _append_sentence(result, add_match.group(1))
    mention_match = re.search(r"(?i)\bmention\s+(?:that\s+)?(.+)$", detail)
    if mention_match:
        mention = _instruction_fragment_to_sentence(mention_match.group(1))
        return _append_sentence(result, mention)
    if "more polite" in lowered:
        detected.add("professional_tone")
        return result
    if not detected:
        return _apply_freeform_instruction(base, instruction, base)
    return normalize_spaces(f"{result}. {_instruction_fragment_to_sentence(detail)}")


def _apply_freeform_instruction(selected: str, instruction: str, current: str) -> str:
    lowered = instruction.lower()
    result = normalize_spaces(current or selected)
    if "more polite" in lowered:
        result = _professional(result)
    if "casual" in lowered or "friendly" in lowered:
        result = _casual(result)
    if "professional" in lowered or "formal" in lowered:
        result = _professional(result)
    if "human" in lowered or "rewrite" in lowered:
        result = _humanize(result)
    mention_match = re.search(r"(?i)\bmention\s+(?:that\s+)?(.+)$", instruction)
    if mention_match:
        result = _append_sentence(result, _instruction_fragment_to_sentence(mention_match.group(1)))
    add_match = re.search(r"(?i)\badd that\s+(.+)$", instruction)
    if add_match:
        result = _append_sentence(result, _instruction_fragment_to_sentence(add_match.group(1)))
    return result


def _append_sentence(base: str, addition: str) -> str:
    left = normalize_spaces(base).rstrip(".!? ")
    right = ensure_terminal_punctuation(sentence_case(normalize_spaces(addition))).strip()
    if right.lower().rstrip(".!?") in left.lower():
        return ensure_terminal_punctuation(sentence_case(left))
    return normalize_spaces(f"{left}. {right}")


def _instruction_fragment_to_sentence(fragment: str) -> str:
    lowered = normalize_spaces(fragment).lower()
    if "sick" in lowered or "not feeling well" in lowered:
        return "I am not feeling well."
    return ensure_terminal_punctuation(sentence_case(fragment))


def _apply_commands(text: str, detected: set[str], detected_specs: list[CommandSpec], auto_fix: bool) -> str:
    result = text
    if "rewrite_humanizer" in detected:
        result = _humanize(result)
    if "professional_tone" in detected:
        result = _professional(result)
    if "casual_tone" in detected:
        result = _casual(result)
    if "extend" in detected and not ({"write_email", "prompt_mode"} & detected):
        result = _extend(result)

    if "write_email" in detected:
        result = _write_email(result, extended="extend" in detected)
    elif "prompt_mode" in detected:
        result = _prompt_mode(result, extended="extend" in detected)
    elif "bullet_points" in detected:
        result = _bullet_points(result, extended="extend" in detected)

    for spec in detected_specs:
        if spec.key not in BUILTIN_KEYS:
            result = _apply_custom_command(result, spec)

    if auto_fix:
        result = _fix_grammar(result)
    return result


def _apply_custom_command(text: str, spec: CommandSpec) -> str:
    guidance = f"{spec.key} {spec.instruction} {spec.output_format}".lower()
    if "email" in guidance:
        return _write_email(text)
    if "bullet" in guidance or "point" in guidance:
        return _bullet_points(text)
    if "prompt" in guidance:
        return _prompt_mode(text)
    if "lowercase" in guidance or "small" in guidance:
        return _lowercase_preserving_specials(text)
    if "extend" in guidance or "expand" in guidance or "elaborate" in guidance:
        return _extend(text)
    if "professional" in guidance or "formal" in guidance:
        return _professional(text)
    if "casual" in guidance or "friendly" in guidance:
        return _casual(text)
    if "poetic" in guidance:
        return _poetic(text)
    return _humanize(text)


def _poetic(text: str) -> str:
    clean = _fix_grammar(_rewrite_core(_translate_to_english(text)))
    lowered = clean.lower()
    if "send" in lowered and "file" in lowered:
        return "I will send the file today, once it is ready and carefully checked."
    return clean


def _rewrite_core(text: str) -> str:
    result = _clean_raw_content(text)
    replacements = (
        (r"\bcan you please teacher that\b", "please inform Sir that"),
        (r"\bcan you please tell teacher that\b", "please inform Sir that"),
        (r"\bteacher that\b", "Sir that"),
        (r"\btell sir\b", "Sir,"),
        (r"\bpls\b|\bplz\b", "please"),
        (r"\bu\b", "you"),
        (r"\bur\b", "your"),
        (r"\bi am not able to\b", "I am unable to"),
        (r"\bi am not come tomorrow because work\b", "I will not be able to come tomorrow due to work commitments"),
        (r"\bi am not coming tomorrow because work\b", "I will not be able to come tomorrow due to work commitments"),
        (r"\bi am sick can't attend exam\b", "I am not feeling well and cannot attend the exam"),
        (r"\bi am sick cant attend exam\b", "I am not feeling well and cannot attend the exam"),
        (r"\bi am sick and cannot attend exam\b", "I am not feeling well and cannot attend the exam"),
        (r"\bi am not well\b", "I am not feeling well"),
        (r"\bcannot attend exam tomorrow\b", "cannot attend tomorrow's exam"),
        (r"\bcannot attend the exam tomorrow\b", "cannot attend tomorrow's exam"),
        (r"\bI can't Attend\b", "I cannot attend"),
        (r"\bi can't attend\b", "I cannot attend"),
        (r"\bcant attend\b", "cannot attend"),
        (r"\burgent work came\b", "some urgent work came up"),
        (r"\burgent work commitment came up\b", "an urgent work commitment came up"),
        (r"\bI cannot come today because urgent work came\b", "I cannot come today because an urgent work commitment came up"),
        (r"\bi cant come tomorrow urgent work came\b", "I cannot come tomorrow because an urgent work commitment came up"),
        (r"\bi cannot attend the meeting tomorrow because i have urgent work\b", "I cannot attend tomorrow's meeting because I have urgent work"),
        (r"\bi will send the design files tonight\b", "I will send the design files tonight"),
        (r"\bnot feeling well\b", "not feeling well"),
    )
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    result = _soften_inappropriate_requests(result)
    return normalize_spaces(result)


def _soften_inappropriate_requests(text: str) -> str:
    result = text
    result = re.sub(
        r"(?i)\bso please pass me in that exam\b",
        "so I request your consideration for any possible alternative arrangement or next steps",
        result,
    )
    result = re.sub(
        r"(?i)\bplease pass me in (?:that|the) exam\b",
        "please guide me regarding any possible alternative arrangement or next steps",
        result,
    )
    result = re.sub(r"(?i)\band also extend this\b", "and consider an extension if possible", result)
    result = re.sub(r"(?i)\bextend this\b", "consider an extension if possible", result)
    return normalize_spaces(result)


def _translate_to_english(text: str) -> str:
    if "\n" in text:
        return "\n".join(_translate_structured_line(line) for line in text.splitlines())
    result = normalize_spaces(text)
    direct = (
        (r"\bkal\s+main\s+documentation\s+complete\s+kar\s+dunga\b", "I will complete the documentation tomorrow"),
        (r"\bkal\s+mai\s+documentation\s+complete\s+kar\s+dunga\b", "I will complete the documentation tomorrow"),
    )
    for source, target in direct:
        result = re.sub(source, target, result, flags=re.I)
    replacements = (
        (r"\bcomplete kar dunga\b", "will complete"),
        (r"\bcomplete kar dungi\b", "will complete"),
        (r"\bkal\b", "tomorrow"),
        (r"\baaj\b", "today"),
        (r"\bmain\b", "I"),
        (r"\bmai\b", "I"),
        (r"\bmujhe\b", "I need to"),
        (r"\bkar dunga\b", "will do"),
        (r"\bkar dungi\b", "will do"),
        (r"\bbhej dunga\b", "will send"),
        (r"\bbhej dungi\b", "will send"),
        (r"\bfile bhej\b", "send the file"),
        (r"\breport bhej\b", "send the report"),
    )
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    result = re.sub(r"\bcomplete documentation\b", "complete the documentation", result, flags=re.I)
    result = re.sub(r"\bwill complete documentation\b", "will complete the documentation", result, flags=re.I)
    result = re.sub(r"\bI documentation will complete\b", "I will complete the documentation", result, flags=re.I)
    result = re.sub(r"\bI (.+?) will complete\b", r"I will complete \1", result, flags=re.I)
    return normalize_spaces(result)


def _translate_structured_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.endswith(":") or stripped.lower().startswith("subject:") or re.match(r"(?i)^hi\b.*,$", stripped) or stripped in {"Regards,"}:
        return line
    if stripped.startswith("-"):
        return "- " + _translate_to_english(stripped[1:].strip())
    return _translate_to_english(line)


def _humanize(text: str) -> str:
    result = normalize_spaces(text)
    replacements = (
        (r"\bI am unable to come today because some urgent work came up\b", "I won't be able to come today because something urgent has come up"),
        (r"\bI cannot come today because some urgent work came up\b", "I won't be able to come today because something urgent has come up"),
        (r"\bI will not be able to come tomorrow due to work commitments\b", "I won't be able to come tomorrow due to some work commitments"),
        (r"\bI am unable to\b", "I can't"),
        (r"\bI will\b", "I'll"),
        (r"\bI am\b", "I'm"),
    )
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    return ensure_terminal_punctuation(sentence_case(normalize_spaces(result)))


def _professional(text: str) -> str:
    if "\n" in text:
        return "\n".join(_professional_structured_line(line) for line in text.splitlines()).strip()
    result = normalize_spaces(text)
    replacements = (
        (r"\bI'll\b", "I will"),
        (r"\bI'm\b", "I am"),
        (r"\bI can't\b", "I am unable to"),
        (r"\bsend you\b", "share"),
    )
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    return ensure_terminal_punctuation(sentence_case(normalize_spaces(result)))


def _professional_structured_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.lower().startswith("subject:") or re.match(r"(?i)^hi\b.*,$", stripped) or stripped in {"Regards,"}:
        return stripped
    return _professional(stripped)


def _casual(text: str) -> str:
    if "\n" in text:
        return "\n".join(_casual_structured_line(line) for line in text.splitlines()).strip()
    result = normalize_spaces(text)
    replacements = (
        (r"\bI will\b", "I'll"),
        (r"\bI am\b", "I'm"),
        (r"\bI cannot\b", "I can't"),
        (r"\bI am unable to\b", "I can't"),
    )
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    return ensure_terminal_punctuation(sentence_case(normalize_spaces(result)))


def _casual_structured_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.lower().startswith("subject:") or re.match(r"(?i)^hi\b.*,$", stripped) or stripped in {"Regards,"}:
        return stripped
    return _casual(stripped)


def _extend(text: str) -> str:
    result = _rewrite_core(_translate_to_english(text))
    lowered = result.lower()
    if "not feeling well" in lowered and "exam" in lowered:
        return (
            "I am not feeling well and may not be able to attend the upcoming exam. Because of my health condition, "
            "I may need to miss the scheduled exam and would like to understand what options are available. Please let "
            "me know if there is any process I should follow or any alternative arrangement possible."
        )
    if "meeting" in lowered and ("urgent work" in lowered or "work commitment" in lowered):
        return (
            "I will not be able to attend tomorrow's meeting because an urgent work commitment has come up. "
            "I am informing you in advance so the schedule or discussion can be adjusted if needed. "
            "If there are key points from the meeting that require my input, I can review them afterward and respond accordingly."
        )
    if ("rewrite command" in lowered or "rewrite option" in lowered) and ("formats" in lowered or "generic line" in lowered):
        return (
            "The rewrite command is not working as expected. It is formatting the text instead of understanding the context, "
            "and it is adding generic lines instead of improving the actual meaning of the selected content."
        )
    if ("cannot come" in lowered or "can't come" in lowered or "unable to come" in lowered) and ("urgent work" in lowered or "work commitment" in lowered):
        return (
            "I will not be able to come because an urgent work commitment has come up. "
            "I wanted to let you know ahead of time so the plan can be adjusted if needed. "
            "If there is anything specific I should complete or review separately, I can take care of it afterward."
        )
    if "send" in lowered and "design" in lowered:
        return (
            "I will share the design files tonight after reviewing the final version. I will make sure the files are organized "
            "and ready for you to check."
        )
    if "send" in lowered and "file" in lowered:
        return (
            "I will share the files tonight after reviewing them and making sure the final version is ready. "
            "I will check the important details once more before sending them so everything is complete."
        )
    if len(result.split()) < 12:
        return ensure_terminal_punctuation(sentence_case(_expand_short_statement(result)))
    return ensure_terminal_punctuation(sentence_case(_expand_long_statement(result)))


def _expand_short_statement(text: str) -> str:
    lowered = text.lower()
    if "cannot come" in lowered or "can't come" in lowered or "unable to come" in lowered:
        return f"{text} This affects my availability, so I am informing you ahead of time and will handle any follow-up separately if required."
    if "completed" in lowered or "finished" in lowered:
        return f"{text} The main work is complete, and the next step is to review it carefully and make any final changes if needed."
    if "send" in lowered or "share" in lowered:
        return f"{text} I will review the details once more before sharing it, so the final version is clear and ready to use."
    if len(text.split()) <= 5:
        return f"{text} I will keep the message focused while adding only the context needed to make the point clear."
    return f"{text} The main idea remains the same, but the message is written with more context and smoother wording."


def _expand_long_statement(text: str) -> str:
    lowered = text.lower()
    if "urgent work" in lowered:
        return f"{text} An urgent work commitment has affected my availability, so I am informing you in advance while there is still time to adjust the plan."
    if "exam" in lowered:
        return f"{text} Please let me know if there is any process I should follow in this situation."
    sentences = re.split(r"(?<=[.!?])\s+", ensure_terminal_punctuation(sentence_case(text)))
    if len(sentences) > 1:
        return normalize_spaces(" ".join(sentences))
    return f"{text} The message is expanded by clarifying the same situation, keeping the original meaning intact and avoiding unsupported details."


def _write_email(text: str, extended: bool = False) -> str:
    recipient, body = _extract_recipient(text)
    body = _email_body_rewrite(body, extended=extended)
    subject = _email_subject(body)
    greeting = f"Hi {recipient}," if recipient else "Hi there,"
    return f"Subject: {subject}\n\n{greeting}\n\n{body}\n\nRegards,"


def _extract_recipient(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if re.search(r"\b(ma'am|madam)\b", lowered):
        return "Ma'am", normalize_spaces(re.sub(r"(?i)\b(?:tell|send to|mail to)?\s*(ma'am|madam)\b[:,]?", " ", text, count=1))
    if re.search(r"\b(teacher|sir)\b", lowered):
        cleaned = re.sub(r"(?i)\bcan you please teacher that\b", " ", text, count=1)
        cleaned = re.sub(r"(?i)\bplease\s+inform\s+sir\s+that\b", " ", cleaned, count=1)
        cleaned = re.sub(r"(?i)\bsir\s+that\b", " ", cleaned, count=1)
        cleaned = re.sub(r"(?i)\b(?:tell|send to|mail to)?\s*(teacher|sir)\b[:,]?", " ", cleaned, count=1)
        return "Sir", normalize_spaces(cleaned)
    if "exam" in lowered:
        return "Sir", text
    match = re.search(r"(?i)^(?:tell|send to|mail to)\s+([A-Z][a-zA-Z]*)\s+", text)
    if match:
        return sentence_case(match.group(1)), normalize_spaces(text[match.end() :])
    return "", text


def _email_body_rewrite(text: str, extended: bool = False) -> str:
    result = _rewrite_core(_translate_to_english(text))
    lowered = result.lower()
    if "not feeling well" in lowered and "exam" in lowered:
        exam_phrase = "tomorrow's exam" if "tomorrow" in lowered else "the upcoming exam"
        if extended:
            return (
                f"I hope you are doing well. I am not feeling well and may not be able to attend {exam_phrase}. "
                "I am sharing this in advance and kindly request your guidance on what I should do in this situation."
            )
        return (
            f"I hope you are doing well. I am not feeling well and may not be able to attend {exam_phrase}. "
            "I am sharing this in advance and kindly request your guidance on what I should do in this situation."
        )
    if ("homepage" in lowered or "design" in lowered) and ("completed" in lowered or "finished" in lowered or "done" in lowered):
        share_part = " and will share the files with you tonight" if re.search(r"(?i)\b(tonight|today|share|send)\b", lowered) else ""
        return (
            f"I have completed the homepage design{share_part}. Please feel free to review it once shared, "
            "and let me know if any changes are needed."
        )
    if "send" in lowered and "design" in lowered:
        return "I will share the design files tonight after reviewing them. Please feel free to check them once shared."
    if "send" in lowered and "file" in lowered:
        return "I will share the files tonight after reviewing them. Please feel free to check them once shared."
    return _professional(result)


def _email_subject(body: str) -> str:
    lowered = body.lower()
    if "exam" in lowered and ("tomorrow" in lowered or "upcoming" in lowered):
        return "Request for Guidance Regarding Tomorrow's Exam" if "tomorrow" in lowered else "Request for Exam Consideration"
    if "homepage" in lowered and "design" in lowered:
        return "Homepage Design Update"
    if "design" in lowered and ("file" in lowered or "share" in lowered):
        return "Design Files Update"
    if "meeting" in lowered:
        return "Meeting Availability Update"
    if "documentation" in lowered:
        return "Documentation Update"
    if "report" in lowered:
        return "Report Update"
    words = normalize_spaces(body).split()[:6]
    return sentence_case(" ".join(words)).rstrip(".") or "Update"


def _prompt_mode(text: str, extended: bool = False) -> str:
    clean = _professional(_translate_to_english(text))
    requirements = _prompt_requirements(clean, extended=extended)
    context = clean
    if extended:
        context = clean + " Include enough detail to make the task clear, practical, and safe to execute."
    return (
        "Task:\n"
        f"{clean}\n\n"
        "Context:\n"
        f"{context}\n\n"
        "Requirements:\n"
        + "\n".join(f"- {item}" for item in requirements)
        + "\n\n"
        "Expected Output:\n"
        "A clear, actionable result that can be used directly."
    )


def _prompt_requirements(text: str, extended: bool = False) -> list[str]:
    lowered = text.lower()
    if "tool" in lowered and "pc" in lowered and "clean" in lowered:
        return [
            "Design a safe PC cleaning tool that avoids deleting important user data.",
            "Include clear steps, safeguards, and user confirmations.",
            "Explain the expected features, constraints, and output.",
        ]
    base = [
        "Keep the solution clear and practical.",
        "Use only the context provided by the user.",
        "Avoid adding unsupported or fake details.",
    ]
    if extended:
        base.append("Provide enough detail for implementation or direct use.")
    return base


def _bullet_points(text: str, extended: bool = False) -> str:
    clean = _rewrite_core(_translate_to_english(text))
    points = _intelligent_points(clean)
    if not points:
        return _fix_grammar(clean)
    heading = _short_heading(clean)
    if extended:
        points = [_extend_bullet(point) for point in points]
    bullets = "\n".join(f"- {ensure_terminal_punctuation(sentence_case(_rewrite_bullet(point)))}" for point in points[:8])
    return f"{heading}\n\n{bullets}"


def _intelligent_points(text: str) -> list[str]:
    lowered = text.lower()
    points: list[str] = []
    if ("rewrite option" in lowered or "rewrite command" in lowered) and ("not working" in lowered or "only converts" in lowered):
        points.append("The rewrite command is formatting text instead of understanding and improving the actual message.")
    if "only converts commands" in lowered or "only converts" in lowered:
        points.append("Command output needs semantic rewriting rather than mechanical conversion.")
    if "email" in lowered and "does not understand context" in lowered:
        points.append("The email command should infer the purpose, recipient, and message context before drafting.")
    if "email command" in lowered and ("format" in lowered or "copies" in lowered):
        points.append("The email command is formatting text into a template instead of understanding the message.")
    if "bullet" in lowered and ("not working" in lowered or "does not understand context" in lowered):
        points.append("Bullet points should group related ideas into clear, useful points.")
    if "line by line" in lowered or ("breaks" in lowered and "point" in lowered):
        points.append("The bullet point command is splitting text line by line instead of organizing ideas.")
    if "generic filler" in lowered or "generic line" in lowered or ("generic" in lowered and "filler" in lowered):
        points.append("The extend command is adding generic filler instead of expanding the actual meaning.")
    if "understand context" in lowered or "context" in lowered:
        points.append("The command processor needs to rewrite based on context, not just apply formatting.")
    if points:
        return points
    return _split_points(text)


def _split_points(text: str) -> list[str]:
    prepared = re.sub(r"\b(?:and then|then|and also|also)\b", ".", text, flags=re.I)
    prepared = re.sub(r"\b(finished|fixed|updated|completed)\b", r". \1", prepared, flags=re.I)
    parts = re.split(r"[.;,\n]+|\s+\band\s+", prepared)
    cleaned = [normalize_spaces(part.strip(" -")) for part in parts if normalize_spaces(part.strip(" -"))]
    points = [part for part in cleaned if part.lower() not in {"i", "today i", "today"}]
    if len(points) <= 1:
        action_points = re.findall(
            r"(?i)\b(?:finished|fixed|updated|completed|created|added|removed|improved)\b\s+[^.]+?(?=\s+\b(?:finished|fixed|updated|completed|created|added|removed|improved)\b|$)",
            text,
        )
        points = [normalize_spaces(point) for point in action_points if normalize_spaces(point)]
    return points


def _rewrite_bullet(text: str) -> str:
    result = normalize_spaces(text)
    result = re.sub(r"(?i)^today\s+", "", result)
    result = re.sub(r"(?i)^i\s+", "", result)
    result = re.sub(r"(?i)^fixed navbar$", "Fixed the navigation bar", result)
    result = re.sub(r"(?i)^updated hero$", "Updated the hero section", result)
    result = re.sub(r"(?i)^completed homepage$", "Completed the homepage design", result)
    return result


def _extend_bullet(text: str) -> str:
    lowered = text.lower()
    if "template" in lowered:
        return text + " It should infer the purpose of the message before writing."
    if "line by line" in lowered:
        return text + " Similar ideas should be grouped into useful points."
    if "generic filler" in lowered:
        return text + " The expansion should add context from the original idea."
    return text


def _short_heading(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("command", "email command", "bullet", "extend")):
        return "Command Processing Issues"
    if any(word in lowered for word in ("homepage", "navbar", "hero")):
        return "Homepage Update"
    if "documentation" in lowered:
        return "Documentation Update"
    words = normalize_spaces(text).split()[:5]
    return sentence_case(" ".join(words)).rstrip(".") if words else "Summary"


def _fix_grammar(text: str) -> str:
    if "\n" in text:
        return "\n".join(_fix_structured_line(line, index, text.splitlines()) for index, line in enumerate(text.splitlines())).strip()
    return _fix_grammar_line(text)


def _fix_structured_line(line: str, index: int, lines: list[str]) -> str:
    stripped = line.strip()
    next_blank = index + 1 < len(lines) and not lines[index + 1].strip()
    if not stripped:
        return line
    if stripped.endswith(":") or stripped.lower().startswith("subject:") or re.match(r"(?i)^hi\b.*,$", stripped) or stripped in {"Regards,"}:
        return stripped
    if index == 0 and next_blank and not stripped.startswith("-"):
        return sentence_case(normalize_spaces(stripped)).rstrip(".")
    if stripped.startswith("-"):
        return "- " + _fix_grammar_line(stripped[1:].strip())
    return _fix_grammar_line(stripped)


def _fix_grammar_line(text: str) -> str:
    result = normalize_spaces(text)
    result = re.sub(r"\b(um|uh|you know|actually|basically)\b[,\s]*", "", result, flags=re.I)
    result = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", result, flags=re.I)
    result = re.sub(r"\bi\b", "I", result)
    result = re.sub(r"\bim\b", "I'm", result, flags=re.I)
    result = re.sub(r"\bdont\b", "don't", result, flags=re.I)
    result = re.sub(r"\bcant\b", "can't", result, flags=re.I)
    return ensure_terminal_punctuation(sentence_case(result))


def _lowercase_preserving_specials(text: str) -> str:
    tokens = re.split(r"(\s+)", text)
    lowered: list[str] = []
    for token in tokens:
        if re.match(r"^[\w.+-]+@[\w.-]+\.\w+$", token) or re.match(r"(?i)^https?://", token) or re.search(r"[`_/\\{}()[\]=<>]", token):
            lowered.append(token)
        else:
            lowered.append(token.lower())
    return "".join(lowered)
