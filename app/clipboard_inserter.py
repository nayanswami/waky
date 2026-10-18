from __future__ import annotations

import logging
import time

import pyautogui
import pyperclip


class ClipboardInserter:
    def __init__(self, settings: dict, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger

    def paste_text(self, text: str) -> bool:
        if not self.settings.get("output", {}).get("auto_paste", True):
            self.logger.info("Auto-paste disabled; copying text only")
            pyperclip.copy(text)
            return False
        old_clipboard = None
        preserve = self.settings.get("output", {}).get("preserve_clipboard", True)
        try:
            self.logger.info("Paste start preserve_clipboard=%s chars=%s", preserve, len(text))
            if preserve:
                try:
                    old_clipboard = pyperclip.paste()
                except Exception:
                    old_clipboard = None
            pyperclip.copy(text)
            time.sleep(0.08)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.25)
            if preserve and old_clipboard is not None:
                pyperclip.copy(old_clipboard)
            self.logger.info("Paste success")
            return True
        except Exception:
            self.logger.exception("Paste failed; final text left on clipboard")
            try:
                pyperclip.copy(text)
            except Exception:
                self.logger.exception("Could not copy final text to clipboard")
            return False
