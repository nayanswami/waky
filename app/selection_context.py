from __future__ import annotations

import logging
import time

import pyautogui
import pyperclip


LOGGER = logging.getLogger("waky")


def get_selected_text_safely() -> str:
    """
    Attempts to capture currently selected text from the active app.
    Returns selected text or empty string.
    Must preserve the user's clipboard.
    """
    LOGGER.info("[SELECTION] capture_attempt=true")
    old_clipboard = ""
    selected_text = ""
    old_read_ok = False
    try:
        try:
            old_clipboard = pyperclip.paste() or ""
            old_read_ok = True
        except Exception:
            LOGGER.warning("[SELECTION] clipboard_read_failed", exc_info=True)

        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.18)

        try:
            selected_text = pyperclip.paste() or ""
        except Exception:
            LOGGER.warning("[SELECTION] selected_clipboard_read_failed", exc_info=True)
            selected_text = ""

        if not selected_text.strip() or (old_read_ok and selected_text == old_clipboard):
            LOGGER.info("[SELECTION] selected_text_detected=false")
            LOGGER.info("[SELECTION] selected_text_length=0")
            return ""

        LOGGER.info("[SELECTION] selected_text_detected=true")
        LOGGER.info("[SELECTION] selected_text_length=%s", len(selected_text))
        return selected_text
    except Exception:
        LOGGER.warning("[SELECTION] capture_failed", exc_info=True)
        return ""
    finally:
        if old_read_ok:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                LOGGER.warning("[SELECTION] clipboard_restore_failed", exc_info=True)
