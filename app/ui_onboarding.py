"""First-run setup assistant: airy two-tone headlines with inline chips, soft white cards, one calm page at a time."""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
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

from . import hotkeys, ios_theme, llm_engine, pill_styles, system_check
from .ios_widgets import AnimatedStack, Group, IOSSwitch, KeyCaps, PillPreview, Segmented, StyleCard
from .onboarding_kit import (
    INK,
    WIZARD_QSS,
    Card,
    Headline,
    PillChip,
    PlanCard,
    ProgressLine,
    ToggleChip,
    tile_label,
)
from .ui_widgets import HotkeyEdit

GROQ_KEYS_URL = "https://console.groq.com/keys"
SWATCHES = (("#2E62FF", "Waky blue"), ("#32ADE6", "Sky"), ("#5E5CE6", "Indigo"), ("#FF375F", "Pink"), ("#FF9F0A", "Orange"), ("#30D158", "Green"), ("#FFFFFF", "White"))
STEP_LABELS = ["Welcome", "Engine", "Groq key", "Hotkey", "Pill", "Behaviour", "Check", "Try it", "All set"]

MIC, PEN, LOCK, CLOUD, DEVICE, KEY, KEYBOARD, CHECK, SYNC = (
    "", "", "", "", "", "", "", "", "",
)


class _NoPop:
    def pop(self) -> None:
        pass


