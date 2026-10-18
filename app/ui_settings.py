from __future__ import annotations

import csv
import os
import threading

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .audio_recorder import AudioRecorder
from .diagnostics import MIC_HELP_TEXT
from .local_memory import (
    MEMORY_DIR,
    add_correction,
    add_preference,
    add_memory_note,
    add_project_context,
    add_vocabulary_item,
    clear_memory,
    get_active_project,
    memory_summary,
    set_active_project,
    summarize_project_memory,
)
from . import __version__, model_manager, pill_styles
from .ios_widgets import IOSSwitch as QCheckBox
from .ios_widgets import FlowLayout, PageStack, PillPreview, StyleCard
from .startup_manager import StartupManager
from .ui_widgets import HotkeyEdit
from .utils import LANGUAGE_LABELS, LOG_DIR, MODE_LABELS, asset_path


class SettingsWindow(QDialog):
    settings_changed = Signal()
    paste_test_requested = Signal()
    transcription_test_requested = Signal()
    groq_test_requested = Signal()
    hotkey_test_requested = Signal()
    force_reset_requested = Signal()
    model_download_finished = Signal(str)
    pill_style_changed = Signal(str)
    appearance_changed = Signal(str)

    def __init__(self, config_manager, recorder: AudioRecorder, transcriber, diagnostics, logger, parent=None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.recorder = recorder
        self.transcriber = transcriber
        self.diagnostics = diagnostics
        self.logger = logger
        self.setWindowTitle("Waky Settings")
        self.setMinimumSize(1040, 720)
        self._build_ui()
        self.load_values()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QFrame()
        side.setObjectName("sideFrame")
        side.setFixedWidth(236)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 22, 14, 14)
        sl.setSpacing(10)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setFixedSize(36, 36)
        pix = QPixmap(str(asset_path("waky-icon.png")))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        name = QLabel("Waky")
        name.setObjectName("settingsTitle")
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch()
        sl.addLayout(brand)
        sl.addSpacing(8)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setIconSize(QSize(28, 28))
        self.sidebar.setFocusPolicy(Qt.NoFocus)
        self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sl.addWidget(self.sidebar, 1)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("caption")
        sl.addWidget(version)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.tabs = PageStack()
        self.tabs.describe = self._tab_description
        right.addWidget(self.tabs, 1)
        footer = QFrame()
        footer.setObjectName("footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(28, 12, 28, 14)
        fl.setSpacing(10)
        fl.addStretch()
        close = QPushButton("Close")
        close.setObjectName("plain")
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self.save_values)
        close.clicked.connect(self.accept)
        fl.addWidget(close)
        fl.addWidget(save)
        right.addWidget(footer)
        outer.addWidget(side)
        outer.addLayout(right, 1)

        self._general_tab()
        self._hotkeys_tab()
        self._audio_tab()
        self._floating_bar_tab()
        self._transcription_tab()
        self._output_tab()
        self._commands_tab()
        self._memory_tab()
        self._vocabulary_tab()
        self._snippets_tab()
        self._privacy_tab()
        self._help_tab()
        self._diagnostics_tab()

        for title in self.tabs.titles:
            item = QListWidgetItem(self._section_icon(title), title)
            item.setSizeHint(QSize(0, 42))
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._on_sidebar)
        self.tabs.currentChanged.connect(self._sync_sidebar)

    SECTION_STYLE = {
        "General": ("", "#8E8E93"), "Hotkeys": ("", "#FF9F0A"), "Audio": ("", "#FF453A"),
        "Floating Bar": ("", "#2E62FF"), "Transcription": ("", "#5E5CE6"), "Output": ("", "#30D158"),
        "Commands": ("", "#BF5AF2"), "Memory": ("", "#32ADE6"), "Vocabulary": ("", "#FF375F"),
        "Snippets": ("", "#FFB000"), "Privacy": ("", "#34C759"), "Help": ("", "#0A84FF"),
        "Diagnostics": ("", "#8E8E93"),
    }

    def _section_icon(self, title: str) -> QIcon:
        glyph, color = self.SECTION_STYLE.get(title, ("", "#8E8E93"))
        pm = QPixmap(56, 56)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, 52, 52), 14, 14)
        p.fillPath(path, QColor(color))
        families = QFontDatabase.families()
        family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)
        if family:
            font = QFont(family)
            font.setPixelSize(28)
            p.setFont(font)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRectF(0, 0, 56, 56), Qt.AlignCenter, glyph)
        p.end()
        pm.setDevicePixelRatio(2.0)
        return QIcon(pm)

    def _on_sidebar(self, row: int) -> None:
        if row < 0:
            return
        self.tabs.go(row, 1 if row > self.tabs.currentIndex() else -1)

    def _sync_sidebar(self, index: int) -> None:
        self.sidebar.blockSignals(True)
        self.sidebar.setCurrentRow(index)
        self.sidebar.blockSignals(False)

    def _add_tab(self, title: str) -> tuple[QWidget, QFormLayout]:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.tabs.addTab(tab, title)
        return tab, form

    def _tab_description(self, title: str) -> str:
        descriptions = {
            "General": "Startup, appearance and everyday behaviour.",
            "Hotkeys": "Click a box and press the keys you want to use.",
            "Audio": "Pick your microphone and test that Waky can hear you.",
            "Floating Bar": "Style, colour, size and where the pill appears. Changes show up live.",
            "Transcription": "Choose Groq or on-device speech to text, model quality and language.",
            "Output": "How dictated text is cleaned, pasted and protected from accidental sending.",
            "Commands": "Voice modes, your own instructions and trigger phrases.",
            "Memory": "Local memory that helps Waky spell and phrase things your way.",
            "Vocabulary": "Names and terms Waky should always get right.",
            "Snippets": "Short phrases that expand into longer text.",
            "Privacy": "Keys, cloud use and how much Waky logs.",
            "Help": "Tests and shortcuts for when something is not working.",
            "Diagnostics": "Technical details for troubleshooting.",
        }
        return descriptions.get(title, "Adjust Waky settings.")

    def _general_tab(self) -> None:
        _, form = self._add_tab("General")
        self.launch_startup = QCheckBox("Launch Waky when Windows starts")
        self.start_minimized = QCheckBox("Start minimized")
        self.start_hidden_no_terminal = QCheckBox("Start hidden, no terminal window")
        self.show_floating_bar_on_startup = QCheckBox("Show the floating pill on startup")
        self.sound_effects = QCheckBox("Sound effects")
        for widget in (self.launch_startup, self.start_minimized, self.start_hidden_no_terminal, self.show_floating_bar_on_startup, self.sound_effects):
            form.addRow(widget)
        self.appearance = QComboBox()
        for label, key in (("Light", "light"), ("Dark", "dark"), ("Match Windows", "system")):
            self.appearance.addItem(label, key)
        self.appearance.currentIndexChanged.connect(lambda _i: self.appearance_changed.emit(self.appearance.currentData()))
        form.addRow("Appearance", self.appearance)

    # ---------- Floating Bar page ----------
    SWATCHES = (("Waky blue", "#2E62FF"), ("Sky", "#32ADE6"), ("Indigo", "#5E5CE6"), ("Pink", "#FF375F"), ("Orange", "#FF9F0A"), ("Green", "#30D158"), ("White", "#FFFFFF"))
    ANCHOR_GRID = (("top_left", 0, 0), ("top_center", 0, 1), ("top_right", 0, 2), ("middle_left", 1, 0), ("middle_right", 1, 2),
                   ("bottom_left", 2, 0), ("bottom_center", 2, 1), ("bottom_right", 2, 2))

    def _section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("section")
        return label

    def _floating_bar_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        fb = self.config_manager.settings.setdefault("floating_bar", {})
        accent = fb.get("accent", pill_styles.DEFAULT_ACCENT)
        self._fb_loading = False

        self.fb_preview = PillPreview(fb.get("style", pill_styles.DEFAULT_STYLE), accent, 1.0)
        self.fb_preview.setFixedHeight(96)
        lay.addWidget(self.fb_preview)

        lay.addSpacing(4)
        lay.addWidget(self._section("Style"))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.style_cards: dict[str, StyleCard] = {}
        for i, style in enumerate(pill_styles.STYLES.values()):
            card = StyleCard(style, accent)
            card.clicked.connect(self._fb_pick_style)
            grid.addWidget(card, i // 3, i % 3)
            self.style_cards[style.key] = card
        lay.addLayout(grid)

        lay.addSpacing(4)
        lay.addWidget(self._section("Colour"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.swatches: list[tuple[str, QPushButton]] = []
        for name, hexv in self.SWATCHES:
            btn = QPushButton()
            btn.setObjectName("swatch")
            btn.setCheckable(True)
            btn.setToolTip(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton#swatch {{ background: {hexv}; }}")
            btn.clicked.connect(lambda _c=False, h=hexv: self._fb_pick_color(h))
            row.addWidget(btn)
            self.swatches.append((hexv, btn))
        custom = QPushButton("Custom...")
        custom.setObjectName("plain")
        custom.clicked.connect(self._fb_custom_color)
        row.addWidget(custom)
        row.addStretch()
        lay.addLayout(row)

        lay.addSpacing(4)
        lay.addWidget(self._section("Size"))
        srow = QHBoxLayout()
        self.fb_size = QSlider(Qt.Horizontal)
        self.fb_size.setRange(60, 220)
        self.fb_size.setSingleStep(5)
        self.fb_size.setPageStep(10)
        self.fb_size_label = QLabel("100%")
        self.fb_size_label.setFixedWidth(54)
        self.fb_size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.fb_size.valueChanged.connect(self._fb_size_changed)
        srow.addWidget(self.fb_size, 1)
        srow.addWidget(self.fb_size_label)
        lay.addLayout(srow)

        lay.addSpacing(4)
        lay.addWidget(self._section("Where it appears"))
        self.pos_preset = QRadioButton("Same place every time Waky starts")
        self.pos_remember = QRadioButton("Remember where I drag it (hold Alt and drag)")
        self.pos_preset.toggled.connect(lambda _on: self._fb_position_changed())
        lay.addWidget(self.pos_preset)
        anchors = QGridLayout()
        anchors.setHorizontalSpacing(6)
        anchors.setVerticalSpacing(6)
        self.anchor_buttons: dict[str, QPushButton] = {}
        for key, r, c in self.ANCHOR_GRID:
            b = QPushButton()
            b.setObjectName("anchor")
            b.setCheckable(True)
            b.setFixedSize(46, 28)
            b.setToolTip(key.replace("_", " ").title())
            b.clicked.connect(lambda _c=False, k=key: self._fb_pick_anchor(k))
            anchors.addWidget(b, r, c)
            self.anchor_buttons[key] = b
        screen_frame = QFrame()
        screen_frame.setObjectName("miniScreen")
        sfl = QHBoxLayout(screen_frame)
        sfl.setContentsMargins(10, 10, 10, 10)
        sfl.addLayout(anchors)
        wrap = QHBoxLayout()
        wrap.addSpacing(26)
        wrap.addWidget(screen_frame)
        wrap.addStretch()
        lay.addLayout(wrap)
        mrow = QHBoxLayout()
        mrow.addSpacing(26)
        mlabel = QLabel("Distance from the edge")
        mlabel.setObjectName("sub")
        self.fb_margin = QSlider(Qt.Horizontal)
        self.fb_margin.setRange(0, 240)
        self.fb_margin.setFixedWidth(220)
        self.fb_margin_label = QLabel("40 px")
        self.fb_margin_label.setFixedWidth(54)
        self.fb_margin.valueChanged.connect(lambda _v: self._fb_position_changed())
        mrow.addWidget(mlabel)
        mrow.addWidget(self.fb_margin)
        mrow.addWidget(self.fb_margin_label)
        mrow.addStretch()
        lay.addLayout(mrow)
        lay.addWidget(self.pos_remember)

        lay.addSpacing(4)
        lay.addWidget(self._section("Behaviour"))
        self.always_on_top = QCheckBox("Keep the pill above other windows")
        self.alt_drag_only = QCheckBox("Drag only while holding Alt")
        lay.addWidget(self.always_on_top)
        lay.addWidget(self.alt_drag_only)
        reset = QPushButton("Put it back in its default place")
        reset.clicked.connect(self._fb_reset_position)
        lay.addWidget(reset, 0, Qt.AlignLeft)
        self.tabs.addTab(tab, "Floating Bar")

    def _fb_settings(self) -> dict:
        return self.config_manager.settings.setdefault("floating_bar", {})

    def _fb_commit(self) -> None:
        if self._fb_loading:
            return
        self.config_manager.save_settings()
        self.pill_style_changed.emit(self._fb_settings().get("style", pill_styles.DEFAULT_STYLE))

    def _fb_refresh_controls(self) -> None:
        fb = self._fb_settings()
        style, accent = fb.get("style", pill_styles.DEFAULT_STYLE), fb.get("accent", pill_styles.DEFAULT_ACCENT)
        style = pill_styles.get_style(style).key
        for key, card in self.style_cards.items():
            card.set_selected(key == style)
            card.preview.set_look(accent=accent)
        for hexv, btn in self.swatches:
            btn.setChecked(hexv.lower() == str(accent).lower())
        self.fb_preview.set_look(style, accent, max(0.6, min(1.6, fb.get("size", 100) / 100.0)))
        mode = fb.get("position_mode", "preset")
        self.pos_preset.blockSignals(True)
        self.pos_preset.setChecked(mode != "remember")
        self.pos_remember.setChecked(mode == "remember")
        self.pos_preset.blockSignals(False)
        for key, btn in self.anchor_buttons.items():
            btn.setChecked(key == fb.get("anchor", "bottom_center"))
            btn.setEnabled(mode != "remember")
        self.fb_margin.setEnabled(mode != "remember")

    def _fb_pick_style(self, key: str) -> None:
        self._fb_settings()["style"] = key
        self._fb_refresh_controls()
        self._fb_commit()

    def _fb_pick_color(self, hexv: str) -> None:
        self._fb_settings()["accent"] = hexv
        self._fb_refresh_controls()
        self._fb_commit()

    def _fb_custom_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._fb_settings().get("accent", pill_styles.DEFAULT_ACCENT)), self, "Pill colour")
        if color.isValid():
            self._fb_pick_color(color.name().upper())

    def _fb_size_changed(self, value: int) -> None:
        self.fb_size_label.setText(f"{value}%")
        self._fb_settings()["size"] = value
        self.fb_preview.set_look(scale=max(0.6, min(1.6, value / 100.0)))
        self._fb_commit()

    def _fb_pick_anchor(self, key: str) -> None:
        self._fb_settings()["anchor"] = key
        self._fb_settings()["position_mode"] = "preset"
        self._fb_refresh_controls()
        self._fb_commit()

    def _fb_position_changed(self) -> None:
        if self._fb_loading:
            return
        fb = self._fb_settings()
        fb["position_mode"] = "preset" if self.pos_preset.isChecked() else "remember"
        fb["margin"] = self.fb_margin.value()
        self.fb_margin_label.setText(f"{self.fb_margin.value()} px")
        self._fb_refresh_controls()
        self._fb_commit()

    def _fb_reset_position(self) -> None:
        fb = self._fb_settings()
        fb.update({"position_mode": "preset", "anchor": "bottom_center", "margin": 40})
        fb.pop("position", None)
        self._fb_load()
        self._fb_commit()

    def _fb_load(self) -> None:
        self._fb_loading = True
        fb = self._fb_settings()
        self.fb_size.setValue(int(fb.get("size", 100)))
        self.fb_size_label.setText(f"{self.fb_size.value()}%")
        self.fb_margin.setValue(int(fb.get("margin", 40)))
        self.fb_margin_label.setText(f"{self.fb_margin.value()} px")
        self.always_on_top.setChecked(self.config_manager.settings["general"].get("always_on_top", True))
        self.alt_drag_only.setChecked(fb.get("alt_drag_only", True))
        self._fb_refresh_controls()
        self._fb_loading = False

    def _hotkeys_tab(self) -> None:
        _, form = self._add_tab("Hotkeys")
        self.ptt_hotkey = HotkeyEdit()
        self.ptt_backup_hotkey = HotkeyEdit()
        self.toggle_hotkey = HotkeyEdit()
        self.cancel_hotkey = HotkeyEdit(allow_single=True)
        reset = QPushButton("Reset to Ctrl+Win/F8 defaults")
        reset.clicked.connect(self._reset_hotkeys)
        form.addRow("Push-to-talk", self.ptt_hotkey)
        form.addRow("Backup push-to-talk", self.ptt_backup_hotkey)
        form.addRow("Hands-free toggle", self.toggle_hotkey)
        form.addRow("Cancel", self.cancel_hotkey)
        form.addRow(reset)
        form.addRow(QLabel("Click a box, then press the keys you want (hold them together). Recommended: Ctrl+Win for dictation, F8 as backup, F9 for toggle."))

    def _audio_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.microphone = QComboBox()
        self.refresh_mics = QPushButton("Refresh device list")
        self.test_mic = QPushButton("Quick mic test")
        self.test_mic_3s = QPushButton("3-second mic test")
        self.test_result = QLabel("Not tested")
        self.trim_silence = QCheckBox("Trim silence at the start and end")
        self.keep_ready = QCheckBox("Keep the microphone ready (instant start, no clipped first word)")
        self.refresh_mics.clicked.connect(self._load_microphones)
        self.test_mic.clicked.connect(lambda: self._test_microphone(1.0))
        self.test_mic_3s.clicked.connect(lambda: self._test_microphone(3.0))
        form.addRow("Microphone", self.microphone)
        form.addRow(self.refresh_mics)
        form.addRow(self.test_mic, self.test_mic_3s)
        form.addRow("Input level", self.test_result)
        form.addRow(self.keep_ready)
        form.addRow(self.trim_silence)
        layout.addLayout(form)
        help_label = QLabel(MIC_HELP_TEXT)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.addStretch()
        self.tabs.addTab(tab, "Audio")

    def _transcription_tab(self) -> None:
        _, form = self._add_tab("Transcription")
        self.backend = QComboBox()
        self.backend.addItem("Groq API", "groq")
        self.backend.addItem("Local faster-whisper", "local")
        self.backend.addItem("Auto fallback", "auto_fallback")
        self.groq_model = QComboBox()
        self.groq_model.addItems(["whisper-large-v3-turbo", "whisper-large-v3"])
        self.model = QComboBox()
        self.model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.engine_mode = QComboBox()
        self.engine_mode.addItem("Safe CPU mode", "safe_cpu")
        self.engine_mode.addItem("Fast CUDA mode", "fast_cuda")
        self.engine_mode.addItem("Auto", "auto")
        self.safe_mode_implementation = QComboBox()
        self.safe_mode_implementation.addItem("isolated subprocess CPU", "isolated_subprocess")
        self.safe_mode_implementation.addItem("in-process CPU", "in_process_cpu")
        self.language_mode = QComboBox()
        for key, label in LANGUAGE_LABELS.items():
            self.language_mode.addItem(label, key)
        self.speed_mode = QComboBox()
        self.speed_mode.addItems(["fast", "balanced", "accurate"])
        self.speed_mode.currentTextChanged.connect(self._apply_accuracy_preset_to_controls)
        self.device_display = QLabel(self.transcriber.device_display())
        self.backend_display = QLabel("Active backend: not checked yet")
        form.addRow("Backend", self.backend)
        form.addRow("Groq model", self.groq_model)
        form.addRow("Transcription engine mode", self.engine_mode)
        form.addRow("Safe mode implementation", self.safe_mode_implementation)
        form.addRow("Local model", self.model)
        self.model_status = QLabel("")
        self.model_download_button = QPushButton("Download local model (offline fallback)")
        self.model_download_button.clicked.connect(self._download_local_model)
        self.model_download_finished.connect(self._model_download_done)
        self.model.currentTextChanged.connect(self._refresh_model_status)
        form.addRow(self.model_download_button, self.model_status)
        self._refresh_model_status()
        form.addRow("Device", self.device_display)
        form.addRow("Language", self.language_mode)
        form.addRow("Accuracy preset", self.speed_mode)
        form.addRow(self.backend_display)

    def _output_tab(self) -> None:
        _, form = self._add_tab("Output")
        self.default_mode = QComboBox()
        for key, label in MODE_LABELS.items():
            self.default_mode.addItem(label, key)
        self.auto_paste = QCheckBox("Auto-paste")
        self.preserve_clipboard = QCheckBox("Preserve clipboard")
        self.never_enter = QCheckBox("Never press Enter")
        self.never_enter.setEnabled(False)
        form.addRow("Default mode", self.default_mode)
        form.addRow(self.auto_paste)
        form.addRow(self.preserve_clipboard)
        form.addRow(self.never_enter)

    def _commands_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.voice_commands_enabled = QCheckBox("Enable Voice Commands")
        self.auto_translate_to_english = QCheckBox("Auto Translate to English")
        self.auto_fix_grammar = QCheckBox("Auto Fix Grammar")
        self.smart_selected_rewrite_enabled = QCheckBox("Smart Selected Text Rewrite")
        self.selected_rewrite_ai_mode = QComboBox()
        self.selected_rewrite_ai_mode.addItems(["auto", "cloud_if_available", "rule_based_only"])
        self.preserve_clipboard_after_selected_rewrite = QCheckBox("Preserve clipboard after selected rewrite")
        self.selected_capture_timeout_ms = QSpinBox()
        self.selected_capture_timeout_ms.setRange(100, 1000)
        self.selected_capture_timeout_ms.setSuffix(" ms")
        self.selected_rewrite_help = QLabel(
            "Select text anywhere, hold Ctrl+Win, speak commands, and Waky will replace the selection. "
            "No selection falls back to normal dictation."
        )
        self.selected_rewrite_help.setWordWrap(True)
        self.command_prompt_mode_enabled = QCheckBox("Enable Prompt Mode Command")
        self.command_bullet_points_enabled = QCheckBox("Enable Bullet Points Command")
        self.command_rewrite_humanizer_enabled = QCheckBox("Enable Rewrite & Humanizer Command")
        self.command_call_caps_small_enabled = QCheckBox("Enable Call Caps Small Command")
        self.command_professional_tone_enabled = QCheckBox("Enable Professional Tone Command")
        self.command_casual_tone_enabled = QCheckBox("Enable Casual Tone Command")
        self.command_write_email_enabled = QCheckBox("Enable Write Email Command")
        self.command_extend_enabled = QCheckBox("Enable Extend Command")
        for widget in (
            self.voice_commands_enabled,
            self.auto_translate_to_english,
            self.auto_fix_grammar,
            self.smart_selected_rewrite_enabled,
            self.preserve_clipboard_after_selected_rewrite,
            self.command_prompt_mode_enabled,
            self.command_bullet_points_enabled,
            self.command_rewrite_humanizer_enabled,
            self.command_call_caps_small_enabled,
            self.command_professional_tone_enabled,
            self.command_casual_tone_enabled,
            self.command_write_email_enabled,
            self.command_extend_enabled,
        ):
            form.addRow(widget)
        form.addRow("Selected rewrite AI mode", self.selected_rewrite_ai_mode)
        form.addRow("Selected capture timeout", self.selected_capture_timeout_ms)
        form.addRow(self.selected_rewrite_help)
        layout.addLayout(form)
        command_buttons = FlowLayout(spacing=8)
        self.command_list = QListWidget()
        self.custom_instructions = QPlainTextEdit()
        self.custom_instructions.setFixedHeight(80)
        self.custom_instructions.setPlaceholderText("Applies to everything you dictate. e.g. 'I am Nayan, a UX designer. Use simple English. Sign emails as Nayan.'")
        layout.addWidget(QLabel("My standing instructions (used for every dictation and rewrite)"))
        layout.addWidget(self.custom_instructions)
        layout.addWidget(QLabel("Modes / commands (say the trigger phrase while dictating)"))
        layout.addWidget(self.command_list)
        editor = QFormLayout()
        self.command_display_name = QLineEdit()
        self.command_enabled = QCheckBox("Enabled")
        self.command_triggers = QPlainTextEdit()
        self.command_triggers.setPlaceholderText("One trigger phrase per line")
        self.command_instruction = QPlainTextEdit()
        self.command_instruction.setPlaceholderText("Tell the AI what this mode does, e.g. 'Write a short blog post with a catchy title from what I said.'")
        self.command_output_format = QPlainTextEdit()
        self.command_output_format.setFixedHeight(70)
        self.command_output_format.setPlaceholderText("Optional layout, e.g. 'Subject: ...' then greeting, body, sign-off")
        self.command_priority = QSpinBox()
        self.command_priority.setRange(1, 999)
        editor.addRow("Display name", self.command_display_name)
        editor.addRow(self.command_enabled)
        editor.addRow("Trigger phrases", self.command_triggers)
        editor.addRow("Instruction for AI", self.command_instruction)
        editor.addRow("Output format", self.command_output_format)
        editor.addRow("Priority", self.command_priority)
        layout.addLayout(editor)
        self.command_list.currentRowChanged.connect(self._load_selected_command)
        self.open_commands_config = QPushButton("Open commands.json")
        self.save_command_edit = QPushButton("Save Command")
        self.add_command = QPushButton("Add Command")
        self.delete_command = QPushButton("Delete Command")
        self.reload_commands_config = QPushButton("Reload Commands")
        self.reset_commands_config = QPushButton("Reset Built-in Commands")
        self.open_commands_config.clicked.connect(self._open_commands_config)
        self.save_command_edit.clicked.connect(self._save_selected_command)
        self.add_command.clicked.connect(self._add_command)
        self.delete_command.clicked.connect(self._delete_command)
        self.reload_commands_config.clicked.connect(self._reload_commands_config)
        self.reset_commands_config.clicked.connect(self._reset_commands_config)
        command_buttons.addWidget(self.open_commands_config)
        command_buttons.addWidget(self.save_command_edit)
        command_buttons.addWidget(self.add_command)
        command_buttons.addWidget(self.delete_command)
        command_buttons.addWidget(self.reload_commands_config)
        command_buttons.addWidget(self.reset_commands_config)
        layout.addLayout(command_buttons)
        examples = QLabel(
            "Examples:\n"
            "- prompt mode make me a tool that cleans my PC safely\n"
            "- bullet points today I finished homepage design fixed navbar and updated hero section\n"
            "- rewrite and humanizer I cannot come today because urgent work came\n"
            "- professional tone I will send the file today\n"
            "- casual tone I will send the file today\n"
            "- write email tell sir I am not feeling well\n"
            "- extend I am not feeling well and cannot attend the exam"
        )
        examples.setWordWrap(True)
        layout.addWidget(examples)
        layout.addStretch()
        self.tabs.addTab(tab, "Commands")

    def _memory_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.local_memory_enabled = QCheckBox("Enable Local Memory")
        self.memory_active_project = QLineEdit()
        self.switch_memory_project = QPushButton("Switch Project")
        self.memory_save_transcript_summaries = QCheckBox("Save transcript summaries")
        self.memory_save_full_transcripts = QCheckBox("Save full transcripts")
        self.memory_save_selected_rewrite_examples = QCheckBox("Save selected rewrite examples")
        self.memory_use_cloud_for_summarization = QCheckBox("Use cloud to summarize memory")
        self.memory_auto_save_useful_vocabulary = QCheckBox("Auto-save useful vocabulary")
        for widget in (
            self.local_memory_enabled,
            self.memory_save_transcript_summaries,
            self.memory_save_full_transcripts,
            self.memory_save_selected_rewrite_examples,
            self.memory_use_cloud_for_summarization,
            self.memory_auto_save_useful_vocabulary,
        ):
            form.addRow(widget)
        form.addRow("Active Project", self.memory_active_project)
        form.addRow(self.switch_memory_project)
        layout.addLayout(form)

        buttons = FlowLayout(spacing=8)
        self.open_memory_folder = QPushButton("Open Memory Folder")
        self.add_memory_correction = QPushButton("Add Correction")
        self.add_memory_vocabulary = QPushButton("Add Vocabulary")
        self.add_memory_note = QPushButton("Add Memory Note")
        self.add_memory_preference = QPushButton("Add Writing Preference")
        self.add_memory_project_context = QPushButton("Add Project Context")
        self.summarize_memory_project = QPushButton("Summarize Active Project")
        self.clear_memory_button = QPushButton("Clear Memory")
        for button in (
            self.open_memory_folder,
            self.add_memory_correction,
            self.add_memory_vocabulary,
            self.add_memory_note,
            self.add_memory_preference,
            self.add_memory_project_context,
            self.summarize_memory_project,
            self.clear_memory_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.memory_summary_text = QPlainTextEdit()
        self.memory_summary_text.setReadOnly(True)
        layout.addWidget(self.memory_summary_text)
        self.open_memory_folder.clicked.connect(lambda: os.startfile(MEMORY_DIR))
        self.switch_memory_project.clicked.connect(self._switch_memory_project)
        self.add_memory_correction.clicked.connect(self._add_memory_correction)
        self.add_memory_vocabulary.clicked.connect(self._add_memory_vocabulary)
        self.add_memory_note.clicked.connect(self._add_memory_note)
        self.add_memory_preference.clicked.connect(self._add_memory_preference)
        self.add_memory_project_context.clicked.connect(self._add_memory_project_context)
        self.summarize_memory_project.clicked.connect(self._summarize_memory_project)
        self.clear_memory_button.clicked.connect(self._clear_memory)
        self.tabs.addTab(tab, "Memory")

    def _vocabulary_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.vocab_list = QListWidget()
        controls = FlowLayout(spacing=8)
        add = QPushButton("Add")
        remove = QPushButton("Remove")
        add.clicked.connect(self._add_vocab)
        remove.clicked.connect(lambda: self._remove_selected(self.vocab_list))
        controls.addWidget(add)
        controls.addWidget(remove)
        layout.addWidget(QLabel("Custom words"))
        layout.addWidget(self.vocab_list)
        layout.addLayout(controls)
        self.tabs.addTab(tab, "Vocabulary")

    def _snippets_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.snippets_enabled = QCheckBox("Enable snippets")
        self.snippet_search = QLineEdit()
        self.snippet_search.setPlaceholderText("Search snippets...")
        self.snippet_list = QListWidget()
        self.snippet_index_map: list[int] = []
        controls = FlowLayout(spacing=8)
        add = QPushButton("Add")
        edit = QPushButton("Edit")
        toggle = QPushButton("Enable/Disable")
        remove = QPushButton("Delete")
        import_file = QPushButton("Import CSV/TSV")
        open_file = QPushButton("Open snippets file")
        add.clicked.connect(self._add_snippet)
        edit.clicked.connect(self._edit_snippet)
        toggle.clicked.connect(self._toggle_snippet)
        remove.clicked.connect(self._remove_snippet)
        import_file.clicked.connect(self._import_snippets_file)
        open_file.clicked.connect(lambda: os.startfile(MEMORY_DIR / "snippets.json"))
        controls.addWidget(add)
        controls.addWidget(edit)
        controls.addWidget(toggle)
        controls.addWidget(remove)
        controls.addWidget(import_file)
        controls.addWidget(open_file)
        self.snippet_search.textChanged.connect(self._reload_snippet_list)
        layout.addWidget(QLabel("Create quick replacements such as 'my phone number' or 'paste my email'."))
        layout.addWidget(self.snippets_enabled)
        layout.addWidget(self.snippet_search)
        layout.addWidget(self.snippet_list)
        layout.addLayout(controls)
        self.tabs.addTab(tab, "Snippets")

    def _privacy_tab(self) -> None:
        _, form = self._add_tab("Privacy")
        self.save_recordings = QCheckBox("Save recordings")
        self.save_recordings.setEnabled(False)
        self.cloud_cleanup = QCheckBox("Cloud cleanup: Off by default. When enabled, transcript text may be sent to selected provider.")
        self.provider = QComboBox()
        self.provider.addItems(["local_basic", "groq", "openai", "openrouter", "gemini"])
        self.gemini_key = QLineEdit()
        self.groq_key = QLineEdit()
        self.openai_key = QLineEdit()
        self.openrouter_key = QLineEdit()
        for key in (self.gemini_key, self.groq_key, self.openai_key, self.openrouter_key):
            key.setEchoMode(QLineEdit.Password)
        self.logs_level = QComboBox()
        self.logs_level.addItems(["warning", "debug"])
        self.include_transcript_logs = QCheckBox("Include transcript in debug logs")
        form.addRow(self.save_recordings)
        form.addRow(self.cloud_cleanup)
        form.addRow("Provider", self.provider)
        form.addRow("Gemini API key", self.gemini_key)
        form.addRow("Groq API key", self.groq_key)
        form.addRow("OpenAI API key", self.openai_key)
        form.addRow("OpenRouter API key", self.openrouter_key)
        form.addRow("Logs level", self.logs_level)
        form.addRow(self.include_transcript_logs)
        self.provider.currentTextChanged.connect(self._update_provider_visibility)

    def _help_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        help_text = QLabel(
            "Use Waky:\n"
            "1. Click any text field.\n"
            "2. Hold F8.\n"
            "3. Speak.\n"
            "4. Release F8.\n"
            "5. Text will paste automatically.\n\n"
            "F9 toggles hands-free mode. Esc cancels/resets."
        )
        help_text.setWordWrap(True)
        help_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(help_text)
        layout.addStretch()
        self.tabs.addTab(tab, "Help")

    def _diagnostics_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = FlowLayout(spacing=8)
        self.hotkey_test = QPushButton("Hotkey Test")
        self.mic_diag_test = QPushButton("Microphone Test")
        self.paste_test = QPushButton("Run Paste Test")
        self.transcription_test = QPushButton("Transcription Test")
        self.groq_test = QPushButton("Test Groq API")
        self.force_reset = QPushButton("Force Reset Pipeline")
        self.command_memory_test = QPushButton("Test Command Rewrite + Memory")
        self.show_memory_summary = QPushButton("Test Memory Load")
        self.refresh_diag = QPushButton("Refresh")
        self.open_logs = QPushButton("Open logs folder")
        self.copy_diag = QPushButton("Copy diagnostics summary")
        self.hotkey_test.clicked.connect(self.hotkey_test_requested.emit)
        self.mic_diag_test.clicked.connect(lambda: self._test_microphone(3.0))
        self.paste_test.clicked.connect(self.paste_test_requested.emit)
        self.transcription_test.clicked.connect(self.transcription_test_requested.emit)
        self.groq_test.clicked.connect(self.groq_test_requested.emit)
        self.force_reset.clicked.connect(self.force_reset_requested.emit)
        self.command_memory_test.clicked.connect(self._test_command_rewrite_memory)
        self.show_memory_summary.clicked.connect(self._show_memory_summary_diagnostics)
        self.refresh_diag.clicked.connect(self.refresh_diagnostics)
        self.open_logs.clicked.connect(lambda: os.startfile(LOG_DIR))
        self.copy_diag.clicked.connect(self._copy_diagnostics)
        for button in (self.hotkey_test, self.mic_diag_test, self.paste_test, self.transcription_test, self.groq_test, self.force_reset):
            controls.addWidget(button)
        layout.addLayout(controls)
        extra = FlowLayout(spacing=8)
        for button in (self.command_memory_test, self.show_memory_summary, self.refresh_diag, self.open_logs, self.copy_diag):
            extra.addWidget(button)
        layout.addLayout(extra)
        self.diagnostics_text = QPlainTextEdit()
        self.diagnostics_text.setReadOnly(True)
        layout.addWidget(self.diagnostics_text)
        self.tabs.addTab(tab, "Diagnostics")

    def load_values(self) -> None:
        s = self.config_manager.settings
        general = s["general"]
        self.launch_startup.setChecked(general["launch_on_startup"])
        self.start_minimized.setChecked(general["start_minimized"])
        self.start_hidden_no_terminal.setChecked(general.get("start_hidden_no_terminal", True))
        self.show_floating_bar_on_startup.setChecked(general.get("show_floating_bar_on_startup", True))
        self.sound_effects.setChecked(general["sound_effects"])
        self.always_on_top.setChecked(general["always_on_top"])
        self.appearance.blockSignals(True)
        self.appearance.setCurrentIndex(max(0, self.appearance.findData(general.get("appearance", "light"))))
        self.appearance.blockSignals(False)
        self._fb_load()
        self.ptt_hotkey.setText(s["hotkeys"]["push_to_talk"])
        self.ptt_backup_hotkey.setText(s["hotkeys"].get("push_to_talk_backup", "<f8>"))
        self.toggle_hotkey.setText(s["hotkeys"]["toggle_recording"])
        self.cancel_hotkey.setText(s["hotkeys"]["cancel"])
        self.trim_silence.setChecked(s["audio"]["silence_trimming"])
        self.keep_ready.setChecked(s["audio"].get("keep_ready", True))
        self.backend.setCurrentIndex(max(0, self.backend.findData(s["transcription"].get("backend", "auto_fallback"))))
        self.groq_model.setCurrentText(s["transcription"].get("groq_model", "whisper-large-v3-turbo"))
        self.model.setCurrentText(s["transcription"]["model"])
        self.engine_mode.setCurrentIndex(max(0, self.engine_mode.findData(s["transcription"].get("engine_mode", "safe_cpu"))))
        self.safe_mode_implementation.setCurrentIndex(max(0, self.safe_mode_implementation.findData(s["transcription"].get("safe_mode_implementation", "isolated_subprocess"))))
        self.speed_mode.setCurrentText(s["transcription"]["speed_mode"])
        self.language_mode.setCurrentIndex(max(0, self.language_mode.findData(s["transcription"]["language_mode"])))
        self.default_mode.setCurrentIndex(max(0, self.default_mode.findData(s["output"]["default_mode"])))
        self.auto_paste.setChecked(s["output"]["auto_paste"])
        self.preserve_clipboard.setChecked(s["output"]["preserve_clipboard"])
        self.never_enter.setChecked(True)
        commands = s.get("command_processing", {})
        self.voice_commands_enabled.setChecked(commands.get("voice_commands_enabled", True))
        self.auto_translate_to_english.setChecked(commands.get("auto_translate_to_english", True))
        self.auto_fix_grammar.setChecked(commands.get("auto_fix_grammar", True))
        self.local_memory_enabled.setChecked(commands.get("local_memory_enabled", True))
        self.memory_active_project.setText(get_active_project() or commands.get("memory_active_project", "general"))
        self.memory_save_transcript_summaries.setChecked(commands.get("memory_save_transcript_summaries", True))
        self.memory_save_full_transcripts.setChecked(commands.get("memory_save_full_transcripts", False))
        self.memory_save_selected_rewrite_examples.setChecked(commands.get("memory_save_selected_rewrite_examples", False))
        self.memory_use_cloud_for_summarization.setChecked(commands.get("memory_use_cloud_for_summarization", True))
        self.memory_auto_save_useful_vocabulary.setChecked(commands.get("memory_auto_save_useful_vocabulary", True))
        self.smart_selected_rewrite_enabled.setChecked(commands.get("smart_selected_rewrite_enabled", True))
        self.selected_rewrite_ai_mode.setCurrentText(commands.get("selected_rewrite_ai_mode", "auto"))
        self.preserve_clipboard_after_selected_rewrite.setChecked(commands.get("preserve_clipboard_after_selected_rewrite", True))
        self.selected_capture_timeout_ms.setValue(int(commands.get("selected_capture_timeout_ms", 250) or 250))
        self.command_prompt_mode_enabled.setChecked(commands.get("command_prompt_mode_enabled", True))
        self.command_bullet_points_enabled.setChecked(commands.get("command_bullet_points_enabled", True))
        self.command_rewrite_humanizer_enabled.setChecked(commands.get("command_rewrite_humanizer_enabled", True))
        self.command_call_caps_small_enabled.setChecked(commands.get("command_call_caps_small_enabled", True))
        self.command_professional_tone_enabled.setChecked(commands.get("command_professional_tone_enabled", True))
        self.command_casual_tone_enabled.setChecked(commands.get("command_casual_tone_enabled", True))
        self.command_write_email_enabled.setChecked(commands.get("command_write_email_enabled", True))
        self.command_extend_enabled.setChecked(commands.get("command_extend_enabled", True))
        self.custom_instructions.setPlainText(str(commands.get("custom_instructions", "")))
        self.cloud_cleanup.setChecked(s["privacy"]["cloud_cleanup"])
        self.provider.setCurrentText(s["privacy"]["provider"])
        self.logs_level.setCurrentText(s["privacy"]["logs_level"])
        self.include_transcript_logs.setChecked(s["privacy"]["include_transcript_in_logs"])
        self.gemini_key.setText(s["providers"]["gemini"]["api_key"])
        self.groq_key.setText(s["providers"]["groq"]["api_key"])
        self.openai_key.setText(s["providers"]["openai"]["api_key"])
        self.openrouter_key.setText(s["providers"].get("openrouter", {}).get("api_key", ""))
        self.snippets_enabled.setChecked(self.config_manager.snippets.get("enabled", True))
        self._load_microphones()
        self._reload_vocab_list()
        self._reload_snippet_list()
        self._reload_command_list()
        self._refresh_memory_summary()
        self._update_provider_visibility()
        self.refresh_diagnostics()

    def save_values(self) -> None:
        s = self.config_manager.settings
        s["general"].update(
            {
                "launch_on_startup": self.launch_startup.isChecked(),
                "start_minimized": self.start_minimized.isChecked(),
                "start_hidden_no_terminal": self.start_hidden_no_terminal.isChecked(),
                "show_floating_bar_on_startup": self.show_floating_bar_on_startup.isChecked(),
                "sound_effects": self.sound_effects.isChecked(),
                "always_on_top": self.always_on_top.isChecked(),
                "appearance": self.appearance.currentData() or "system",
            }
        )
        s.setdefault("floating_bar", {})["alt_drag_only"] = self.alt_drag_only.isChecked()
        s["hotkeys"].update(
            {
                "push_to_talk": self.ptt_hotkey.text().strip() or "<ctrl>+<win>",
                "push_to_talk_backup": self.ptt_backup_hotkey.text().strip() or "<f8>",
                "toggle_recording": self.toggle_hotkey.text().strip() or "<f9>",
                "cancel": self.cancel_hotkey.text().strip() or "<esc>",
            }
        )
        s["audio"]["microphone"] = self.microphone.currentData()
        s["audio"]["silence_trimming"] = self.trim_silence.isChecked()
        s["audio"]["keep_ready"] = self.keep_ready.isChecked()
        s["transcription"]["backend"] = self.backend.currentData()
        s["transcription"]["groq_model"] = self.groq_model.currentText()
        s["transcription"]["model"] = self.model.currentText()
        s["transcription"]["engine_mode"] = self.engine_mode.currentData()
        s["transcription"]["safe_mode_implementation"] = self.safe_mode_implementation.currentData()
        s["transcription"]["language_mode"] = self.language_mode.currentData()
        s["transcription"]["speed_mode"] = self.speed_mode.currentText()
        s["output"]["default_mode"] = self.default_mode.currentData()
        s["output"]["auto_paste"] = self.auto_paste.isChecked()
        s["output"]["preserve_clipboard"] = self.preserve_clipboard.isChecked()
        s["output"]["never_press_enter"] = True
        s.setdefault("command_processing", {}).update(
            {
                "voice_commands_enabled": self.voice_commands_enabled.isChecked(),
                "custom_instructions": self.custom_instructions.toPlainText().strip(),
                "auto_translate_to_english": self.auto_translate_to_english.isChecked(),
                "auto_fix_grammar": self.auto_fix_grammar.isChecked(),
                "local_memory_enabled": self.local_memory_enabled.isChecked(),
                "memory_active_project": self.memory_active_project.text().strip() or "general",
                "memory_save_transcript_summaries": self.memory_save_transcript_summaries.isChecked(),
                "memory_save_full_transcripts": self.memory_save_full_transcripts.isChecked(),
                "memory_save_selected_rewrite_examples": self.memory_save_selected_rewrite_examples.isChecked(),
                "memory_use_cloud_for_summarization": self.memory_use_cloud_for_summarization.isChecked(),
                "memory_auto_save_useful_vocabulary": self.memory_auto_save_useful_vocabulary.isChecked(),
                "store_full_transcripts_for_learning": self.memory_save_full_transcripts.isChecked(),
                "store_selected_text_history": False,
                "store_rewrite_examples": self.memory_save_selected_rewrite_examples.isChecked(),
                "save_only_manual_corrections": True,
                "smart_selected_rewrite_enabled": self.smart_selected_rewrite_enabled.isChecked(),
                "selected_rewrite_ai_mode": self.selected_rewrite_ai_mode.currentText(),
                "preserve_clipboard_after_selected_rewrite": self.preserve_clipboard_after_selected_rewrite.isChecked(),
                "selected_capture_timeout_ms": self.selected_capture_timeout_ms.value(),
                "selected_text_rewrite_enabled": False,
                "command_prompt_mode_enabled": self.command_prompt_mode_enabled.isChecked(),
                "command_bullet_points_enabled": self.command_bullet_points_enabled.isChecked(),
                "command_rewrite_humanizer_enabled": self.command_rewrite_humanizer_enabled.isChecked(),
                "command_call_caps_small_enabled": self.command_call_caps_small_enabled.isChecked(),
                "command_professional_tone_enabled": self.command_professional_tone_enabled.isChecked(),
                "command_casual_tone_enabled": self.command_casual_tone_enabled.isChecked(),
                "command_write_email_enabled": self.command_write_email_enabled.isChecked(),
                "command_extend_enabled": self.command_extend_enabled.isChecked(),
            }
        )
        s["privacy"]["save_recordings"] = False
        s["privacy"]["cloud_cleanup"] = self.cloud_cleanup.isChecked()
        s["privacy"]["provider"] = self.provider.currentText()
        s["privacy"]["logs_level"] = self.logs_level.currentText()
        s["privacy"]["include_transcript_in_logs"] = self.include_transcript_logs.isChecked()
        s["providers"]["gemini"]["api_key"] = self.gemini_key.text()
        s["providers"]["groq"]["api_key"] = self.groq_key.text()
        s["providers"]["openai"]["api_key"] = self.openai_key.text()
        s["providers"].setdefault("openrouter", {"enabled": False, "api_key": ""})["api_key"] = self.openrouter_key.text()
        self.config_manager.snippets["enabled"] = self.snippets_enabled.isChecked()
        self.config_manager.save_all()
        set_active_project(s.get("command_processing", {}).get("memory_active_project", "general"))
        try:
            StartupManager(self.config_manager.config_dir.parent / "start_waky_hidden.vbs", self.logger).set_enabled(self.launch_startup.isChecked())
        except Exception:
            self.logger.warning("Could not update startup setting", exc_info=True)
        self.settings_changed.emit()
        self.refresh_diagnostics()
        QMessageBox.information(self, "Waky", "Settings saved.")

    def _refresh_model_status(self, *_args) -> None:
        name = self.model.currentText()
        if model_manager.is_downloaded(name):
            self.model_status.setText(f"{name}: downloaded, ready offline")
            self.model_download_button.setEnabled(False)
        else:
            self.model_status.setText(f"{name}: not downloaded ({model_manager.size_label(name)})")
            self.model_download_button.setEnabled(True)

    def _download_local_model(self) -> None:
        name = self.model.currentText()
        self.model_download_button.setEnabled(False)
        self.model_status.setText(f"Downloading {name} ({model_manager.size_label(name)})... keep Waky open")

        def work() -> None:
            try:
                model_manager.download(name)
                self.model_download_finished.emit("")
            except Exception as exc:
                self.model_download_finished.emit(str(exc))

        threading.Thread(target=work, daemon=True, name="waky-model-download").start()

    def _model_download_done(self, error: str) -> None:
        if error:
            self.model_status.setText(f"Download failed: {error}")
            self.model_download_button.setEnabled(True)
        else:
            self._refresh_model_status()

    def refresh_diagnostics(self) -> None:
        self.device_display.setText(self.transcriber.device_display())
        self.backend_display.setText(self._active_backend_label())
        self.diagnostics_text.setPlainText(self.diagnostics.summary())

    def _active_backend_label(self) -> str:
        transcription = self.config_manager.settings.get("transcription", {})
        backend = transcription.get("backend", "auto_fallback")
        groq_key = self.config_manager.settings.get("providers", {}).get("groq", {}).get("api_key", "").strip()
        if backend == "groq" or (backend == "auto_fallback" and groq_key):
            return f"Active backend: Groq {transcription.get('groq_model', 'whisper-large-v3-turbo')}"
        return f"Active backend: Local faster-whisper {transcription.get('model', 'base')} {self.transcriber.device_display()}"

    def _apply_accuracy_preset_to_controls(self, preset: str) -> None:
        if preset == "fast":
            self.groq_model.setCurrentText("whisper-large-v3-turbo")
            self.model.setCurrentText("base")
        elif preset == "balanced":
            self.groq_model.setCurrentText("whisper-large-v3-turbo")
            self.model.setCurrentText("small")
        elif preset == "accurate":
            self.groq_model.setCurrentText("whisper-large-v3")
            self.model.setCurrentText("large-v3")

    def append_diagnostics(self, message: str) -> None:
        self.refresh_diagnostics()
        self.diagnostics_text.appendPlainText(f"\n{message}")

    def _copy_diagnostics(self) -> None:
        self.diagnostics.copy_summary()
        self.append_diagnostics("Diagnostics summary copied to clipboard.")

    def _test_command_rewrite_memory(self) -> None:
        from .command_processor import process_text
        from .local_memory import get_forbidden_phrases

        sample = "write email tell sir I am not feeling well so I cannot attend tomorrow exam please help"
        output = process_text(sample, self.config_manager.settings, custom_commands=self.config_manager.custom_commands)
        forbidden_hit = any(phrase.lower() in output.lower() for phrase in get_forbidden_phrases())
        engine = "groq_chat" if self.config_manager.settings.get("providers", {}).get("groq", {}).get("api_key", "").strip() else "rule_based"
        self.append_diagnostics(
            "\nCommand rewrite + memory test\n"
            f"Engine used: {engine}\n"
            "Memory loaded: true\n"
            f"Forbidden phrase check passed: {not forbidden_hit}\n"
            f"Fallback used: {engine == 'rule_based'}\n\n"
            f"Output preview:\n{output}"
        )

    def _show_memory_summary_diagnostics(self) -> None:
        summary = memory_summary(self.config_manager.settings)
        self.append_diagnostics(
            "\nMemory summary\n"
            f"Enabled: {summary['memory_enabled']}\n"
            f"Active project: {summary['active_project']}\n"
            f"Custom vocabulary: {summary['custom_vocabulary_count']}\n"
            f"Corrections: {summary['corrections_count']}\n"
            f"Preferences: {summary['preferences_count']}\n"
            f"Forbidden phrases: {summary['forbidden_phrases_count']}\n"
            f"Project summary exists: {summary['project_summary_exists']}\n"
            f"Folder: {summary['memory_dir']}"
        )

    def _load_microphones(self) -> None:
        self.microphone.clear()
        self.microphone.addItem("System default", None)
        selected = self.config_manager.get("audio.microphone")
        try:
            for mic in self.recorder.list_microphones():
                rate = mic.get("default_samplerate") or "unknown rate"
                self.microphone.addItem(f"{mic['index']}: {mic['name']} ({rate} Hz)", mic["index"])
        except Exception as exc:
            self.logger.warning("Could not list microphones", exc_info=True)
            self.test_result.setText(f"Device list failed: {exc}")
        idx = self.microphone.findData(selected)
        if idx >= 0:
            self.microphone.setCurrentIndex(idx)

    def _test_microphone(self, seconds: float) -> None:
        try:
            result = self.recorder.record_test(seconds)
            label = f"{result.message}; level={result.level:.3f}; rate={result.sample_rate or 'n/a'}"
            self.test_result.setText(label)
            self.diagnostics.mark_microphone(label)
            self.refresh_diagnostics()
            if not result.ok:
                QMessageBox.warning(self, "Microphone test", f"{label}\n\n{MIC_HELP_TEXT}")
        except Exception as exc:
            self.test_result.setText("Microphone failed")
            self.diagnostics.mark_microphone(f"Failed: {exc}")
            self.refresh_diagnostics()
            QMessageBox.warning(self, "Microphone error", f"{exc}\n\n{MIC_HELP_TEXT}")

    def _refresh_memory_summary(self) -> None:
        summary = memory_summary(self.config_manager.settings)
        self.memory_summary_text.setPlainText(
            "\n".join(
                [
                    "Local memory summary",
                    f"Enabled: {summary['memory_enabled']}",
                    f"Active project: {summary['active_project']}",
                    f"Custom vocabulary: {summary['custom_vocabulary_count']}",
                    f"Corrections: {summary['corrections_count']}",
                    f"Preferences: {summary['preferences_count']}",
                    f"Forbidden phrases: {summary['forbidden_phrases_count']}",
                    f"Project summary exists: {summary['project_summary_exists']}",
                    f"Folder: {summary['memory_dir']}",
                ]
            )
        )

    def _switch_memory_project(self) -> None:
        set_active_project(self.memory_active_project.text().strip() or "general")
        self.config_manager.settings.setdefault("command_processing", {})["memory_active_project"] = get_active_project()
        self.memory_active_project.setText(get_active_project())
        self.config_manager.save_settings()
        self._refresh_memory_summary()

    def _add_memory_correction(self) -> None:
        wrong, ok = QInputDialog.getText(self, "Add correction", "Wrong phrase")
        if not ok or not wrong.strip():
            return
        correct, ok = QInputDialog.getText(self, "Add correction", "Correct phrase")
        if not ok or not correct.strip():
            return
        note, ok = QInputDialog.getText(self, "Add correction", "Note (optional)")
        add_correction(wrong, correct, note if ok else "")
        self._refresh_memory_summary()

    def _add_memory_vocabulary(self) -> None:
        term, ok = QInputDialog.getText(self, "Add vocabulary", "Term")
        if not ok or not term.strip():
            return
        note, ok = QInputDialog.getText(self, "Add vocabulary", "Notes (optional)")
        add_vocabulary_item(term, note if ok else "")
        self._refresh_memory_summary()

    def _add_memory_note(self) -> None:
        text, ok = QInputDialog.getText(self, "Add memory note", "Note")
        if ok and text.strip():
            add_memory_note(text)
            self._refresh_memory_summary()

    def _add_memory_preference(self) -> None:
        text, ok = QInputDialog.getText(self, "Add writing preference", "Preference")
        if ok and text.strip():
            add_preference(text)
            self._refresh_memory_summary()

    def _add_memory_project_context(self) -> None:
        text, ok = QInputDialog.getText(self, "Add project context", "Context note")
        if ok and text.strip():
            add_project_context(text)
            self._refresh_memory_summary()

    def _summarize_memory_project(self) -> None:
        summarize_project_memory(get_active_project())
        self._refresh_memory_summary()

    def _clear_memory(self) -> None:
        confirmed = QMessageBox.question(self, "Clear memory", "Restore memory files to defaults?")
        if confirmed == QMessageBox.Yes:
            clear_memory()
            self._refresh_memory_summary()

    def _reset_hotkeys(self) -> None:
        self.ptt_hotkey.setText("<ctrl>+<win>")
        self.ptt_backup_hotkey.setText("<f8>")
        self.toggle_hotkey.setText("<f9>")
        self.cancel_hotkey.setText("<esc>")

    def _reload_vocab_list(self) -> None:
        self.vocab_list.clear()
        self.vocab_list.addItems(self.config_manager.vocabulary.get("words", []))

    def _reload_snippet_list(self) -> None:
        self.snippet_list.clear()
        self.snippet_index_map = []
        query = self.snippet_search.text().strip().lower() if hasattr(self, "snippet_search") else ""
        for index, snippet in enumerate(self.config_manager.snippets.get("snippets", [])):
            label = self._snippet_label(snippet)
            haystack = label.lower()
            if query and query not in haystack:
                continue
            prefix = "on" if snippet.get("enabled", True) else "off"
            self.snippet_list.addItem(f"[{prefix}] {label}")
            self.snippet_index_map.append(index)

    def _add_vocab(self) -> None:
        word, ok = QInputDialog.getText(self, "Add word", "Word")
        if ok and word.strip():
            self.config_manager.vocabulary.setdefault("words", []).append(word.strip())
            self.config_manager.save_vocabulary()
            self._reload_vocab_list()

    def _remove_selected(self, widget: QListWidget) -> None:
        row = widget.currentRow()
        if row < 0:
            return
        if widget is self.vocab_list:
            del self.config_manager.vocabulary["words"][row]
            self.config_manager.save_vocabulary()
            self._reload_vocab_list()
        else:
            self._remove_snippet()

    def _add_snippet(self) -> None:
        snippet = self._snippet_dialog("Add snippet")
        if not snippet:
            return
        self.config_manager.snippets.setdefault("snippets", []).append(snippet)
        self.config_manager.save_snippets()
        self._reload_snippet_list()

    def _edit_snippet(self) -> None:
        index = self._selected_snippet_index()
        if index is None:
            return
        snippet = self.config_manager.snippets["snippets"][index]
        updated = self._snippet_dialog("Edit snippet", snippet)
        if not updated:
            return
        snippet.clear()
        snippet.update(updated)
        self.config_manager.save_snippets()
        self._reload_snippet_list()

    def _remove_snippet(self) -> None:
        index = self._selected_snippet_index()
        if index is None:
            return
        confirmed = QMessageBox.question(self, "Delete snippet", "Delete the selected snippet?")
        if confirmed != QMessageBox.Yes:
            return
        del self.config_manager.snippets["snippets"][index]
        self.config_manager.save_snippets()
        self._reload_snippet_list()

    def _toggle_snippet(self) -> None:
        index = self._selected_snippet_index()
        if index is None:
            return
        snippet = self.config_manager.snippets["snippets"][index]
        snippet["enabled"] = not snippet.get("enabled", True)
        self.config_manager.save_snippets()
        self._reload_snippet_list()

    def _selected_snippet_index(self) -> int | None:
        row = self.snippet_list.currentRow()
        if row < 0 or row >= len(self.snippet_index_map):
            return None
        return self.snippet_index_map[row]

    def _snippet_label(self, snippet: dict) -> str:
        name = str(snippet.get("name") or snippet.get("trigger") or "Snippet")
        triggers = self._snippet_triggers(snippet)
        trigger_text = ", ".join(triggers)
        value = str(snippet.get("value", ""))
        category = str(snippet.get("category", "")).strip()
        category_text = f" [{category}]" if category else ""
        return f"{name}{category_text} | {trigger_text} -> {value}"

    def _snippet_triggers(self, snippet: dict) -> list[str]:
        triggers = snippet.get("triggers")
        if isinstance(triggers, list):
            result = [str(trigger).strip() for trigger in triggers if str(trigger).strip()]
        else:
            trigger = str(snippet.get("trigger", "")).strip()
            result = [trigger] if trigger else []
        return result

    def _snippet_dialog(self, title: str, snippet: dict | None = None) -> dict | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        form = QFormLayout(dialog)
        name = QLineEdit(str((snippet or {}).get("name", "")))
        triggers = QPlainTextEdit()
        triggers.setPlainText("\n".join(self._snippet_triggers(snippet or {})))
        value = QPlainTextEdit()
        value.setPlainText(str((snippet or {}).get("value", "")))
        category = QLineEdit(str((snippet or {}).get("category", "")))
        enabled = QCheckBox("Enabled")
        enabled.setChecked((snippet or {}).get("enabled", True))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow("Name", name)
        form.addRow("Trigger phrases\n(one per line)", triggers)
        form.addRow("Value", value)
        form.addRow("Category", category)
        form.addRow(enabled)
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        trigger_list = [line.strip() for line in triggers.toPlainText().replace(";", "\n").splitlines() if line.strip()]
        snippet_value = value.toPlainText().strip()
        if not trigger_list or not snippet_value:
            QMessageBox.warning(self, title, "Snippet needs at least one trigger and a value.")
            return None
        return {
            "name": name.text().strip() or trigger_list[0],
            "trigger": trigger_list[0],
            "triggers": trigger_list,
            "value": snippet_value,
            "enabled": enabled.isChecked(),
            "category": category.text().strip(),
        }

    def _import_snippets_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import snippets", "", "Snippet files (*.csv *.tsv *.txt);;All files (*.*)")
        if not path:
            return
        try:
            snippets = self._read_snippet_import(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import snippets", f"Could not import snippets:\n{exc}")
            return
        if not snippets:
            QMessageBox.information(self, "Import snippets", "No valid snippets found.")
            return
        preview = "\n".join(self._snippet_label(snippet) for snippet in snippets[:8])
        if len(snippets) > 8:
            preview += f"\n...and {len(snippets) - 8} more"
        confirmed = QMessageBox.question(self, "Import snippets", f"Import {len(snippets)} snippets?\n\n{preview}")
        if confirmed != QMessageBox.Yes:
            return
        existing = {trigger.lower() for item in self.config_manager.snippets.get("snippets", []) for trigger in self._snippet_triggers(item)}
        added = 0
        for snippet in snippets:
            triggers = self._snippet_triggers(snippet)
            if any(trigger.lower() in existing for trigger in triggers):
                continue
            self.config_manager.snippets.setdefault("snippets", []).append(snippet)
            existing.update(trigger.lower() for trigger in triggers)
            added += 1
        self.config_manager.save_snippets()
        self._reload_snippet_list()
        QMessageBox.information(self, "Import snippets", f"Imported {added} new snippets. Existing triggers were skipped.")

    def _read_snippet_import(self, path: str) -> list[dict]:
        text = open(path, "r", encoding="utf-8-sig", newline="").read()
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel_tab if path.lower().endswith(".tsv") else csv.excel
        rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
        snippets: list[dict] = []
        for row in rows:
            normalized = {str(key).strip().lower(): (value or "").strip() for key, value in row.items() if key}
            raw_triggers = normalized.get("triggers") or normalized.get("trigger") or normalized.get("phrase") or ""
            triggers = [part.strip() for part in raw_triggers.replace(";", ",").split(",") if part.strip()]
            value = normalized.get("value") or normalized.get("replacement") or normalized.get("text") or ""
            if not triggers or not value:
                continue
            enabled_text = (normalized.get("enabled") or "true").lower()
            snippets.append(
                {
                    "name": normalized.get("name") or triggers[0],
                    "trigger": triggers[0],
                    "triggers": triggers,
                    "value": value,
                    "enabled": enabled_text not in {"false", "0", "no", "off"},
                    "category": normalized.get("category", ""),
                }
            )
        return snippets

    def _open_commands_config(self) -> None:
        self.config_manager.save_custom_commands()
        try:
            os.startfile(self.config_manager.custom_commands_path)
        except Exception as exc:
            QMessageBox.warning(self, "Commands config", f"Could not open commands config:\n{exc}")

    def _reload_commands_config(self) -> None:
        try:
            self.config_manager.reload_custom_commands()
            self._reload_command_list()
            QMessageBox.information(self, "Commands config", "Commands config reloaded.")
        except Exception as exc:
            QMessageBox.warning(self, "Commands config", f"Could not reload commands config:\n{exc}")

    def _reset_commands_config(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Reset commands",
            "Reset built-in commands to defaults? This will overwrite command edits in custom_commands.json.",
        )
        if confirmed == QMessageBox.Yes:
            self.config_manager.reset_custom_commands()
            self._reload_command_list()
            QMessageBox.information(self, "Commands config", "Built-in commands reset to defaults.")

    def _command_items(self) -> list[dict]:
        return self.config_manager.custom_commands.setdefault("commands", [])

    def _reload_command_list(self) -> None:
        self.command_list.clear()
        for command in self._command_items():
            name = command.get("display_name") or command.get("name") or command.get("command_id") or command.get("id", "Command")
            enabled = "on" if command.get("enabled", True) else "off"
            self.command_list.addItem(f"[{enabled}] {name}")
        if self.command_list.count() and self.command_list.currentRow() < 0:
            self.command_list.setCurrentRow(0)

    def _load_selected_command(self, row: int) -> None:
        commands = self._command_items()
        if row < 0 or row >= len(commands):
            return
        command = commands[row]
        self.command_display_name.setText(command.get("display_name") or command.get("name") or "")
        self.command_enabled.setChecked(command.get("enabled", True))
        triggers = command.get("trigger_phrases") or command.get("triggers") or []
        self.command_triggers.setPlainText("\n".join(triggers))
        self.command_instruction.setPlainText(command.get("instruction_template") or command.get("instruction") or "")
        self.command_output_format.setPlainText(command.get("output_format") or "")
        self.command_priority.setValue(int(command.get("priority", 50)))

    def _save_selected_command(self) -> None:
        row = self.command_list.currentRow()
        commands = self._command_items()
        if row < 0 or row >= len(commands):
            return
        command = commands[row]
        command_id = command.get("command_id") or command.get("id") or self.command_display_name.text().strip().lower().replace(" ", "_")
        command["command_id"] = command_id
        command["display_name"] = self.command_display_name.text().strip() or command_id
        command["enabled"] = self.command_enabled.isChecked()
        command["trigger_phrases"] = [line.strip() for line in self.command_triggers.toPlainText().splitlines() if line.strip()]
        command["command_type"] = command.get("command_type", "custom")
        command["instruction_template"] = self.command_instruction.toPlainText().strip()
        command["output_format"] = self.command_output_format.toPlainText().strip()
        command["priority"] = self.command_priority.value()
        command.pop("id", None)
        command.pop("name", None)
        command.pop("triggers", None)
        command.pop("instruction", None)
        self.config_manager.save_custom_commands()
        self._reload_command_list()
        self.command_list.setCurrentRow(row)

    def _add_command(self) -> None:
        commands = self._command_items()
        index = len(commands) + 1
        commands.append(
            {
                "command_id": f"custom_command_{index}",
                "display_name": f"Custom Command {index}",
                "enabled": True,
                "trigger_phrases": [f"custom command {index}"],
                "command_type": "custom",
                "priority": 50,
                "instruction_template": "Rewrite the content according to this custom command while preserving meaning.",
                "output_format": "",
            }
        )
        self.config_manager.save_custom_commands()
        self._reload_command_list()
        self.command_list.setCurrentRow(len(commands) - 1)

    def _delete_command(self) -> None:
        row = self.command_list.currentRow()
        commands = self._command_items()
        if row < 0 or row >= len(commands):
            return
        confirmed = QMessageBox.question(self, "Delete command", "Delete the selected command?")
        if confirmed == QMessageBox.Yes:
            del commands[row]
            self.config_manager.save_custom_commands()
            self._reload_command_list()

    def _update_provider_visibility(self) -> None:
        selected = self.provider.currentText()
        self.gemini_key.setVisible(selected == "gemini")
        self.groq_key.setVisible(selected == "groq")
        self.openai_key.setVisible(selected == "openai")
        self.openrouter_key.setVisible(selected == "openrouter")
