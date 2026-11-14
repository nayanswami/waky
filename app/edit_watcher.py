"""Learn from your fixes by itself: after Waky pastes, watch the focused text field for a short while.

If you change a word in what Waky just wrote, the edited text is handed to a callback (which learns the fix and shows a notice).
Uses Windows UI Automation to read the field. Apps that do not expose their text are simply not watched.
Nothing is stored here and nothing leaves the PC. Password fields are never read.
"""
from __future__ import annotations

import difflib
import logging
import threading
import time
from typing import Callable

LOGGER = logging.getLogger("waky")

UIA_VALUE_PATTERN = 10002
UIA_TEXT_PATTERN = 10014
WATCH_SECONDS = 45
POLL_SECONDS = 0.8
SETTLE_POLLS = 2          # the edit must stay the same this many polls before it counts
MAX_LEN = 3000


class _Reader:
    """Reads the text of the focused element. Created on the thread that uses it."""

    def __init__(self) -> None:
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA

        self.UIA = UIA
        self.uia = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}", interface=UIA.IUIAutomation)

    def focused(self):
        try:
            return self.uia.GetFocusedElement()
        except Exception:
            return None

    def key(self, el) -> tuple:
        try:
            return tuple(el.GetRuntimeId())
        except Exception:
            return ()

    def is_password(self, el) -> bool:
        try:
            return bool(el.CurrentIsPassword)
        except Exception:
            return False

    def text(self, el) -> str | None:
        UIA = self.UIA
        try:
            pattern = el.GetCurrentPattern(UIA_TEXT_PATTERN)
            if pattern:
                return pattern.QueryInterface(UIA.IUIAutomationTextPattern).DocumentRange.GetText(MAX_LEN * 4)
        except Exception:
            pass
        try:
            pattern = el.GetCurrentPattern(UIA_VALUE_PATTERN)
            if pattern:
                return pattern.QueryInterface(UIA.IUIAutomationValuePattern).CurrentValue
        except Exception:
            pass
        return None


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class EditWatcher:
    """watch(pasted, on_edit): on_edit(pasted, edited) is called once if the user fixes the pasted text."""

    def __init__(self) -> None:
        self._token = 0
        self._lock = threading.Lock()
        self.available = True

    def watch(self, pasted: str, on_edit: Callable[[str, str], None]) -> None:
        if not self.available or not pasted.strip() or len(pasted) > MAX_LEN:
            return
        with self._lock:
            self._token += 1
            token = self._token
        threading.Thread(target=self._run, args=(token, pasted, on_edit), daemon=True, name="waky-edit-watch").start()

    def warm(self) -> None:
        """Build the UI Automation bindings once at start-up so the first watch is not late."""
        try:
            _Reader()
        except Exception:
            LOGGER.info("[WATCH] UI Automation unavailable", exc_info=True)
            self.available = False

    def stop(self) -> None:
        with self._lock:
            self._token += 1

    def _current(self, token: int) -> bool:
        return token == self._token

    def _run(self, token: int, pasted: str, on_edit: Callable[[str, str], None]) -> None:
        try:
            reader = _Reader()
        except Exception:
            LOGGER.info("[WATCH] UI Automation unavailable; automatic learning is off", exc_info=True)
            self.available = False
            return
        try:
            pasted_n = _norm(pasted).strip()
            element, snap, start = None, "", -1
            for _ in range(6):   # the paste lands a moment after the keystroke
                time.sleep(0.35)
                if not self._current(token):
                    return
                element = reader.focused()
                if element is None or reader.is_password(element):
                    return
                text = reader.text(element)
                if text is not None:
                    snap = _norm(text)
                    start = snap.rfind(pasted_n)
                    if start >= 0:
                        break
            if start < 0 or element is None:
                return   # this app does not expose its text, or the paste went elsewhere
            prefix, suffix = snap[:start], snap[start + len(pasted_n):]
            focus_key = reader.key(element)
            last_edit, stable, deadline = None, 0, time.monotonic() + WATCH_SECONDS
            while time.monotonic() < deadline and self._current(token):
                time.sleep(POLL_SECONDS)
                now = reader.focused()
                if now is None or (focus_key and reader.key(now) != focus_key):
                    if last_edit is None:
                        return   # moved to another field before editing anything
                    now = element
                text = reader.text(now)
                if text is None:
                    continue
                current = _norm(text)
                if current == snap or not (current.startswith(prefix) and current.endswith(suffix)) or len(current) < len(prefix) + len(suffix):
                    continue
                edited = current[len(prefix): len(current) - len(suffix)].strip() if suffix else current[len(prefix):].strip()
                if not edited or edited == pasted_n:
                    continue
                if difflib.SequenceMatcher(a=pasted_n.lower(), b=edited.lower(), autojunk=False).ratio() < 0.55:
                    continue   # rewritten, not corrected
                stable = stable + 1 if edited == last_edit else 1
                last_edit = edited
                if stable >= SETTLE_POLLS:
                    on_edit(pasted_n, edited)
                    return
        except Exception:
            LOGGER.info("[WATCH] stopped", exc_info=True)
        finally:
            try:
                import comtypes

                comtypes.CoUninitialize()
            except Exception:
                pass
