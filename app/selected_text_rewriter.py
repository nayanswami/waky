from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

import pyautogui
import pyperclip

from .command_processor import process_text_with_context


LOGGER = logging.getLogger("waky")


@dataclass
class SelectedTextCapture:
    selected_text: str
    previous_clipboard: str
    had_clipboard: bool


def capture_selected_text_safely(preserve_clipboard: bool = True, timeout_ms: int = 250) -> SelectedTextCapture | None:
    """
    Copy the active selection into memory without permanently changing clipboard
    where possible. Returns None when no selected text is detected.
    """
    old_clipboard = ""
    old_read_ok = False
    try:
        try:
            old_clipboard = pyperclip.paste() or ""
            old_read_ok = True
            LOGGER.info("[SELECTED_CAPTURE] clipboard_before_length=%s", len(old_clipboard))
        except Exception:
            LOGGER.warning("[SELECTED_CAPTURE] clipboard_read_failed", exc_info=True)

        sentinel = f"__WAKY_NO_SELECTION_{uuid.uuid4().hex}__"
        try:
            pyperclip.copy(sentinel)
            time.sleep(0.03)
        except Exception:
            LOGGER.warning("[SELECTED_CAPTURE] clipboard_sentinel_failed", exc_info=True)

        pyautogui.hotkey("ctrl", "c")
        time.sleep(max(0.05, timeout_ms / 1000.0))
        selected_text = pyperclip.paste() or ""
        LOGGER.info("[SELECTED_CAPTURE] clipboard_after_length=%s", len(selected_text))

        if not selected_text.strip() or selected_text == sentinel:
            LOGGER.info("[SELECTED_CAPTURE] selected_text_detected=false")
            return None

        # If text is unchanged, it may still be a valid selection that already
        # matched the clipboard. Accept it; no-selection fallback remains safe.
        LOGGER.info("[SELECTED_CAPTURE] selected_text_detected=true")
        LOGGER.info("[SELECTED_REWRITE] selected_text_length=%s", len(selected_text))
        return SelectedTextCapture(selected_text=selected_text, previous_clipboard=old_clipboard, had_clipboard=old_read_ok)
    except Exception:
        LOGGER.warning("[SELECTED_REWRITE ERROR] capture_failed", exc_info=True)
        return None
    finally:
        if preserve_clipboard and old_read_ok:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                LOGGER.warning("[SELECTED_CAPTURE] clipboard_restore_failed", exc_info=True)


def capture_selected_text(preserve_clipboard: bool = True, wait_seconds: float = 0.22) -> str:
    capture = capture_selected_text_safely(preserve_clipboard, int(wait_seconds * 1000))
    return capture.selected_text if capture else ""


def rewrite_selected_text(selected_text: str, instruction_text: str, settings: dict | None = None, custom_commands: dict | None = None) -> str:
    return process_text_with_context(selected_text, instruction_text, settings, custom_commands)
