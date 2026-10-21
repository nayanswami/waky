from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

from pynput import keyboard, mouse


# Set while the settings UI is recording a new hotkey, so the live listener ignores key presses.
CAPTURING = threading.Event()

MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")


def mouse_token(button) -> str | None:
    """Middle and the two side buttons can be hotkeys; left and right never can."""
    name = getattr(button, "name", "")
    return {"middle": "mouse_middle", "x1": "mouse_x1", "x2": "mouse_x2"}.get(name)


def key_token(key) -> str:
    if isinstance(key, str):  # already a token (mouse buttons)
        return key
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return "ctrl"
    if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
        return "win"
    if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
        return "shift"
    if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, getattr(keyboard.Key, "alt_gr", None)):
        return "alt"
    if key == keyboard.Key.space:
        return "space"
    if key == keyboard.Key.esc:
        return "esc"
    vk = getattr(key, "vk", None)
    if vk is not None:  # raw virtual-key codes: stable even with Ctrl held (where .char becomes a control code)
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if vk in (0x5B, 0x5C):
            return "win"
        if vk == 0x20:
            return "space"
    if hasattr(key, "name") and key.name:
        return key.name.lower()
    try:
        return key.char.lower()
    except Exception:
        return str(key).lower()


PRETTY = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "space": "Space", "esc": "Esc",
          "mouse_middle": "Middle Click", "mouse_x1": "Mouse Back", "mouse_x2": "Mouse Forward"}


def pretty_combo(combo: str) -> str:
    """'<ctrl>+<win>' -> 'Ctrl + Win'."""
    parts = [p.strip().strip("<>").lower() for p in combo.split("+") if p.strip()]
    return " + ".join(PRETTY.get(p, p.upper() if len(p) <= 3 else p.title()) for p in parts)


def combo_from_tokens(tokens) -> str:
    """Format pressed key tokens as a settings string, modifiers first: '<ctrl>+<win>'."""
    tokens = set(tokens)
    ordered = [m for m in MODIFIER_ORDER if m in tokens] + sorted(tokens - set(MODIFIER_ORDER))
    return "+".join(f"<{token}>" for token in ordered)


def is_safe_combo(tokens) -> bool:
    """A usable push-to-talk combo needs a modifier or a function key, so normal typing never triggers it."""
    tokens = set(tokens)
    if tokens & set(MODIFIER_ORDER) or any(token.startswith("mouse_") for token in tokens):
        return True
    return any(token.startswith("f") and token[1:].isdigit() for token in tokens)


