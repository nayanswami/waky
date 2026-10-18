from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import MEMORY_DIR


LOGGER = logging.getLogger("waky")
PROJECTS_DIR = MEMORY_DIR / "projects"


DEFAULT_USER_PROFILE = {"name": "", "notes": ["Prefer clean natural English.", "Avoid generic filler."]}
DEFAULT_WRITING_PREFERENCES = {
    "preferences": [
        "Write in clean natural English.",
        "Prefer meaningful output over mechanical formatting.",
        "Avoid generic filler.",
        "Do not sound robotic.",
        "Do not over-explain unless asked.",
        "Preserve the user's intent.",
        "User dislikes emojis.",
        "For write email, understand the real purpose and write a useful email.",
        "For bullet points, group ideas meaningfully instead of splitting every line.",
        "For extend, expand the actual idea to around 3x length, but avoid fake facts and generic filler.",
        "For selected text rewrite, use selected text as the main context and spoken instruction as the transformation command.",
    ]
}
DEFAULT_VOCABULARY = {
    "items": [
        {"term": "Waky", "notes": "Windows dictation app project."},
        {"term": "Groq", "notes": "Speech-to-text and optional chat provider."},
        {"term": "Wispr Flow", "notes": "Dictation app reference."},
        {"term": "WhisperFlow", "notes": "Dictation app reference."},
        {"term": "Codex", "notes": ""},
        {"term": "Notion", "notes": ""},
        {"term": "selected text rewrite", "notes": ""},
        {"term": "floating bar", "notes": ""},
        {"term": "command processor", "notes": ""},
        {"term": "Groq API", "notes": ""},
        {"term": "prompt mode", "notes": ""},
        {"term": "rewrite and humanizer", "notes": ""},
        {"term": "OpenAI", "notes": "Optional BYOK provider."},
        {"term": "OpenRouter", "notes": "Optional BYOK provider for rewriting."},
    ],
    "words": [
        "Waky",
        "Groq",
        "OpenAI",
        "OpenRouter",
        "Wispr Flow",
        "WhisperFlow",
        "Codex",
        "Notion",
        "selected text rewrite",
        "floating bar",
        "command processor",
        "Groq API",
        "prompt mode",
        "rewrite and humanizer",
    ],
}
DEFAULT_CORRECTIONS = {
    "corrections": [
        {"wrong": "Groc", "correct": "Groq", "note": "Common misheard word."},
        {"wrong": "Grok", "correct": "Groq", "note": "Common misheard word."},
        {"wrong": "Gopher", "correct": "Groq", "note": "Common misheard word."},
        {"wrong": "extended", "correct": "extend", "note": "May mean extend when used as a command."},
        {"wrong": "mail", "correct": "email", "note": "Can mean email."},
        {"wrong": "professional", "correct": "professional", "note": "Polished but not overly corporate."},
        {"wrong": "casual", "correct": "casual", "note": "Natural and simple, no emojis."},
        {"wrong": "bullet", "correct": "bullet points", "note": "Meaningful bullet points, not line-by-line splitting."},
        {"wrong": "open router", "correct": "OpenRouter", "note": "Provider name."},
        {"wrong": "waki", "correct": "Waky", "note": "App name."},
        {"wrong": "wakey", "correct": "Waky", "note": "App name."},
    ]
}
DEFAULT_SNIPPETS = {
    "enabled": True,
    "snippets": [
        {"name": "linkedin", "triggers": ["my linkedin", "linkedin profile", "paste my linkedin"], "value": "", "enabled": True},
        {"name": "email", "triggers": ["my email", "email address", "paste my email"], "value": "", "enabled": True},
    ],
}
DEFAULT_ACTIVE_PROJECT = {"active_project": "general"}
DEFAULT_FORBIDDEN = {
    "phrases": [
        "Please treat this as the current update from my side.",
        "I wanted to explain this more clearly",
        "I wanted to share this with a little more clarity",
        "so the message is easy to understand",
        "so the situation is easy to understand",
        "so the next step is clear",
        "I would appreciate your understanding and guidance",
    ],
    "notes": "Avoid these unless the original context specifically requires them.",
}
DEFAULT_PROJECT_CONTEXT = {
    "waky": [
        "Waky is a Windows desktop dictation and writing assistant.",
        "Waky supports normal dictation, selected text rewrite, voice commands, floating bar UI, Groq/local transcription, and command rewriting.",
        "Selected text plus spoken instruction should be understood together.",
        "The command engine should use context, not templates.",
    ],
    "general": ["General writing and dictation memory for Waky."],
}