class OnboardingWizard(QDialog):
    settings_applied = Signal()   # emitted whenever a step has written new settings
    finished_setup = Signal(bool)  # True when the user wants Settings opened afterwards
    _verify_done = Signal(bool, str)
    _checks_done = Signal(object)

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.setObjectName("wizard")
        self.setWindowTitle("Welcome to Waky")
        self.setFixedSize(900, 720)
        self.setStyleSheet(WIZARD_QSS)
        fb = config_manager.settings.get("floating_bar", {})
        self.cloud = True
        self._closing = False
        self.style_key = pill_styles.get_style(fb.get("style")).key
        self.accent = str(fb.get("accent") or pill_styles.DEFAULT_ACCENT)
        self.size_pct = int(fb.get("size", 100))
        self.welcome_badge = _NoPop()
        self.done_badge = _NoPop()

        root = QVBoxLayout(self)
        root.setContentsMargins(60, 30, 60, 0)
        root.setSpacing(0)

        # ---- top bar: tag, step counter, skip ----
        top = QHBoxLayout()
        top.setSpacing(12)
        tag = QLabel("SETUP")
        tag.setObjectName("tag")
        self.step_label = QLabel("")
        self.step_label.setObjectName("step")
        self.skip_button = QPushButton("Skip setup  →")
        self.skip_button.setObjectName("plain")
        self.skip_button.setCursor(Qt.PointingHandCursor)
        self.skip_button.clicked.connect(self._skip)
        top.addWidget(tag)
        top.addWidget(self.step_label)
        top.addStretch()
        top.addWidget(self.skip_button)
        root.addLayout(top)
        root.addSpacing(12)
        self.progress = ProgressLine(len(STEP_LABELS))
        root.addWidget(self.progress)
        root.addSpacing(26)

        self.stack = AnimatedStack()
        root.addWidget(self.stack, 1)

        footer = QFrame()
        footer.setObjectName("footer")
        nav = QHBoxLayout(footer)
        nav.setContentsMargins(0, 8, 0, 26)
        nav.setSpacing(10)
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Continue")
        self.next_button.setObjectName("ink")
        self.next_button.setMinimumWidth(150)
        self.next_button.setDefault(True)
        self.next_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        nav.addStretch()
        nav.addWidget(self.back_button)
        nav.addWidget(self.next_button)
        root.addWidget(footer)

        self._verify_timer = QTimer(self)
        self._verify_timer.setSingleShot(True)
        self._verify_timer.timeout.connect(self._auto_verify)

        self.pages = [
            self._welcome_page(), self._engine_page(), self._key_page(), self._hotkey_page(), self._style_page(),
            self._behaviour_page(), self._check_page(), self._try_page(), self._done_page(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        self._verify_done.connect(self._on_verified)
        self._checks_done.connect(self._on_checks)
        self.index = 0
        self._update_nav()

    # ---------- page scaffolding ----------

    def _page(self, headline: list, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(Headline(headline))
        if subtitle:
            layout.addSpacing(10)
            sub = QLabel(subtitle)
            sub.setObjectName("sub")
            sub.setWordWrap(True)
            layout.addWidget(sub)
        layout.addSpacing(22)
        return page, layout

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cap")
        label.setWordWrap(True)
        return label

    # ---------- pages ----------

    def _welcome_page(self) -> QWidget:
        page, layout = self._page(
            [("g", "Say it messy."), ("k", "Get it"), ("c", tile_label(MIC, "#FFFFFF", "#FF3B30", 50)), ("k", "written.")],
            "Hold a key, speak naturally, and finished text appears in any app. Setup takes about two minutes.",
        )
        row = QHBoxLayout()
        row.setSpacing(16)
        for glyph, title, text in (
            (MIC, "Dictate anywhere", "Hold your hotkey in any text field, speak, release."),
            (PEN, "Writes like you", "Fillers and Hinglish become clean text in your words."),
            (LOCK, "Private by design", "Your own Groq key. Audio is never saved."),
        ):
            card = Card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 20, 20, 20)
            cl.setSpacing(12)
            cl.addWidget(tile_label(glyph, "#18181B", "#FFFFFF", 42, shadow=False), 0, Qt.AlignLeft)
            name = QLabel(title)
            name.setStyleSheet("font-size:16px;font-weight:600;")
            cl.addWidget(name)
            body = QLabel(text)
            body.setStyleSheet("font-size:13px;color:#7C7C83;")
            body.setWordWrap(True)
            cl.addWidget(body)
            cl.addStretch()
            row.addWidget(card, 1)
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _engine_page(self) -> QWidget:
        page, layout = self._page(
            [("g", "Pick how Waky"), ("c", tile_label(CLOUD, "#FFFFFF", "#2E62FF", 50)), ("k", "listens.")],
            "You can change this any time in Settings.",
        )
        row = QHBoxLayout()
        row.setSpacing(16)
        self.cloud_radio = PlanCard(
            CLOUD, "Groq cloud", "free key", "Choose cloud",
            ["Fast and accurate speech to text", "Smart rewriting and your own modes", "Needs your own free Groq key"],
        )
        self.local_radio = PlanCard(
            DEVICE, "Local only", "on this PC", "Choose local",
            ["Runs fully on this PC, offline", "One-time model download (75 MB to 3 GB)", "Rewriting stays basic"],
        )
        self.cloud_radio.setChecked(True)
        self.cloud_radio.chosen.connect(lambda: self._pick_engine(True))
        self.local_radio.chosen.connect(lambda: self._pick_engine(False))
        row.addWidget(self.cloud_radio, 1)
        row.addWidget(self.local_radio, 1)
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _pick_engine(self, cloud: bool) -> None:
        self.cloud = cloud
        self.cloud_radio.setChecked(cloud)
        self.local_radio.setChecked(not cloud)
        self._update_nav()

    def _key_page(self) -> QWidget:
        page, layout = self._page(
            [("g", "Connect your"), ("c", tile_label(KEY, "#FFFFFF", "#FF9F0A", 50)), ("k", "Groq key.")],
            "Groq runs the speech and rewriting models. The free tier is enough to start.",
        )
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(12)
        for number, text in (
            ("1", "Open the Groq console and sign in. Google sign-in works."),
            ("2", "Click <b>Create API Key</b> and name it <b>Waky</b>."),
            ("3", "Copy the key (it starts with <b>gsk_</b>) and paste it below."),
        ):
            line = QHBoxLayout()
            line.setSpacing(12)
            badge = QLabel(number)
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(f"background:{INK};color:#fff;border-radius:12px;font-weight:700;font-size:12px;")
            label = QLabel(text)
            label.setWordWrap(True)
            line.addWidget(badge)
            line.addWidget(label, 1)
            cl.addLayout(line)
        open_button = QPushButton("Open Groq console  ↗")
        open_button.setCursor(Qt.PointingHandCursor)
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GROQ_KEYS_URL)))
        cl.addWidget(open_button, 0, Qt.AlignLeft)
        layout.addWidget(card)
        layout.addSpacing(16)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Paste your key here (gsk_...)")
        self.key_edit.setMinimumHeight(46)
        self.key_edit.textChanged.connect(self._key_changed)
        layout.addWidget(self.key_edit)
        layout.addSpacing(10)
        row = QHBoxLayout()
        self.verify_button = QPushButton("Verify key")
        self.verify_button.clicked.connect(self._verify)
        self.verify_label = QLabel("")
        self.verify_label.setWordWrap(True)
        row.addWidget(self.verify_button)
        row.addWidget(self.verify_label, 1)
        layout.addLayout(row)
        layout.addSpacing(6)
        layout.addWidget(self._caption("Your key is saved in Windows Credential Manager on this PC and sent only to Groq."))
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
        page, layout = self._page(
            [("g", "Choose the keys"), ("k", "you hold to talk.")],
            "Hold them while you speak, release to paste.",
        )
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 14, 22, 20)
        cl.setSpacing(6)
        self.keycaps = KeyCaps(["Ctrl", "Win"])
        cl.addWidget(self.keycaps)
        self.hotkey_edit = HotkeyEdit()
        self.hotkey_edit.setObjectName("hotkeyBig")
        self.hotkey_edit.setText(self.config_manager.get("hotkeys.push_to_talk", "<ctrl>+<win>"))
        self.hotkey_edit.setMinimumHeight(60)
        self.hotkey_edit.textChanged.connect(lambda _t: self._sync_keys())
        cl.addWidget(self.hotkey_edit)
        layout.addWidget(card)
        layout.addSpacing(14)
        layout.addWidget(self._caption(
            "Click the box, then press the keys you want together. Ctrl + Win is the default and F8 always works as a backup. "
            "You can also use your mouse's middle or side button."
        ))
        layout.addStretch()
        self._sync_keys()
        return page

    def _sync_keys(self) -> None:
        raw = self.hotkey_edit.text()
        if raw:
            self.keycaps.set_keys(hotkeys.pretty_combo(raw).split(" + "))

    def _style_page(self) -> QWidget:
        page, layout = self._page([("g", "Make the"), ("c", PillChip(self.accent)), ("k", "pill yours.")], "")
        self.preview = PillPreview(self.style_key, self.accent, 1.0)
        self.preview.setFixedHeight(84)
        layout.addWidget(self.preview)
        layout.addSpacing(14)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.style_radios: dict[str, StyleCard] = {}
        for i, style in enumerate(pill_styles.STYLES.values()):
            card = StyleCard(style, self.accent)
            card.preview.setMinimumSize(100, 40)
            card.clicked.connect(self._pick_style)
            grid.addWidget(card, i // 3, i % 3)
            self.style_radios[style.key] = card
        layout.addLayout(grid)
        layout.addSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.swatch_buttons: list[tuple[str, QPushButton]] = []
        for hexv, name in SWATCHES:
            b = QPushButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(26, 26)
            b.setStyleSheet(f"QPushButton#swatch {{ background: {hexv}; border-radius: 13px; padding: 0; min-height: 0; }}")
            b.clicked.connect(lambda _c=False, h=hexv: self._pick_accent(h))
            row.addWidget(b)
            self.swatch_buttons.append((hexv, b))
        more = QPushButton("Custom...")
        more.setObjectName("link")
        more.clicked.connect(self._custom_accent)
        row.addWidget(more)
        row.addSpacing(18)
        size_label = QLabel("Size")
        size_label.setObjectName("cap")
        row.addWidget(size_label)
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

    def _choice(self, title: str, control: QWidget, hint: str) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(6)
        head = QLabel(title)
        head.setStyleSheet("font-weight:600;font-size:14px;")
        box.addWidget(head)
        box.addWidget(control, 0, Qt.AlignLeft)
        box.addWidget(self._caption(hint))
        return box

    def _behaviour_page(self) -> QWidget:
        page, layout = self._page([("g", "Set it once."), ("c", ToggleChip()), ("k", "Then forget it.")], "")
        s = self.config_manager.settings
        start = s.get("floating_bar", {}).get("visibility", "always")
        language = s.get("transcription", {}).get("language_mode", "english")
        style = s.get("output", {}).get("writing_style", "clean")

        columns = QHBoxLayout()
        columns.setSpacing(16)
        left = Group()
        self.vis_segment = Segmented([("always", "Always"), ("active", "Dictating"), ("hidden", "Hidden")], start if start in ("always", "active", "hidden") else "always")
        left.addRow(self._choice("Show the pill", self.vis_segment, "Dictating: it fades in only when you hold the hotkey."))
        self.language_seg = Segmented([("english", "English"), ("hinglish", "Hinglish"), ("hindi", "Hindi")], language if language in ("english", "hinglish", "hindi") else "english")
        left.addRow(self._choice("I mostly speak", self.language_seg, "Hinglish means Hindi and English mixed together."))
        self.style_seg = Segmented([("exact", "Exact"), ("clean", "Clean"), ("rewrite", "Rewrite")], style if style in ("exact", "clean", "rewrite") else "clean")
        left.addRow(self._choice("Writing style", self.style_seg, "Clean keeps your own words and fixes punctuation and misheard words."))
        columns.addWidget(left, 1)

        right = Group()
        self.autostart_box = IOSSwitch("Start with Windows")
        self.autostart_box.setChecked(True)
        right.addRow(self.autostart_box, hint="Opens quietly in the tray. No window pops up.")
        self.sound_box = IOSSwitch("Soft sounds")
        self.sound_box.setChecked(bool(s.get("general", {}).get("sound_effects", False)))
        right.addRow(self.sound_box, hint="A gentle tone when recording starts and stops.")
        self.history_box = IOSSwitch("Remember recent dictations")
        self.history_box.setChecked(bool(s.get("privacy", {}).get("keep_history", True)))
        right.addRow(self.history_box, hint="Text only, on this PC. Lets you teach Waky corrections.")
        self.update_box = IOSSwitch("Check for updates")
        self.update_box.setChecked(bool(s.get("updates", {}).get("auto_check", True)))
        right.addRow(self.update_box, hint="About once a day. Nothing installs without you.")
        columns.addWidget(right, 1)
        layout.addLayout(columns)
        layout.addStretch()
        return page

    def _check_page(self) -> QWidget:
        page, layout = self._page(
            [("g", "Everything"), ("c", tile_label(CHECK, "#FFFFFF", "#1E9E4A", 50)), ("k", "working?")],
            "A quick look to make sure Waky will work on this PC. Anything amber or red comes with a fix.",
        )
        card = Group()
        self.check_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for key, name in (("mic", "Microphone"), ("perm", "Microphone access"), ("keys", "Global hotkeys"), ("clip", "Paste into apps"), ("net", "Internet to Groq")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            dot = QLabel("●")
            dot.setFixedWidth(20)
            dot.setStyleSheet("color:#B4B4BA;")
            title = QLabel(name)
            title.setStyleSheet("font-weight:600;")
            title.setFixedWidth(150)
            detail = QLabel("Checking...")
            detail.setObjectName("sub")
            detail.setStyleSheet("font-size:13px;")
            detail.setWordWrap(True)
            row.addWidget(dot)
            row.addWidget(title)
            row.addWidget(detail, 1)
            card.addRow(row)
            self.check_rows[key] = (dot, detail)
        layout.addWidget(card)
        layout.addSpacing(14)
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
            dot.setStyleSheet("color:#B4B4BA;")
            detail.setText("Checking...")
        self.fix_button.hide()
        threading.Thread(target=lambda: self._checks_done.emit(system_check.run_all()), daemon=True, name="waky-system-check").start()

    def _on_checks(self, results) -> None:
        pal = ios_theme.LIGHT
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
        page, layout = self._page(
            [("g", "Say something."), ("c", tile_label(MIC, "#FFFFFF", "#2E62FF", 50)), ("k", "Watch it land.")],
            "",
        )
        self.try_hint = QLabel("")
        self.try_hint.setObjectName("sub")
        layout.addWidget(self.try_hint)
        layout.addSpacing(10)
        self.try_box = QPlainTextEdit()
        self.try_box.setPlaceholderText("Click here, hold your hotkey, say a sentence, then release...")
        layout.addWidget(self.try_box, 1)
        layout.addSpacing(10)
        layout.addWidget(self._caption(
            "Tip: say \"write email\" or \"bullet points\" at the start or end of your sentence to reshape it. Add your own modes in Settings > Commands."
        ))
        return page

    def _done_page(self) -> QWidget:
        page, layout = self._page([("g", "You are"), ("c", tile_label(CHECK, "#FFFFFF", "#1E9E4A", 50)), ("k", "all set.")], "")
        self.done_note = QLabel("")
        self.done_note.setObjectName("sub")
        self.done_note.setWordWrap(True)
        layout.addWidget(self.done_note)
        layout.addSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(14)
        for glyph, title, text in (
            (KEYBOARD, "Hold to talk", "Press your hotkey in any text field."),
            (PEN, "Teach Waky", "Settings > History: fix a word once, it remembers."),
            (SYNC, "Stays current", "Waky tells you when an update is ready."),
        ):
            card = Card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(18, 18, 18, 18)
            cl.setSpacing(10)
            cl.addWidget(tile_label(glyph, "#18181B", "#FFFFFF", 38, shadow=False), 0, Qt.AlignLeft)
            name = QLabel(title)
            name.setStyleSheet("font-size:15px;font-weight:600;")
            cl.addWidget(name)
            body = QLabel(text)
            body.setStyleSheet("font-size:12px;color:#7C7C83;")
            body.setWordWrap(True)
            cl.addWidget(body)
            cl.addStretch()
            row.addWidget(card, 1)
        layout.addLayout(row)
        layout.addSpacing(14)
        layout.addWidget(self._caption("Tip: hold Shift and click the pill to open Settings. Hold Alt and drag to move it."))
        layout.addStretch()
        return page

    # ---------- navigation ----------

    def _visible_indexes(self) -> list[int]:
        return [i for i in range(len(self.pages)) if not (i == 2 and not self.cloud)]

    def _show(self, index: int, direction: int = 1, animate: bool = True) -> None:
        self.index = index
        if index == 6:
            self._run_checks()
        if index == 7:
            self.try_hint.setText(f"Hold {hotkeys.pretty_combo(self.hotkey_edit.text())} (or F8) and speak.")
        if index == 8:
            mode = self.vis_segment.value()
            where = {
                "always": "The pill waits quietly at the edge of your screen.",
                "active": "The pill appears only while you dictate.",
                "hidden": "The pill stays hidden. Waky lives in the system tray.",
            }[mode]
            engine = (
                "Cloud mode is on. If Groq's free limit is ever reached, Waky switches to local Whisper once you download a model in Settings > Transcription."
                if self.cloud
                else "Local mode is on. Open Settings > Transcription next and download a model so dictation works offline."
            )
            self.done_note.setText(f"{where} {engine}")
        self.stack.go(index, direction, animate)
        self._update_nav()

    def jump(self, index: int) -> None:
        """Go to a page without animation (used for previews and tests)."""
        self._show(index, 1, animate=False)

    def _update_nav(self) -> None:
        order = self._visible_indexes()
        position = order.index(self.index)
        self.progress.set_progress(position, len(order))
        self.step_label.setText(f"{position + 1:02d} / {len(order):02d}   {STEP_LABELS[self.index].upper()}")
        self.back_button.setVisible(position > 0)
        last = position == len(order) - 1
        self.next_button.setText("Start using Waky" if last else ("Get started" if position == 0 else "Continue  →"))
        self.skip_button.setVisible(not last)
        needs_key = self.index == 2 and not self.key_edit.text().strip()
        self.next_button.setEnabled(not needs_key)

    def _next(self) -> None:
        if self.index in (2, 3, 4, 5):
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
        fb = s.setdefault("floating_bar", {})
        fb.update({"style": self.style_key, "accent": self.accent, "size": self.size_pct, "visibility": self.vis_segment.value()})
        fb.pop("hidden", None)
        s.setdefault("general", {})["sound_effects"] = self.sound_box.isChecked()
        s.setdefault("updates", {})["auto_check"] = self.update_box.isChecked()
        s.setdefault("transcription", {})["language_mode"] = self.language_seg.value()
        s.setdefault("output", {})["writing_style"] = self.style_seg.value()
        s.setdefault("privacy", {})["keep_history"] = self.history_box.isChecked()
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
        """Skipping (or closing the window) keeps what was chosen so far and uses the defaults, including starting with Windows."""
        self._closing = True
        self._apply()
        self._apply_autostart()
        self._mark_done()
        self.finished_setup.emit(False)
        self.accept()

    def reject(self) -> None:  # window X button or Esc
        if self._closing:
            super().reject()
        else:
            self._skip()

    def _finish(self) -> None:
        self._closing = True
        self._apply()
        self._apply_autostart()
        self._mark_done()
        self.finished_setup.emit(not self.cloud)
        self.accept()
