"""Quick checks that tell a new user (and us) whether Waky can work on this PC, with a fix hint for each."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass
class Check:
    key: str
    name: str
    status: str   # "ok" | "warn" | "fail"
    detail: str
    fix: str = ""  # an ms-settings: URI or empty


def _mic_devices() -> Check:
    try:
        import sounddevice as sd

        inputs = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
    except Exception as exc:
        return Check("mic", "Microphone", "fail", f"Audio system not available ({exc.__class__.__name__}).")
    if not inputs:
        return Check("mic", "Microphone", "fail", "No microphone found. Plug one in or enable it in Windows sound settings.", "ms-settings:sound")
    return Check("mic", "Microphone", "ok", f"{len(inputs)} input device{'s' if len(inputs) != 1 else ''} found.")


def _mic_permission() -> Check:
    if sys.platform != "win32":
        return Check("perm", "Microphone access", "ok", "Not applicable.")
    try:
        import winreg

        base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
        states = []
        for sub in ("", r"\NonPackaged"):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + sub) as key:
                    states.append(str(winreg.QueryValueEx(key, "Value")[0]))
            except FileNotFoundError:
                continue
        if any(s.lower() == "deny" for s in states):
            return Check(
                "perm", "Microphone access", "fail",
                "Windows is blocking microphone access for desktop apps. Turn on 'Let desktop apps access your microphone'.",
                "ms-settings:privacy-microphone",
            )
        return Check("perm", "Microphone access", "ok", "Windows allows desktop apps to use the microphone.")
    except Exception:
        return Check("perm", "Microphone access", "warn", "Could not read the Windows privacy setting.")


def _hotkeys() -> Check:
    try:
        from pynput import keyboard  # noqa: F401

        return Check("keys", "Global hotkeys", "ok", "Hotkey listener is available.")
    except Exception as exc:
        return Check("keys", "Global hotkeys", "fail", f"Hotkeys unavailable ({exc.__class__.__name__}). Security software may be blocking keyboard hooks.")


def _clipboard() -> Check:
    try:
        import pyperclip

        pyperclip.paste()
        return Check("clip", "Paste into apps", "ok", "Clipboard access works.")
    except Exception:
        return Check("clip", "Paste into apps", "warn", "Clipboard access failed. Auto-paste may not work in some apps.")


def _internet() -> Check:
    try:
        req = Request("https://api.groq.com/openai/v1/models", headers={"User-Agent": "Waky/1.0"}, method="GET")
        try:
            urlopen(req, timeout=5)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in (401, 403):  # reachable; just no key in this request
                return Check("net", "Internet to Groq", "ok", "Groq is reachable.")
            raise
        return Check("net", "Internet to Groq", "ok", "Groq is reachable.")
    except Exception:
        return Check("net", "Internet to Groq", "warn", "Could not reach Groq. Cloud mode needs internet; local mode works offline.")


def run_all() -> list[Check]:
    return [_mic_devices(), _mic_permission(), _hotkeys(), _clipboard(), _internet()]