def ensure_memory_files() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_json(MEMORY_DIR / "user_profile.json", DEFAULT_USER_PROFILE)
    _ensure_json(MEMORY_DIR / "writing_preferences.json", DEFAULT_WRITING_PREFERENCES)
    _ensure_legacy_alias(MEMORY_DIR / "rewrite_preferences.json", DEFAULT_WRITING_PREFERENCES)
    _ensure_json(MEMORY_DIR / "custom_vocabulary.json", DEFAULT_VOCABULARY)
    _ensure_json(MEMORY_DIR / "corrections.json", DEFAULT_CORRECTIONS)
    _ensure_json(MEMORY_DIR / "snippets.json", DEFAULT_SNIPPETS)
    _ensure_json(MEMORY_DIR / "active_project.json", DEFAULT_ACTIVE_PROJECT)
    _ensure_json(MEMORY_DIR / "forbidden_phrases.json", DEFAULT_FORBIDDEN)
    _ensure_json(PROJECTS_DIR / "_index.json", {"projects": ["general", "waky"]})
    ensure_project("general")
    ensure_project("waky")
    _seed_required_vocabulary()
    _seed_required_corrections()


def load_memory() -> dict:
    ensure_memory_files()
    active_project = get_active_project()
    return {
        "user_profile": _read_json(MEMORY_DIR / "user_profile.json", DEFAULT_USER_PROFILE),
        "writing_preferences": _read_json(MEMORY_DIR / "writing_preferences.json", DEFAULT_WRITING_PREFERENCES),
        "rewrite_preferences": _read_json(MEMORY_DIR / "writing_preferences.json", DEFAULT_WRITING_PREFERENCES),
        "custom_vocabulary": _read_json(MEMORY_DIR / "custom_vocabulary.json", DEFAULT_VOCABULARY),
        "corrections": _read_json(MEMORY_DIR / "corrections.json", DEFAULT_CORRECTIONS),
        "snippets": _read_json(MEMORY_DIR / "snippets.json", DEFAULT_SNIPPETS),
        "active_project": active_project,
        "active_project_data": _load_project(active_project),
        "forbidden_phrases": _read_json(MEMORY_DIR / "forbidden_phrases.json", DEFAULT_FORBIDDEN),
    }


def save_memory_section(section_name: str, data: dict) -> None:
    ensure_memory_files()
    allowed = {
        "user_profile": "user_profile.json",
        "writing_preferences": "writing_preferences.json",
        "custom_vocabulary": "custom_vocabulary.json",
        "corrections": "corrections.json",
        "active_project": "active_project.json",
        "forbidden_phrases": "forbidden_phrases.json",
    }
    filename = allowed.get(section_name)
    if not filename:
        raise ValueError(f"Unknown memory section: {section_name}")
    _write_json(MEMORY_DIR / filename, data)


def get_active_project() -> str:
    ensure_memory_files_shallow()
    data = _read_json(MEMORY_DIR / "active_project.json", DEFAULT_ACTIVE_PROJECT)
    return _slugify(data.get("active_project") or "general")


def set_active_project(project_name: str) -> None:
    project = _slugify(project_name or "general")
    ensure_project(project)
    _write_json(MEMORY_DIR / "active_project.json", {"active_project": project})


def ensure_project(project_name: str) -> None:
    project = _slugify(project_name or "general")
    project_dir = PROJECTS_DIR / project
    project_dir.mkdir(parents=True, exist_ok=True)
    context = DEFAULT_PROJECT_CONTEXT.get(project, [f"Project memory for {project}."])
    _ensure_text(project_dir / "project_context.md", "\n".join(f"- {line}" for line in context) + "\n")
    _ensure_text(project_dir / "project_summary.md", f"# {project} Summary\n\n")
    _ensure_json(project_dir / "vocabulary.json", {"items": []})
    _ensure_json(project_dir / "corrections.json", {"corrections": []})
    _ensure_text(project_dir / "notes.md", f"# {project} Notes\n\n")
    _ensure_json(project_dir / "rewrite_examples.json", {"examples": []})
    index_path = PROJECTS_DIR / "_index.json"
    index = _read_json(index_path, {"projects": []})
    projects = index.setdefault("projects", [])
    if project not in projects:
        projects.append(project)
        projects.sort()
        _write_json(index_path, index)


