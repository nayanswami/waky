from __future__ import annotations

import threading

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import QTimer

from . import hotkeys, llm_engine, pill_styles, system_check
from .ui_illustrations import Illustration
from .ios_widgets import AnimatedStack, IOSSwitch, PillPreview, StepDots, StyleCard
from . import ios_theme
from .ui_widgets import HotkeyEdit
from .utils import asset_path

GROQ_KEYS_URL = "https://console.groq.com/keys"
SWATCHES = (("#2E62FF", "Waky blue"), ("#32ADE6", "Sky"), ("#5E5CE6", "Indigo"), ("#FF375F", "Pink"), ("#FF9F0A", "Orange"), ("#30D158", "Green"), ("#FFFFFF", "White"))


class ChoiceCard(QFrame):
    """A big selectable card (radio behaviour handled by the wizard)."""

    chosen = Signal()

    def __init__(self, title: str, body: str, badge: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("styleCard")
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(4)
        top = QHBoxLayout()
        head = QLabel(title)
        head.setStyleSheet("font-size:17px;font-weight:700;")
        top.addWidget(head)
        if badge:
            tag = QLabel(badge)
            tag.setObjectName("ok")
            top.addWidget(tag)
        top.addStretch()
        lay.addLayout(top)
        text = QLabel(body)
        text.setObjectName("sub")
        text.setWordWrap(True)
        lay.addWidget(text)
        self.setProperty("selected", False)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, on: bool) -> None:
        self._checked = on
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e) -> None:
        self.chosen.emit()
        super().mousePressEvent(e)


