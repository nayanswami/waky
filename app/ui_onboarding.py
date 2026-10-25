"""First-run setup assistant, laid out like a macOS app's welcome window: step rail on the left, one calm page at a time on the right."""
from __future__ import annotations

import threading

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPainterPath, QPen, QPixmap
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
from .ios_widgets import AnimatedStack, Group, IOSSwitch, KeyCaps, PillPreview, Segmented, StepRail, StyleCard, glyph_pixmap
from .ui_widgets import HotkeyEdit
from .utils import asset_path

GROQ_KEYS_URL = "https://console.groq.com/keys"
SWATCHES = (("#2E62FF", "Waky blue"), ("#32ADE6", "Sky"), ("#5E5CE6", "Indigo"), ("#FF375F", "Pink"), ("#FF9F0A", "Orange"), ("#30D158", "Green"), ("#FFFFFF", "White"))
STEP_LABELS = ["Welcome", "Engine", "Groq key", "Hotkey", "Pill", "Behaviour", "Check", "Try it", "All set"]


class ChoiceCard(QFrame):
    """A selectable card (radio behaviour handled by the wizard)."""

    chosen = Signal()

    def __init__(self, title: str, body: str, badge: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("styleCard")
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(3)
        top = QHBoxLayout()
        head = QLabel(title)
        head.setStyleSheet("font-size:14px;font-weight:600;")
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


class FeatureRow(QWidget):
    """Icon tile + title + one line of text (macOS 'What's New' style)."""

    def __init__(self, glyph: str, color: str, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(14)
        icon = QLabel()
        icon.setPixmap(glyph_pixmap(glyph, color, 36))
        icon.setFixedSize(36, 36)
        lay.addWidget(icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        head = QLabel(title)
        head.setStyleSheet("font-weight:600;font-size:14px;")
        body = QLabel(text)
        body.setObjectName("sub")
        body.setWordWrap(True)
        col.addWidget(head)
        col.addWidget(body)
        lay.addLayout(col, 1)


class PopBadge(QWidget):
    """The app icon, or a success tick, that pops in with a small spring whenever its page appears."""

    def __init__(self, kind: str = "app", size: int = 84, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._size = size
        self._scale = 1.0
        self.setFixedSize(size + 24, size + 24)
        self._pix = QPixmap(str(asset_path("waky-icon.png"))) if kind == "app" else QPixmap()
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setStartValue(0.72)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_value)

    def _on_value(self, v) -> None:
        self._scale = float(v)
        self.update()

    def pop(self) -> None:
        self._anim.stop()
        self._anim.start()

    def paintEvent(self, _e) -> None:
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self._size * self._scale
        x = (self.width() - s) / 2
        y = (self.height() - s) / 2
        p.setOpacity(min(1.0, 0.3 + self._scale * 0.7))
        if self.kind == "app":
            for grow, alpha in ((10, 6), (7, 8), (4, 10), (2, 12)):   # soft layered shadow
                path = QPainterPath()
                path.addRoundedRect(QRectF(x - grow / 2, y + 6 - grow / 2, s + grow, s + grow), s * 0.225 + grow / 2, s * 0.225 + grow / 2)
                p.fillPath(path, QColor(0, 0, 0, alpha if not pal.is_dark else alpha * 3))
            if not self._pix.isNull():
                p.drawPixmap(QRectF(x, y, s, s), self._pix, QRectF(self._pix.rect()))
        else:
            p.setPen(Qt.NoPen)
            for grow, alpha in ((10, 6), (6, 9), (3, 12)):
                p.setBrush(QColor(0, 0, 0, alpha))
                p.drawEllipse(QRectF(x - grow / 2, y + 5 - grow / 2, s + grow, s + grow))
            p.setBrush(QColor(pal.success))
            p.drawEllipse(QRectF(x, y, s, s))
            pen = QPen(QColor("#FFFFFF"), s * 0.075)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            cx, cy = x + s / 2, y + s / 2
            p.drawPolyline([
                QPointF(cx - s * 0.2, cy + s * 0.01),
                QPointF(cx - s * 0.05, cy + s * 0.16),
                QPointF(cx + s * 0.22, cy - s * 0.14),
            ])


class OnboardingWizard(QDialog):
    settings_applied = Signal()   # emitted whenever a step has written new settings
    finished_setup = Signal(bool)  # True when the user wants Settings opened afterwards
    _verify_done = Signal(bool, str)
    _checks_done = Signal(object)

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Welcome to Waky")
        self.setFixedSize(820, 660)
        fb = config_manager.settings.get("floating_bar", {})
        self.cloud = True
        self._closing = False
        self.style_key = pill_styles.get_style(fb.get("style")).key
        self.accent = str(fb.get("accent") or pill_styles.DEFAULT_ACCENT)
        self.size_pct = int(fb.get("size", 100))

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- left rail ----
        rail = QFrame()
        rail.setObjectName("sideFrame")
        rail.setFixedWidth(210)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(22, 26, 18, 20)
        rl.setSpacing(0)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setFixedSize(30, 30)
        pix = QPixmap(str(asset_path("waky-icon.png")))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand_text = QLabel("Waky")
        brand_text.setObjectName("settingsTitle")
        brand.addWidget(logo)
        brand.addWidget(brand_text)
        brand.addStretch()
        rl.addLayout(brand)
        rl.addSpacing(26)
        self.rail = StepRail(STEP_LABELS)
        rl.addWidget(self.rail)
        rl.addStretch()
        self.step_label = QLabel("")
        self.step_label.setObjectName("caption")
        rl.addWidget(self.step_label)
        outer.addWidget(rail)

        # ---- right side ----
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.stack = AnimatedStack()
        holder = QVBoxLayout()
        holder.setContentsMargins(40, 34, 40, 8)
        holder.addWidget(self.stack)
        right.addLayout(holder, 1)

        footer = QFrame()
        footer.setObjectName("footer")
        nav = QHBoxLayout(footer)
        nav.setContentsMargins(40, 12, 40, 14)
        nav.setSpacing(8)
        self.skip_button = QPushButton("Skip setup")
        self.skip_button.setObjectName("plain")
        self.skip_button.clicked.connect(self._skip)
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Continue")
        self.next_button.setObjectName("primary")
        self.next_button.setMinimumWidth(120)
        self.next_button.setDefault(True)
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        nav.addWidget(self.skip_button)
        nav.addStretch()
        nav.addWidget(self.back_button)
        nav.addWidget(self.next_button)
        right.addWidget(footer)
        outer.addLayout(right, 1)

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
        self.welcome_badge.pop()

    # ---------- pages ----------

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("title")
        sub = QLabel(subtitle)
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(10)
        return page, layout

    def _welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.welcome_badge = PopBadge("app", 84)
        layout.addWidget(self.welcome_badge, 0, Qt.AlignLeft)
        heading = QLabel("Welcome to Waky")
        heading.setObjectName("title")
        sub = QLabel("Hold a key, speak naturally, and finished text appears in any app. Setup takes about two minutes.")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(16)
        layout.addWidget(FeatureRow("", "#FF3B30", "Dictate anywhere", "Hold your hotkey in any text field, speak, release. The words are pasted for you."))
        layout.addWidget(FeatureRow("", "#5E5CE6", "Writes like you", "Filler words and Hinglish turn into clean text. Say \"write email\" or \"bullet points\" to reshape it."))
        layout.addWidget(FeatureRow("", "#30B0C7", "Private by design", "Your own Groq key stays in Windows Credential Manager. Audio is never saved."))
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
        layout.addSpacing(4)
        layout.addWidget(self.local_radio)
        layout.addStretch()
        return page

    def _pick_engine(self, cloud: bool) -> None:
        self.cloud = cloud
        self.cloud_radio.setChecked(cloud)
        self.local_radio.setChecked(not cloud)
        self._update_nav()

    def _key_page(self) -> QWidget:
        page, layout = self._page("Connect your Groq key", "Groq runs the speech and rewriting models. The free tier is enough to start.")
        steps = Group()
        for number, text in (
            ("1", "Open the Groq console and sign in. Google sign-in works."),
            ("2", "Click <b>Create API Key</b> and name it <b>Waky</b>."),
            ("3", "Copy the key (it starts with <b>gsk_</b>) and paste it below."),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            badge = QLabel(number)
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(f"background:{ios_theme.current().accent_fill};color:{ios_theme.current().accent};border-radius:11px;font-weight:700;")
            label = QLabel(text)
            label.setWordWrap(True)
            row.addWidget(badge)
            row.addSpacing(8)
            row.addWidget(label, 1)
            steps.addRow(row)
        open_button = QPushButton("Open Groq console")
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GROQ_KEYS_URL)))
        steps.addRow(open_button)
        layout.addWidget(steps)
        layout.addSpacing(8)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Paste your key here (gsk_...)")
        self.key_edit.setMinimumHeight(34)
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
        self.keycaps = KeyCaps(["Ctrl", "Win"])
        layout.addWidget(self.keycaps)
        self.hotkey_edit = HotkeyEdit()
        self.hotkey_edit.setObjectName("hotkeyBig")
        self.hotkey_edit.setText(self.config_manager.get("hotkeys.push_to_talk", "<ctrl>+<win>"))
        self.hotkey_edit.setMinimumHeight(52)
        self.hotkey_edit.textChanged.connect(lambda _t: self._sync_keys())
        layout.addWidget(self.hotkey_edit)
        hint = QLabel(
            "Click the box, then press the keys you want together. Ctrl + Win is the default and F8 always works as a backup. "
            "You can also use your mouse's middle or side button."
        )
        hint.setObjectName("caption")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        self._sync_keys()
        return page

    def _sync_keys(self) -> None:
        raw = self.hotkey_edit.text()
        if raw:
            self.keycaps.set_keys(hotkeys.pretty_combo(raw).split(" + "))

    def _style_page(self) -> QWidget:
        page, layout = self._page("Make the pill yours", "A tiny always-on-top indicator. Everything here can be changed later in Settings.")
        self.preview = PillPreview(self.style_key, self.accent, 1.0)
        self.preview.setFixedHeight(78)
        layout.addWidget(self.preview)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.style_radios: dict[str, StyleCard] = {}
        for i, style in enumerate(pill_styles.STYLES.values()):
            card = StyleCard(style, self.accent)
            card.preview.setMinimumSize(100, 40)
            card.clicked.connect(self._pick_style)
            grid.addWidget(card, i // 3, i % 3)
            self.style_radios[style.key] = card
        layout.addLayout(grid)
        row = QHBoxLayout()
        row.setSpacing(7)
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
        more.setObjectName("link")
        more.clicked.connect(self._custom_accent)
        row.addWidget(more)
        row.addSpacing(14)
        size_label = QLabel("Size")
        size_label.setObjectName("caption")
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

    def _behaviour_page(self) -> QWidget:
        page, layout = self._page("How should Waky behave?", "Set it once and forget it. Every option can be changed later.")
        s = self.config_manager.settings
        start = s.get("floating_bar", {}).get("visibility", "always")

        vis = Group()
        self.vis_segment = Segmented([("always", "Always"), ("active", "While dictating"), ("hidden", "Hidden")], start if start in ("always", "active", "hidden") else "always")
        vis.addRow("Show the pill", self.vis_segment, hint="While dictating: it fades in only when you hold the hotkey.")
        layout.addWidget(vis)
        layout.addSpacing(8)

        how = Group()
        language = s.get("transcription", {}).get("language_mode", "english")
        self.language_seg = Segmented([("english", "English"), ("hinglish", "Hinglish"), ("hindi", "Hindi")], language if language in ("english", "hinglish", "hindi") else "english")
        how.addRow("I mostly speak", self.language_seg, hint="Hinglish means Hindi and English mixed in one sentence.")
        style = s.get("output", {}).get("writing_style", "clean")
        self.style_seg = Segmented([("exact", "Exact words"), ("clean", "Clean"), ("rewrite", "Rewrite")], style if style in ("exact", "clean", "rewrite") else "clean")
        how.addRow("Writing style", self.style_seg, hint="Clean keeps your own words and fixes punctuation and misheard words. Exact adds nothing at all.")
        layout.addWidget(how)
        layout.addSpacing(8)

        opts = Group()
        self.autostart_box = IOSSwitch("Start Waky when Windows starts")
        self.autostart_box.setChecked(True)
        opts.addRow(self.autostart_box, hint="Waky opens quietly in the tray. The pill appears, no window pops up.")
        self.sound_box = IOSSwitch("Play soft sounds")
        self.sound_box.setChecked(bool(s.get("general", {}).get("sound_effects", False)))
        opts.addRow(self.sound_box, hint="A gentle tone when recording starts, stops and finishes.")
        self.history_box = IOSSwitch("Remember recent dictations on this PC")
        self.history_box.setChecked(bool(s.get("privacy", {}).get("keep_history", True)))
        opts.addRow(self.history_box, hint="Lets you review what Waky heard and teach it corrections. Text only, never audio. Clear it any time.")
        self.update_box = IOSSwitch("Check for updates automatically")
        self.update_box.setChecked(bool(s.get("updates", {}).get("auto_check", True)))
        opts.addRow(self.update_box, hint="Looks at GitHub about once a day. Nothing installs without your click.")
        layout.addWidget(opts)
        layout.addStretch()
        return page

    def _check_page(self) -> QWidget:
        page, layout = self._page("System check", "Making sure Waky will work on this PC. Anything amber or red comes with a fix.")
        card = Group()
        self.check_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for key, name in (("mic", "Microphone"), ("perm", "Microphone access"), ("keys", "Global hotkeys"), ("clip", "Paste into apps"), ("net", "Internet to Groq")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            dot = QLabel("●")
            dot.setFixedWidth(18)
            dot.setStyleSheet("color:#9A9AA1;")
            title = QLabel(name)
            title.setStyleSheet("font-weight:600;")
            title.setFixedWidth(140)
            detail = QLabel("Checking...")
            detail.setObjectName("sub")
            detail.setWordWrap(True)
            row.addWidget(dot)
            row.addWidget(title)
            row.addWidget(detail, 1)
            card.addRow(row)
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
            dot.setStyleSheet("color:#9A9AA1;")
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
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.done_badge = PopBadge("check", 72)
        layout.addWidget(self.done_badge, 0, Qt.AlignLeft)
        heading = QLabel("You are all set")
        heading.setObjectName("title")
        layout.addWidget(heading)
        self.done_note = QLabel("")
        self.done_note.setObjectName("sub")
        self.done_note.setWordWrap(True)
        layout.addWidget(self.done_note)
        layout.addSpacing(14)
        tips = Group()
        for title, text in (
            ("Open Settings", "Hold Shift and click the pill, or use the tray icon."),
            ("Move the pill", "Hold Alt and drag it. Settings > Floating Bar has more spots."),
            ("Rewrite text", "Select text in any app, hold your hotkey and say what to change."),
            ("Updates", "Waky tells you when a new version is ready. Settings > Updates."),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            head = QLabel(title)
            head.setStyleSheet("font-weight:600;")
            head.setFixedWidth(120)
            body = QLabel(text)
            body.setObjectName("sub")
            body.setWordWrap(True)
            row.addWidget(head)
            row.addWidget(body, 1)
            tips.addRow(row)
        layout.addWidget(tips)
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
            self.try_hint.setText(f"Hotkey: {hotkeys.pretty_combo(self.hotkey_edit.text())}   (or F8)")
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
            self.done_badge.pop()
        if index == 0:
            self.welcome_badge.pop()
        self.stack.go(index, direction, animate)
        self._update_nav()

    def jump(self, index: int) -> None:
        """Go to a page without animation (used for previews and tests)."""
        self._show(index, 1, animate=False)

    def _update_nav(self) -> None:
        order = self._visible_indexes()
        position = order.index(self.index)
        self.rail.set_state([STEP_LABELS[i] for i in order], position)
        self.step_label.setText(f"Step {position + 1} of {len(order)}")
        self.back_button.setVisible(position > 0)
        last = position == len(order) - 1
        self.next_button.setText("Start using Waky" if last else ("Get started" if position == 0 else "Continue"))
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