def get_rewrite_context(project_name: str | None = None) -> str:
    ensure_memory_files()
    project = _slugify(project_name or get_active_project())
    ensure_project(project)
    memory = load_memory()
    project_data = _load_project(project)
    preferences = memory.get("writing_preferences", {}).get("preferences", [])
    global_vocab = _vocab_terms(memory.get("custom_vocabulary", {}))
    project_vocab = _vocab_terms(project_data.get("vocabulary", {}))
    combined_vocab = list(dict.fromkeys(project_vocab + global_vocab))
    corrections = _correction_lines(memory.get("corrections", {})) + _correction_lines(project_data.get("corrections", {}))
    forbidden = memory.get("forbidden_phrases", {}).get("phrases", [])

    LOGGER.info("[MEMORY] context_loaded=true")
    LOGGER.info("[MEMORY] active_project=%s", project)
    LOGGER.info("[MEMORY] vocabulary_count=%s", len(combined_vocab))
    LOGGER.info("[MEMORY] corrections_count=%s", len(corrections))
    LOGGER.info("[MEMORY] project_context_used=true")

    return "\n".join(
        [
            "User writing preferences:",
            *_bullet_lines(preferences[:14]),
            "",
            f"Active project: {project}",
            "",
            "Project context:",
            *_compact_markdown(project_data.get("project_context", ""), 8),
            "",
            "Project summary:",
            *_compact_markdown(project_data.get("project_summary", ""), 5),
            "",
            "Project notes:",
            *_compact_markdown(project_data.get("notes", ""), 6),
            "",
            "Custom vocabulary:",
            ", ".join(combined_vocab[:80]),
            "",
            "Corrections:",
            *_bullet_lines(corrections[:30]),
            "",
            "Forbidden phrases:",
            *_bullet_lines(forbidden[:20]),
        ]
    ).strip()


def add_memory_note(text: str, project_name: str | None = None) -> None:
    text = text.strip()
    if not text:
        return
    project = _slugify(project_name or get_active_project())
    ensure_project(project)
    path = PROJECTS_DIR / project / "notes.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {stamp}: {text}\n")


def add_vocabulary_item(term: str, notes: str = "", project_name: str | None = None) -> None:
    term = term.strip()
    if not term:
        return
    if project_name:
        project = _slugify(project_name)
        ensure_project(project)
        path = PROJECTS_DIR / project / "vocabulary.json"
        data = _read_json(path, {"items": []})
    else:
        path = MEMORY_DIR / "custom_vocabulary.json"
        data = _read_json(path, DEFAULT_VOCABULARY)
    items = data.setdefault("items", [])
    if not any(str(item.get("term", "")).lower() == term.lower() for item in items if isinstance(item, dict)):
        items.append({"term": term, "notes": notes.strip()})
    words = data.setdefault("words", [])
    if term not in words:
        words.append(term)
    _write_json(path, data)


def add_correction(wrong: str, correct: str, note: str = "", project_name: str | None = None) -> None:
    wrong = wrong.strip()
    correct = correct.strip()
    if not wrong or not correct:
        return
    if project_name:
        project = _slugify(project_name)
        ensure_project(project)
        path = PROJECTS_DIR / project / "corrections.json"
        data = _read_json(path, {"corrections": []})
    else:
        path = MEMORY_DIR / "corrections.json"
        data = _read_json(path, DEFAULT_CORRECTIONS)
    corrections = data.setdefault("corrections", [])
    if not any(str(item.get("wrong", "")).lower() == wrong.lower() for item in corrections if isinstance(item, dict)):
        corrections.append({"wrong": wrong, "correct": correct, "note": note.strip()})
    _write_json(path, data)


def add_writing_preference(text: str) -> None:
    text = text.strip()
    if not text:
        return
    data = _read_json(MEMORY_DIR / "writing_preferences.json", DEFAULT_WRITING_PREFERENCES)
    preferences = data.setdefault("preferences", [])
    if text not in preferences:
        preferences.append(text)
    _write_json(MEMORY_DIR / "writing_preferences.json", data)


def add_preference(text: str) -> None:
    add_writing_preference(text)


def add_project_context(text: str, project_name: str | None = None) -> None:
    text = text.strip()
    if not text:
        return
    project = _slugify(project_name or get_active_project())
    ensure_project(project)
    with (PROJECTS_DIR / project / "project_context.md").open("a", encoding="utf-8") as handle:
        handle.write(f"- {text}\n")


def add_rewrite_example(input_text: str, output_text: str, command: str, project_name: str | None = None) -> None:
    project = _slugify(project_name or get_active_project())
    ensure_project(project)
    path = PROJECTS_DIR / project / "rewrite_examples.json"
    data = _read_json(path, {"examples": []})
    data.setdefault("examples", []).append(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "command": command.strip(),
            "input": input_text.strip(),
            "output": output_text.strip(),
        }
    )
    _write_json(path, data)