class OnboardingWizard(QDialog):
    settings_applied = Signal()   # emitted whenever a step has written new settings
    finished_setup = Signal(bool)  # True when the user wants Settings opened afterwards
    _verify_done = Signal(bool, str)
    _checks_done = Signal(object)

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Welcome to Waky")
        self.setFixedSize(640, 820)
        fb = config_manager.settings.get("floating_bar", {})
        self.cloud = True
        self.style_key = pill_styles.get_style(fb.get("style")).key
        self.accent = str(fb.get("accent") or pill_styles.DEFAULT_ACCENT)
        self.size_pct = int(fb.get("size", 100))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        card = QFrame()
        card.setObjectName("wizardCard")
        outer.addWidget(card)
        root = QVBoxLayout(card)
        root.setContentsMargins(30, 22, 30, 24)
        root.setSpacing(0)

        head = QHBoxLayout()
        self.step_label = QLabel("")
        self.step_label.setObjectName("caption")
        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("plain")
        self.skip_button.clicked.connect(self._skip)
        head.addWidget(self.step_label)
        head.addStretch()
        head.addWidget(self.skip_button)
        root.addLayout(head)
        root.addSpacing(6)
        self.illus = Illustration()
        root.addWidget(self.illus)
        root.addSpacing(16)
        self.stack = AnimatedStack()
        root.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 14, 0, 0)
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("plain")
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("primary")
        self.next_button.setMinimumWidth(150)
        self.next_button.setMinimumHeight(40)
        self.dots = StepDots(8)
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        nav.addWidget(self.dots)
        nav.addStretch()
        nav.addWidget(self.back_button)
        nav.addWidget(self.next_button)
        root.addLayout(nav)

        self._verify_timer = QTimer(self)
        self._verify_timer.setSingleShot(True)
        self._verify_timer.timeout.connect(self._auto_verify)

        self.pages = [
            self._welcome_page(), self._engine_page(), self._key_page(), self._hotkey_page(),
            self._style_page(), self._check_page(), self._try_page(), self._done_page(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        self._verify_done.connect(self._on_verified)
        self._checks_done.connect(self._on_checks)
        self.index = 0
        self._update_nav()
        self.illus.configure(engine="cloud")

    # ---------- pages ----------

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("title")
        heading.setStyleSheet("font-size:28px;font-weight:800;")
        sub = QLabel(subtitle)
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(8)
        return page, layout

    def _welcome_page(self) -> QWidget:
        page, layout = self._page("Talk. Waky writes it.", "Hold a key, speak naturally, and finished text appears in any app. Setup takes about two minutes.")
        layout.insertSpacing(0, 10)
        for text in ("Push-to-talk in any text field", "Filler words and Hinglish become clean writing", "Your key, your PC. Nothing is sold or stored by us"):
            row = QLabel("\u2713  " + text)
            row.setStyleSheet("font-size:14px;")
            layout.addWidget(row)
        layout.addStretch()
        return page

    def _engine_page(self) -> QWidget:
        page, layout = self._page("How should Waky listen?", "You can change this any time in Settings.")
        self.cloud_radio = ChoiceCard(
            "Groq cloud", "Fast and accurate with smart rewriting: emails, bullet points, your own modes. Needs your own free Groq key.", "Recommended"
        )
        self.local_radio = ChoiceCard(
            "Local only", "Speech to text runs on this PC with Whisper. Needs a one-time model download (75 MB to 3 GB). Rewriting stays basic.", ""
        )
        self.cloud_radio.setChecked(True)
        self.cloud_radio.chosen.connect(lambda: self._pick_engine(True))
        self.local_radio.chosen.connect(lambda: self._pick_engine(False))
        layout.addWidget(self.cloud_radio)
        layout.addSpacing(6)
        layout.addWidget(self.local_radio)
        layout.addStretch()
        return page

    def _pick_engine(self, cloud: bool) -> None:
        self.cloud = cloud
        self.cloud_radio.setChecked(cloud)
        self.local_radio.setChecked(not cloud)
        self.illus.configure(engine="cloud" if cloud else "local")

    def _key_page(self) -> QWidget:
        page, layout = self._page("Connect your Groq key", "Groq runs the speech and rewriting models. The free tier is enough to start.")
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(8)
        steps = QLabel(
            "1.  Open the Groq console and sign in (Google works).<br>"
            "2.  Click <b>Create API Key</b> and name it <b>Waky</b>.<br>"
            "3.  Copy the key (it starts with <b>gsk_</b>) and paste it below."
        )
        steps.setWordWrap(True)
        cl.addWidget(steps)
        open_button = QPushButton("Open Groq console")
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GROQ_KEYS_URL)))
        cl.addWidget(open_button, 0, Qt.AlignLeft)
        layout.addWidget(card)
        layout.addSpacing(6)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Paste your key here (gsk_...)")
        self.key_edit.textChanged.connect(self._key_changed)
        layout.addWidget(self.key_edit)
        row = QHBoxLayout()
        self.verify_button = QPushButton("Verify key")
        self.verify_button.clicked.connect(self._verify)
        self.verify_label = QLabel("")
        self.verify_label.setWordWrap(True)
        row.addWidget(self.verify_button)
        row.addWidget(self.verify_label, 1)
        layout.addLayout(row)
        privacy = QLabel("Your key is saved in Windows Credential Manager on this PC and sent only to Groq.")
        privacy.setObjectName("caption")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        layout.addStretch()
        return page

    def _key_changed(self, text: str) -> None:
        self._update_nav()
        self.verify_label.setText("")
        if len(text.strip()) >= 20:
            self._verify_timer.start(700)  # verify on its own once the paste settles

    def _auto_verify(self) -> None:
        if self.index == 2 and self.verify_button.isEnabled():
            self._verify()

    def _hotkey_page(self) -> QWidget:
        page, layout = self._page("Choose your hotkey", "Hold it while you speak, release to paste.")
        layout.addSpacing(18)
        self.hotkey_edit = HotkeyEdit()
        self.hotkey_edit.setText(self.config_manager.get("hotkeys.push_to_talk", "<ctrl>+<win>"))
        self.hotkey_edit.setMinimumHeight(60)
        self.hotkey_edit.textChanged.connect(lambda _t: self._sync_keys())
        layout.addWidget(self.hotkey_edit)
        hint = QLabel("Click the box, then press the keys you want together. Ctrl + Win is the default and F8 always works as a backup.")
        hint.setObjectName("caption")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _sync_keys(self) -> None:
        raw = self.hotkey_edit.text()
        if raw:
            self.illus.configure(keys=hotkeys.pretty_combo(raw).split(" + "))

    def _style_page(self) -> QWidget:
        page, layout = self._page("Make the pill yours", "A tiny always-on-top indicator. Everything here can be changed later in Settings.")
        self.preview = PillPreview(self.style_key, self.accent, 1.0)
        self.preview.hide()
        grid = QGridLayout()
        grid.setSpacing(10)
        self.style_radios: dict[str, StyleCard] = {}
        for i, style in enumerate(pill_styles.STYLES.values()):
            card = StyleCard(style, self.accent)
            card.preview.setMinimumSize(100, 46)
            card.clicked.connect(self._pick_style)
            grid.addWidget(card, i // 3, i % 3)
            self.style_radios[style.key] = card
        layout.addLayout(grid)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.swatch_buttons: list[tuple[str, QPushButton]] = []
        for hexv, name in SWATCHES:
            b = QPushButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#swatch {{ background: {hexv}; }}")
            b.clicked.connect(lambda _c=False, h=hexv: self._pick_accent(h))
            row.addWidget(b)
            self.swatch_buttons.append((hexv, b))
        more = QPushButton("Custom...")
        more.setObjectName("plain")
        more.clicked.connect(self._custom_accent)
        row.addWidget(more)
        row.addSpacing(18)
        row.addWidget(QLabel("Size"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(60, 220)
        self.size_slider.setValue(self.size_pct)
        self.size_slider.valueChanged.connect(self._pick_size)
        row.addWidget(self.size_slider, 1)
        layout.addLayout(row)
        layout.addStretch()
        self._refresh_style_cards()
        return page

    def _refresh_style_cards(self) -> None:
        for key, card in self.style_radios.items():
            card.set_selected(key == self.style_key)
            card.preview.set_look(accent=self.accent)
        for hexv, b in self.swatch_buttons:
            b.setChecked(hexv.lower() == self.accent.lower())
        self.preview.set_look(self.style_key, self.accent, max(0.6, min(1.6, self.size_pct / 100)))
        self.illus.configure(pill_style=self.style_key, accent=self.accent, pill_scale=max(0.6, min(1.5, self.size_pct / 100)))

    def _pick_style(self, key: str) -> None:
        self.style_key = key
        self._refresh_style_cards()
        self._apply_look_live()

    def _pick_accent(self, hexv: str) -> None:
        self.accent = hexv
        self._refresh_style_cards()
        self._apply_look_live()

    def _custom_accent(self) -> None:
        color = QColorDialog.getColor(QColor(self.accent), self, "Pill colour")
        if color.isValid():
            self._pick_accent(color.name().upper())

    def _pick_size(self, value: int) -> None:
        self.size_pct = value
        self._refresh_style_cards()
        self._apply_look_live()

    def _apply_look_live(self) -> None:
        fb = self.config_manager.settings.setdefault("floating_bar", {})
        fb.update({"style": self.style_key, "accent": self.accent, "size": self.size_pct})
        self.settings_applied.emit()  # the real pill on screen follows along

    def _check_page(self) -> QWidget:
        page, layout = self._page("System check", "Making sure Waky will work on this PC. Anything amber or red comes with a fix.")
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.setSpacing(10)
        self.check_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for key, name in (("mic", "Microphone"), ("perm", "Microphone access"), ("keys", "Global hotkeys"), ("clip", "Paste into apps"), ("net", "Internet to Groq")):
            row = QHBoxLayout()
            dot = QLabel("\u25CF")
            dot.setFixedWidth(18)
            dot.setStyleSheet("color:#8E8E93;")
            title = QLabel(name)
            title.setStyleSheet("font-weight:600;")
            title.setFixedWidth(150)
            detail = QLabel("Checking...")
            detail.setObjectName("sub")
            detail.setWordWrap(True)
            row.addWidget(dot)
            row.addWidget(title)
            row.addWidget(detail, 1)
            cl.addLayout(row)
            self.check_rows[key] = (dot, detail)
        layout.addWidget(card)
        row = QHBoxLayout()
        again = QPushButton("Check again")
        again.clicked.connect(self._run_checks)
        self.fix_button = QPushButton("Open Windows settings")
        self.fix_button.hide()
        self.fix_button.clicked.connect(self._open_fix)
        row.addWidget(again)
        row.addWidget(self.fix_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        self._fix_uri = ""
        return page

    def _run_checks(self) -> None:
        for dot, detail in self.check_rows.values():
            dot.setStyleSheet("color:#8E8E93;")
            detail.setText("Checking...")
        self.fix_button.hide()
        threading.Thread(target=lambda: self._checks_done.emit(system_check.run_all()), daemon=True, name="waky-system-check").start()

    def _on_checks(self, results) -> None:
        pal = ios_theme.current()
        colors = {"ok": pal.success, "warn": "#FF9500", "fail": pal.danger}
        self._fix_uri = ""
        for c in results:
            if c.key in self.check_rows:
                dot, detail = self.check_rows[c.key]
                dot.setStyleSheet(f"color:{colors[c.status]};")
                detail.setText(c.detail)
                if c.fix and not self._fix_uri:
                    self._fix_uri = c.fix
        self.fix_button.setVisible(bool(self._fix_uri))

    def _open_fix(self) -> None:
        if self._fix_uri:
            QDesktopServices.openUrl(QUrl(self._fix_uri))

    def _try_page(self) -> QWidget:
        page, layout = self._page("Try it", "Click inside the box, hold your hotkey, say a sentence, then release.")
        self.try_hint = QLabel("")
        self.try_hint.setObjectName("sub")
        layout.addWidget(self.try_hint)
        self.try_box = QPlainTextEdit()
        self.try_box.setPlaceholderText("Your dictated text appears here...")
        layout.addWidget(self.try_box, 1)
        tip = QLabel("Tip: say \"write email\" or \"bullet points\" inside your sentence to reshape the text. Add your own modes in Settings > Commands.")
        tip.setObjectName("caption")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        return page

    def _done_page(self) -> QWidget:
        page, layout = self._page("You are all set", "Waky now lives in the system tray. The pill waits quietly at the edge of your screen.")
        self.done_note = QLabel("")
        self.done_note.setObjectName("sub")
        self.done_note.setWordWrap(True)
        layout.addWidget(self.done_note)
        layout.addSpacing(6)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 8, 20, 8)
        self.autostart_box = IOSSwitch("Start Waky when Windows starts")
        self.autostart_box.setChecked(True)
        cl.addWidget(self.autostart_box)
        layout.addWidget(card)
        layout.addStretch()
        return page

    # ---------- navigation ----------

    def _visible_indexes(self) -> list[int]:
        return [i for i in range(len(self.pages)) if not (i == 2 and not self.cloud)]

    KINDS = ["welcome", "engine", "key", "hotkey", "pill", "check", "try", "done"]

    def _show(self, index: int, direction: int = 1, animate: bool = True) -> None:
        self.index = index
        if index == 5:
            self._run_checks()
        if index == 6:
            self.try_hint.setText(f"Hotkey: {hotkeys.pretty_combo(self.hotkey_edit.text())}   (or F8)")
        if index == 7:
            self.done_note.setText(
                "Cloud mode is on. If Groq's free limit is ever reached, Waky switches to local Whisper once you download a model in Settings > Transcription."
                if self.cloud
                else "Local mode is on. Open Settings > Transcription next and download a model so dictation works offline."
            )
        self.illus.set_kind(self.KINDS[index], animate)
        self._sync_keys()
        self.stack.go(index, direction, animate)
        self._update_nav()

    def jump(self, index: int) -> None:
        """Go to a page without animation (used for previews and tests)."""
        self._show(index, 1, animate=False)

    def _update_nav(self) -> None:
        order = self._visible_indexes()
        position = order.index(self.index)
        self.dots.set_count(len(order))
        self.dots.go(position)
        self.step_label.setText(f"Step {position + 1} of {len(order)}")
        self.back_button.setVisible(position > 0)
        last = position == len(order) - 1
        self.next_button.setText("Start using Waky" if last else ("Get started" if position == 0 else "Next  \u203A"))
        self.skip_button.setVisible(not last)
        needs_key = self.index == 2 and not self.key_edit.text().strip()
        self.next_button.setEnabled(not needs_key)

    def _next(self) -> None:
        if self.index in (2, 3, 4):
            self._apply()
        order = self._visible_indexes()
        position = order.index(self.index)
        if position == len(order) - 1:
            self._finish()
            return
        self._show(order[position + 1], 1)

    def _back(self) -> None:
        order = self._visible_indexes()
        self._show(order[max(0, order.index(self.index) - 1)], -1)

    # ---------- actions ----------

    def _verify(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            return
        self.verify_button.setEnabled(False)
        self.verify_label.setText("Checking...")
        self.verify_label.setObjectName("")

        def work() -> None:
            ok, message = llm_engine.verify_key(key)
            self._verify_done.emit(ok, message)

        threading.Thread(target=work, daemon=True, name="waky-key-verify").start()

    def _on_verified(self, ok: bool, message: str) -> None:
        self.verify_button.setEnabled(True)
        self.verify_label.setObjectName("ok" if ok else "bad")
        self.verify_label.style().unpolish(self.verify_label)
        self.verify_label.style().polish(self.verify_label)
        self.verify_label.setText(("✓ " if ok else "✗ ") + message)

    def _apply(self) -> None:
        s = self.config_manager.settings
        if self.cloud and self.key_edit.text().strip():
            groq = s.setdefault("providers", {}).setdefault("groq", {})
            groq["api_key"] = self.key_edit.text().strip()
            groq["enabled"] = True
            s.setdefault("transcription", {})["backend"] = "auto_fallback"
        elif not self.cloud:
            s.setdefault("transcription", {})["backend"] = "local"
        combo = self.hotkey_edit.text().strip()
        if combo and "Press" not in combo:
            s.setdefault("hotkeys", {})["push_to_talk"] = combo
        s.setdefault("floating_bar", {}).update({"style": self.style_key, "accent": self.accent, "size": self.size_pct})
        self.config_manager.save_settings()
        self.settings_applied.emit()

    def _apply_autostart(self) -> None:
        from .startup_manager import StartupManager
        from .utils import PROJECT_ROOT

        enabled = self.autostart_box.isChecked()
        self.config_manager.settings.setdefault("general", {})["launch_on_startup"] = enabled
        try:
            StartupManager(PROJECT_ROOT / "start_waky_hidden.vbs").set_enabled(enabled)
        except Exception:
            pass  # not fatal; Settings > General can retry and will report errors

    def _mark_done(self) -> None:
        self.config_manager.settings.setdefault("general", {})["onboarding_done"] = True
        self.config_manager.save_settings()

    def _skip(self) -> None:
        self._mark_done()
        self.finished_setup.emit(False)
        self.accept()

    def _finish(self) -> None:
        self._apply()
        self._apply_autostart()
        self._mark_done()
        self.finished_setup.emit(not self.cloud)
        self.accept()