class HotkeyManager:
    def __init__(
        self,
        settings: dict,
        logger: logging.Logger,
        on_push_start: Callable[[], bool],
        on_push_stop: Callable[[], None],
        on_toggle: Callable[[], None],
        on_cancel: Callable[[], None],
        on_error: Callable[[str], None],
        on_paste_last: Callable[[], None] | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.on_push_start = on_push_start
        self.on_push_stop = on_push_stop
        self.on_toggle = on_toggle
        self.on_cancel = on_cancel
        self.on_error = on_error
        self.on_paste_last = on_paste_last
        self.paste_last_down = False
        self.listener: keyboard.Listener | None = None
        self.mouse_listener: mouse.Listener | None = None
        self.current_keys: set[str] = set()
        self.push_active = False
        self.pending_push_timer: threading.Timer | None = None
        self.toggle_combo_was_down = False
        self.lock = threading.Lock()

    def start(self) -> None:
        try:
            self.stop()
            self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.listener.start()
            if self._uses_mouse():
                kwargs = {"win32_event_filter": self._mouse_filter} if sys.platform == "win32" else {"on_click": self._on_click}
                self.mouse_listener = mouse.Listener(**kwargs)
                self.mouse_listener.start()
            self.logger.info(
                "Hotkey listener started. push_to_talk=%s backup=%s toggle=%s cancel=%s",
                self.settings.get("hotkeys", {}).get("push_to_talk"),
                self.settings.get("hotkeys", {}).get("push_to_talk_backup"),
                self.settings.get("hotkeys", {}).get("toggle_recording"),
                self.settings.get("hotkeys", {}).get("cancel"),
            )
        except Exception as exc:
            self.logger.exception("Hotkey registration failed")
            self.on_error(f"Hotkey error: {exc}. Try F8/F9 in settings.")

    def stop(self) -> None:
        for name in ("listener", "mouse_listener"):
            listener = getattr(self, name)
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
                setattr(self, name, None)

    def _configured_tokens(self) -> set[str]:
        tokens: set[str] = set()
        for name in ("push_to_talk", "push_to_talk_backup", "toggle_recording", "cancel", "paste_last"):
            tokens |= self._parse_combo(self.settings.get("hotkeys", {}).get(name, ""))
        return tokens

    def _uses_mouse(self) -> bool:
        return any(token.startswith("mouse_") for token in self._configured_tokens())

    def _on_click(self, _x, _y, button, pressed) -> None:  # non-Windows fallback
        token = mouse_token(button)
        if token:
            (self._press if pressed else self._release)(token)

    def _mouse_filter(self, msg, data):
        """Windows: handle middle/side buttons ourselves and swallow the ones used as hotkeys so they do not also navigate back."""
        if msg in (0x207, 0x208):
            token, down = "mouse_middle", msg == 0x207
        elif msg in (0x20B, 0x20C):
            token, down = ("mouse_x1" if ((data.mouseData >> 16) & 0xFFFF) == 1 else "mouse_x2"), msg == 0x20B
        else:
            return True
        if CAPTURING.is_set():
            return True
        (self._press if down else self._release)(token)
        if token in self._configured_tokens() and self.mouse_listener is not None:
            self.mouse_listener.suppress_event()
        return False

    def reload(self, settings: dict) -> None:
        self.settings = settings
        self.start()

    def _on_press(self, key) -> None:
        self._press(self._token(key))

    def _press(self, token: str) -> None:
        if CAPTURING.is_set():
            return
        with self.lock:
            self.current_keys.add(token)
            if self._combo_matches("cancel"):
                self.logger.info("Cancel hotkey pressed")
                self.on_cancel()
                return
            if self.on_paste_last and self._combo_matches("paste_last"):
                self._cancel_pending_push()
                if not self.paste_last_down:
                    self.paste_last_down = True
                    self.logger.info("Paste-last hotkey pressed")
                    self.on_paste_last()
                return
            if self._combo_matches("toggle_recording"):
                self._cancel_pending_push()
                if not self.toggle_combo_was_down:
                    self.toggle_combo_was_down = True
                    self.logger.info("Toggle hotkey pressed")
                    self.on_toggle()
                return
            if self._push_combo_matches() and not self.push_active:
                self.logger.info("Push-to-talk key pressed")
                self._schedule_push_start()

    def _on_release(self, key) -> None:
        self._release(self._token(key))

    def _release(self, token: str) -> None:
        if CAPTURING.is_set():
            self.current_keys.clear()
            return
        with self.lock:
            was_push_active = self.push_active
            self.current_keys.discard(token)
            if not self._push_combo_matches():
                self._cancel_pending_push()
            if not self._combo_matches("toggle_recording"):
                self.toggle_combo_was_down = False
            if not self._combo_matches("paste_last"):
                self.paste_last_down = False
            if was_push_active and not self._push_combo_matches():
                self.push_active = False
                self.logger.info("Push-to-talk key released")
                self.on_push_stop()

    def _schedule_push_start(self) -> None:
        if self.pending_push_timer or self.push_active:
            return
        self.pending_push_timer = threading.Timer(0.06, self._fire_push_start)
        self.pending_push_timer.daemon = True
        self.pending_push_timer.start()

    def _fire_push_start(self) -> None:
        with self.lock:
            self.pending_push_timer = None
            if self.push_active or self._combo_matches("toggle_recording") or not self._push_combo_matches():
                return
            self.push_active = True
            try:
                accepted = self.on_push_start()
                if accepted is False:
                    self.push_active = False
            except Exception:
                self.logger.exception("Push-to-talk start callback failed")
                self.push_active = False

    def _cancel_pending_push(self) -> None:
        if self.pending_push_timer:
            self.pending_push_timer.cancel()
            self.pending_push_timer = None

    def _push_combo_matches(self) -> bool:
        return self._combo_matches("push_to_talk") or self._combo_matches("push_to_talk_backup")

    def _combo_matches(self, name: str) -> bool:
        combo = self.settings.get("hotkeys", {}).get(name, "")
        wanted = self._parse_combo(combo)
        return bool(wanted) and wanted.issubset(self.current_keys)

    def _parse_combo(self, combo: str) -> set[str]:
        parts = [part.strip().strip("<>").lower() for part in combo.split("+") if part.strip()]
        normalized = set()
        for part in parts:
            aliases = {"cmd": "win", "windows": "win", "control": "ctrl", "esc": "esc", "escape": "esc"}
            normalized.add(aliases.get(part, part))
        return normalized

    def _token(self, key) -> str:
        return key_token(key)