def summarize_project_memory(project_name: str) -> None:
    project = _slugify(project_name or get_active_project())
    ensure_project(project)
    project_data = _load_project(project)
    note_lines = _compact_markdown(project_data.get("notes", ""), 20)
    context_lines = _compact_markdown(project_data.get("project_context", ""), 12)
    summary = [f"# {project} Summary", "", "## Context", *context_lines, "", "## Recent Notes", *note_lines, ""]
    (PROJECTS_DIR / project / "project_summary.md").write_text("\n".join(summary), encoding="utf-8")


def get_forbidden_phrases() -> list[str]:
    ensure_memory_files()
    data = _read_json(MEMORY_DIR / "forbidden_phrases.json", DEFAULT_FORBIDDEN)
    return [str(phrase) for phrase in data.get("phrases", []) if str(phrase).strip()]


def load_snippets() -> dict[str, Any]:
    ensure_memory_files()
    return _read_json(MEMORY_DIR / "snippets.json", DEFAULT_SNIPPETS)


def memory_summary(settings: dict | None = None) -> dict[str, Any]:
    memory_enabled = True
    if isinstance(settings, dict):
        memory_enabled = bool(settings.get("command_processing", {}).get("local_memory_enabled", True))
    memory = load_memory()
    project = get_active_project()
    project_dir = PROJECTS_DIR / project
    return {
        "memory_enabled": memory_enabled,
        "active_project": project,
        "custom_vocabulary_count": len(_vocab_terms(memory.get("custom_vocabulary", {}))),
        "corrections_count": len(memory.get("corrections", {}).get("corrections", [])),
        "preferences_count": len(memory.get("writing_preferences", {}).get("preferences", [])),
        "forbidden_phrases_count": len(memory.get("forbidden_phrases", {}).get("phrases", [])),
        "project_summary_exists": (project_dir / "project_summary.md").exists(),
        "memory_dir": str(MEMORY_DIR),
    }


def clear_memory() -> None:
    for path in (
        MEMORY_DIR / "user_profile.json",
        MEMORY_DIR / "writing_preferences.json",
        MEMORY_DIR / "rewrite_preferences.json",
        MEMORY_DIR / "custom_vocabulary.json",
        MEMORY_DIR / "corrections.json",
        MEMORY_DIR / "active_project.json",
        MEMORY_DIR / "forbidden_phrases.json",
    ):
        if path.exists():
            path.unlink()
    ensure_memory_files()


def ensure_memory_files_shallow() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_json(MEMORY_DIR / "active_project.json", DEFAULT_ACTIVE_PROJECT)


def _load_project(project: str) -> dict[str, Any]:
    ensure_project(project)
    project_dir = PROJECTS_DIR / project
    return {
        "project_context": _read_text(project_dir / "project_context.md"),
        "project_summary": _read_text(project_dir / "project_summary.md"),
        "vocabulary": _read_json(project_dir / "vocabulary.json", {"items": []}),
        "corrections": _read_json(project_dir / "corrections.json", {"corrections": []}),
        "notes": _read_text(project_dir / "notes.md"),
        "rewrite_examples": _read_json(project_dir / "rewrite_examples.json", {"examples": []}),
    }


def _seed_required_vocabulary() -> None:
    return


def _seed_required_corrections() -> None:
    return


def _vocab_terms(data: dict[str, Any]) -> list[str]:
    terms = []
    for item in data.get("items", []):
        if isinstance(item, dict) and str(item.get("term", "")).strip():
            terms.append(str(item["term"]).strip())
    for word in data.get("words", []):
        if str(word).strip():
            terms.append(str(word).strip())
    seen = set()
    unique = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def _correction_lines(data: dict[str, Any]) -> list[str]:
    lines = []
    for item in data.get("corrections", []):
        if isinstance(item, dict):
            wrong = str(item.get("wrong", "")).strip()
            correct = str(item.get("correct", "")).strip()
            note = str(item.get("note", "")).strip()
            if wrong and correct:
                lines.append(f"{wrong} -> {correct}" + (f" ({note})" if note else ""))
    return lines


def _compact_markdown(text: str, limit: int) -> list[str]:
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            lines.append(clean)
        if len(lines) >= limit:
            break
    return lines or ["- No saved context yet."]


def _slugify(project_name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(project_name).strip().lower()).strip("-")
    return value or "general"


def _bullet_lines(values: list[Any]) -> list[str]:
    return [f"- {str(value)}" for value in values if str(value).strip()]


def _ensure_json(path: Path, data: dict[str, Any]) -> None:
    if not path.exists():
        _write_json(path, data)


def _ensure_legacy_alias(path: Path, data: dict[str, Any]) -> None:
    if not path.exists():
        _write_json(path, data)


def _ensure_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.warning("[MEMORY] could not read %s; repairing with defaults", path, exc_info=True)
        _write_json(path, fallback)
        return json.loads(json.dumps(fallback))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)
