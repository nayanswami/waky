"""Per-app profiles: the app you are typing into decides how Waky writes (chat stays casual, email stays polished, code stays literal)."""
from __future__ import annotations

import copy
import os
import sys
from dataclasses import dataclass

PRESETS = (
    {
        "name": "Chat apps",
        "match": "slack.exe, discord.exe, whatsapp.exe, telegram.exe, teams.exe, ms-teams.exe, whatsapp web",
        "instruction": "This is a chat message. Keep it short, natural and casual. No greeting, no sign-off, no subject line.",
        "light": False,
    },
    {
        "name": "Email",
        "match": "outlook.exe, olk.exe, thunderbird.exe, gmail, outlook",
        "instruction": "This is an email. Use clear, polite, complete sentences with a professional but warm tone. Do not add a subject line unless I ask for one.",
        "light": False,
    },
    {
        "name": "Code and terminal",
        "match": "code.exe, cursor.exe, devenv.exe, pycharm64.exe, windowsterminal.exe, cmd.exe, powershell.exe, pwsh.exe",
        "instruction": "Keep technical terms, identifiers, file names and commands exactly as spoken.",
        "light": True,
    },
    {
        "name": "Notes and documents",
        "match": "notion.exe, winword.exe, onenote.exe, obsidian.exe, notepad.exe",
        "instruction": "Write clear, well-structured prose with correct punctuation.",
        "light": False,
    },
)


@dataclass(frozen=True)
class AppInfo:
    exe: str      # lower case, e.g. "slack.exe"
    title: str    # window title


def foreground_app() -> AppInfo | None:
    """The app that currently has keyboard focus (Waky's own windows are ignored)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return None
        title_buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title_buf, 256)
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        exe = ""
        if handle:
            try:
                size = wintypes.DWORD(520)
                buf = ctypes.create_unicode_buffer(520)
                if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    exe = os.path.basename(buf.value).lower()
            finally:
                kernel32.CloseHandle(handle)
        return AppInfo(exe, title_buf.value) if exe else None
    except Exception:
        return None


def _patterns(profile: dict) -> list[str]:
    raw = str(profile.get("match", ""))
    return [p.strip().lower() for p in raw.replace(";", ",").replace("\n", ",").split(",") if p.strip()]


def matches(profile: dict, app: AppInfo) -> bool:
    exe, title = app.exe.lower(), app.title.lower()
    stem = exe[:-4] if exe.endswith(".exe") else exe
    for pattern in _patterns(profile):
        if pattern == exe or pattern == stem:
            return True
        if not pattern.endswith(".exe") and pattern in title:   # text from the window title, e.g. "gmail"
            return True
    return False


def match_profile(settings: dict, app: AppInfo | None) -> dict | None:
    cfg = settings.get("app_profiles", {}) if isinstance(settings, dict) else {}
    if not app or not cfg.get("enabled", True):
        return None
    for profile in cfg.get("items", []):
        if profile.get("enabled", True) and matches(profile, app):
            return profile
    return None


def apply_profile(settings: dict, profile: dict | None) -> dict:
    """Settings as they should be for this dictation. The stored settings are never modified."""
    if not profile:
        return settings
    run = dict(settings)
    options = copy.copy(settings.get("command_processing", {}))
    base = str(options.get("custom_instructions", "")).strip()
    extra = str(profile.get("instruction", "")).strip()
    name = str(profile.get("name", "this app")).strip() or "this app"
    if extra:
        options["custom_instructions"] = (base + "\n\n" if base else "") + f"While writing in {name}: {extra}"
    if profile.get("light"):
        options["command_rewrite_engine"] = "rule_based_only"
        options["auto_translate_to_english"] = False
    run["command_processing"] = options
    return run
