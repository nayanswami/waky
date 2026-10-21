from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit

from . import hotkeys


class HotkeyEdit(QLineEdit):
    """Click, then press the key combination you want. Replaces typing '<ctrl>+<win>' by hand."""

    _live = Signal(str, bool)  # (text, finished)

    def __init__(self, allow_single: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.allow_single = allow_single
        self._raw = ""
        self.setObjectName("hotkey")
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setReadOnly(True)
        self.setPlaceholderText("Click to record")
        self._listener = None
        self._mouse_listener = None
        self._previous = ""
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._cancel)
        self._live.connect(self._on_live)

    def text(self) -> str:  # the stored form, e.g. "<ctrl>+<win>"
        return self._raw

    def setText(self, value: str) -> None:  # shown prettily, stored raw
        if not value:
            self._raw = ""
            super().setText("")
        elif value.startswith("<") or "+" in value:
            self._raw = value
            super().setText(hotkeys.pretty_combo(value))
        else:  # transient prompts like "Press your keys..."
            super().setText(value)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if self._listener is None:
            self._start()

    def _start(self) -> None:
        from pynput import keyboard

        self._previous = self._raw
        super().setText("Press your keys...")
        hotkeys.CAPTURING.set()
        pressed: set[str] = set()
        best: set[str] = set()

        def on_press(key) -> None:
            pressed.add(hotkeys.key_token(key))
            if len(pressed) >= len(best):
                best.clear()
                best.update(pressed)
            self._live.emit(hotkeys.combo_from_tokens(best), False)

        def on_release(key):
            pressed.discard(hotkeys.key_token(key))
            if not pressed:
                ok = self.allow_single or hotkeys.is_safe_combo(best)
                self._live.emit(hotkeys.combo_from_tokens(best) if ok else "", True)
                return False
            return None

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()
        from pynput import mouse

        def on_click(_x, _y, button, down) -> None:
            token = hotkeys.mouse_token(button)
            if token:
                (on_press if down else on_release)(token)

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()
        self._timeout.start(10_000)

    def _on_live(self, text: str, finished: bool) -> None:
        if not finished:
            self.setText(text)
            return
        self._stop()
        if text:
            self.setText(text)
        else:
            self.setText(self._previous)
            self.setToolTip("Use a modifier (Ctrl, Alt, Shift, Win), a function key like F8, or a middle/side mouse button.")

    def _cancel(self) -> None:
        self._stop()
        self.setText(self._previous)

    def _stop(self) -> None:
        self._timeout.stop()
        hotkeys.CAPTURING.clear()
        for name in ("_listener", "_mouse_listener"):
            listener = getattr(self, name)
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
                setattr(self, name, None)
