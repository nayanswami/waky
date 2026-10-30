from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == "--transcribe-once":
    # Packaged build: the exe doubles as the isolated transcription worker (no Qt needed).
    from app.transcribe_worker import main as _transcribe_worker_main

    raise SystemExit(_transcribe_worker_main(sys.argv[2:]))

# High-DPI scaling stays on (Qt default) so the UI is the right size on 125% / 150% / 4K screens.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window.warning=false")

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from app.audio_recorder import AudioRecorder, AudioResult
from app.clipboard_inserter import ClipboardInserter
from app.command_processor import process_text as process_voice_commands
from app import app_profiles, http_pool, ios_theme, llm_engine, sounds, updater as updater_mod
from app.config_manager import ConfigManager
from app.diagnostics import DiagnosticsService
from app import local_memory
import pyperclip
from app.history import History, fix_pairs as history_fix_pairs, learn as history_learn
from app.stats import Stats
from app.whats_new import WhatsNewDialog
from app import __version__ as APP_VERSION
from app.hotkeys import HotkeyManager
from app.logger_setup import setup_logging
from app.selected_text_rewriter import capture_selected_text_safely, rewrite_selected_text
from app.startup_manager import StartupManager
from app.text_processor import TextProcessor
from app.transcriber import FasterWhisperTranscriber
from app.updater import UpdateChecker
from app.ui_floating_bar import FloatingBar, TrayController
from app.ui_onboarding import OnboardingWizard
from app.ui_settings import SettingsWindow
from app.utils import FROZEN, LOG_DIR, PROJECT_ROOT, RUNTIME_DIR


PID_FILE = RUNTIME_DIR / "waky.pid"


class AppSignals(QObject):
    status = Signal(str)
    error = Signal(str)
    paste_done = Signal(bool)
    recording_finished = Signal(object)
    diagnostics_message = Signal(str)
    processing_done = Signal(object)
    transcription_test_done = Signal(object)
    groq_test_done = Signal(object)
    paste_started = Signal(int)
    push_pressed = Signal()
    push_released = Signal()
    toggle_requested = Signal()
    cancel_hotkey_requested = Signal()
    paste_last_requested = Signal()
    learn_fix_requested = Signal()
    notify = Signal(str, str)
    push_tap = Signal()
    lock_changed = Signal(bool)


class AppState(str, Enum):
    OFF = "OFF"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    STOPPING = "STOPPING"
    TRANSCRIBING = "TRANSCRIBING"
    PASTING = "PASTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class WakyApp(QObject):
    def __init__(self, qt_app: QApplication) -> None:
        super().__init__()
        self.qt_app = qt_app
        self.config = ConfigManager()
        self.theme = ios_theme.ThemeManager(qt_app, self.config.get("general.appearance", "system"))
        self._write_pid_file()
        if os.environ.get("WAKY_DEBUG") == "1":
            self.config.settings["privacy"]["logs_level"] = "debug"
        self.logger = setup_logging(self.config.get("privacy.logs_level", "warning"))
        self._repair_startup_if_enabled()
        self.signals = AppSignals()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="waky-worker")
        self.recorder = AudioRecorder(self.config.settings, self.logger)
        self.transcriber = FasterWhisperTranscriber(self.config.settings, self.logger)
        self.transcriber.on_notice = lambda message: self.signals.diagnostics_message.emit(message)
        self.diagnostics = DiagnosticsService(self.config, self.recorder, self.transcriber, self.logger)
        self.processor = TextProcessor(self.config, self.logger)
        self.inserter = ClipboardInserter(self.config.settings, self.logger)
        self.settings_window: SettingsWindow | None = None
        self.onboarding: OnboardingWizard | None = None
        self.mode_override: str | None = self.config.get("output.default_mode", "clean_casual")
        self.processing_future: Future | None = None
        self.pipeline_id = 0
        self.active_pipeline_id = 0
        self.current_job_id = ""
        self.current_transcription_context: dict = {}
        self.current_input_mode: str | None = None
        self.selected_text_context: str | None = None
        self.selected_previous_clipboard = ""
        self.selected_had_clipboard = False
        self.cancel_requested = threading.Event()
        self.toggle_recording = False
        self.last_result = ""   # kept in memory only, never written to disk
        self.current_profile: dict | None = None
        self.current_app_exe = ""
        self.history = History()
        self.stats = Stats()
        self.cleaned_up = False
        self.state = AppState.IDLE
        self._state_lock = threading.RLock()

        self.bar = FloatingBar(self.config.settings)
        self.bar.settings_requested.connect(self.open_settings)
        self.bar.mic_test_requested.connect(self.open_settings_audio)
        self.bar.pause_requested.connect(self.toggle_pause)
        self.bar.position_changed.connect(self.save_bar_position)

        self.tray = TrayController(
            qt_app,
            self._make_icon(),
            self.open_settings,
            self.pause,
            self.resume,
            self.restart,
            lambda: self.reset_pipeline("tray force reset"),
            self.reset_floating_bar_position,
            self.set_bar_visibility,
            self.bar.visibility_mode,
            self.quit,
        )
        self.paste_last_action = self.tray.add_action("Paste Last Result", self.paste_last_result)
        self.tray.add_action("Review and teach Waky...", self.open_history)
        self.update_action = self.tray.add_action("Update available", self.open_updates, visible=False)
        self.signals.status.connect(self.bar.set_status)
        self.signals.paste_last_requested.connect(self.paste_last_result)
        self.signals.learn_fix_requested.connect(self.learn_from_selection)
        self.signals.notify.connect(lambda title, text: self.tray.notify(title, text))
        self.signals.push_tap.connect(self._handle_push_tap)
        self.signals.lock_changed.connect(self._handle_lock_changed)
        self.signals.error.connect(self._show_error)
        self.signals.recording_finished.connect(self._process_audio)
        self.signals.diagnostics_message.connect(self._append_diagnostics)
        self.signals.processing_done.connect(self._processing_done)
        self.signals.transcription_test_done.connect(self._transcription_test_done)
        self.signals.groq_test_done.connect(self._groq_test_done)
        self.signals.paste_started.connect(lambda pipeline_id: QTimer.singleShot(5_000, lambda: self._check_pipeline_timeout(pipeline_id, "paste", 5)))
        self.signals.push_pressed.connect(self._handle_push_pressed)
        self.signals.push_released.connect(self._handle_push_released)
        self.signals.toggle_requested.connect(self._handle_toggle_requested)
        self.signals.cancel_hotkey_requested.connect(self._handle_cancel_requested)

        self.logger.info("App start python=%s platform=%s cwd=%s", sys.version.split()[0], sys.platform, os.getcwd())
        self.logger.info("Selected model=%s", self.config.get("transcription.model", "base"))
        self.hotkeys = HotkeyManager(
            self.config.settings,
            self.logger,
            self.start_push_recording,
            self.stop_push_recording,
            self.toggle_recording_hotkey,
            self.cancel,
            self._hotkey_error,
            on_paste_last=self.signals.paste_last_requested.emit,
            on_learn_fix=self.signals.learn_fix_requested.emit,
            on_push_tap=self.signals.push_tap.emit,
            on_lock_changed=self.signals.lock_changed.emit,
        )
        self.hotkeys.start()
        self._mic_signature = (self.config.get("audio.keep_ready", True), self.config.get("audio.microphone"))
        self._start_background_warmup()
        self.show_floating_bar(startup=True, reset=False)

        self.updater = UpdateChecker(self.config, self)
        self.updater.update_found.connect(self._on_update_found)
        self.updater.installer_ready.connect(self._launch_update_installer)
        self.updater.install_failed.connect(self._on_update_failed)
        QTimer.singleShot(25_000, self.updater.auto_check)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self.updater.auto_check)
        self._update_timer.start(6 * 3600 * 1000)

        # The welcome tour appears once per install. Closing it counts as skipping, so a normal boot only shows the pill.
        returning_user = bool(self.config.get("general.onboarding_done", False) or self.config.get("general.onboarding_seen", False))
        if self.config.get("general.last_seen_version", "") != APP_VERSION:
            self.config.settings["general"]["last_seen_version"] = APP_VERSION
            self.config.save_settings()
            if returning_user:   # an update, not a fresh install: say what changed
                QTimer.singleShot(2500, self.show_whats_new)
        if not self.config.get("general.onboarding_done", False) and not self.config.get("general.onboarding_seen", False):
            self.config.settings["general"]["onboarding_seen"] = True
            self.config.save_settings()
            QTimer.singleShot(600, self.open_onboarding)

    @Slot(object)
    def _on_update_found(self, info) -> None:
        self.update_action.setText(f"Update to v{info.version}...")
        self.update_action.setVisible(True)
        if getattr(self, "_notified_version", "") != info.version:
            self._notified_version = info.version
            self.tray.notify("Waky update available", f"Version {info.version} is ready. Click to open the updater.", self.open_updates)

    @Slot(object)
    def _launch_update_installer(self, path) -> None:
        self.logger.info("Launching update installer %s", path)
        try:
            updater_mod.launch_installer(path)
        except Exception as exc:
            self.signals.error.emit(f"Could not start the installer: {exc}")
            return
        QTimer.singleShot(500, self.quit)

    @Slot(str)
    def _on_update_failed(self, message: str) -> None:
        self.logger.warning("Update failed: %s", message)
        self.tray.notify("Waky update failed", message)

    @Slot()
    def open_history(self) -> None:
        self.open_settings()
        if self.settings_window:
            self.settings_window.show_history()

    @Slot()
    def show_whats_new(self) -> None:
        dialog = WhatsNewDialog()
        dialog.open_insights.connect(self.open_insights)
        self._whats_new = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @Slot()
    def open_insights(self) -> None:
        self.open_settings()
        if self.settings_window:
            self.settings_window.tabs.go(self.settings_window.tabs.index_of("Insights"))

    @Slot()
    def open_updates(self) -> None:
        self.open_settings()
        if self.settings_window:
            self.settings_window.tabs.go(self.settings_window.tabs.index_of("Updates"))

    @Slot()
    def learn_from_selection(self) -> None:
        """The user fixed a dictated sentence by hand and selected it: compare it with what Waky heard and remember the fixes."""
        def work() -> None:
            deadline = time.monotonic() + 2.0
            while self.hotkeys.current_keys and time.monotonic() < deadline:   # wait for the keys to come up before copying
                time.sleep(0.05)
            time.sleep(0.1)
            capture = capture_selected_text_safely(preserve_clipboard=True, timeout_ms=250)
            if capture is None:
                self.signals.notify.emit("Waky", "Select the sentence you corrected, then press the Learn hotkey again.")
                return
            try:
                if capture.had_clipboard:
                    pyperclip.copy(capture.previous_clipboard)
            except Exception:
                pass
            final = capture.selected_text.strip()
            entry = self.history.best_match(final)
            if entry is None:
                self.signals.notify.emit("Waky", "That text does not look like a recent dictation, so there is nothing to learn from.")
                return
            pairs = history_fix_pairs(str(entry.get("heard", "")), str(entry.get("written", "")), final)
            if not pairs:
                self.signals.notify.emit("Waky", "No changed words found. Waky already wrote it that way.")
                return
            saved = history_learn(pairs)
            self.history.update_written(entry["id"], final)
            self.stats.add_taught(saved)
            listing = ", ".join(f"{a} -> {b}" for a, b in pairs[:3])
            self.signals.notify.emit("Waky learned " + (f"{saved} fix" if saved == 1 else f"{saved} fixes"), listing + ". It will use them from your next dictation.")

        self.executor.submit(work)

    @Slot()
    def paste_last_result(self) -> None:
        text = self.last_result
        if not text:
            self.tray.notify("Waky", "Nothing to paste yet. Dictate something first.")
            return

        def work() -> None:
            time.sleep(0.3)   # let the tray menu close and the previous window regain focus
            self.inserter.paste_text(text)

        self.executor.submit(work)

    @Slot()
    def open_onboarding(self) -> None:
        self.onboarding = OnboardingWizard(self.config)
        self.onboarding.settings_applied.connect(self.reload_settings)
        self.onboarding.finished_setup.connect(lambda open_settings: self.open_settings() if open_settings else None)
        self.onboarding.show()
        self.onboarding.raise_()
        self.onboarding.activateWindow()

    def _start_background_warmup(self) -> None:
        """Get everything slow out of the way before the first dictation: mic stream, TLS to Groq, local model."""
        def work() -> None:
            try:
                local_memory.ensure_memory_files()   # also removes the old built-in seed rules once
                if self.config.get("audio.keep_ready", True):
                    self.recorder.arm()
                key = llm_engine.get_api_key(self.config.settings)
                if key:
                    http_pool.warm(key)
                self.transcriber.prewarm()
            except Exception:
                self.logger.warning("Warm-up failed", exc_info=True)

        threading.Thread(target=work, daemon=True, name="waky-warmup").start()

    def _repair_startup_if_enabled(self) -> None:
        if not self.config.get("general.launch_on_startup", False):
            return
        try:
            StartupManager(PROJECT_ROOT / "start_waky_hidden.vbs", self.logger).repair_startup_entry()
        except Exception:
            self.logger.warning("[STARTUP] repair failed", exc_info=True)

    def _make_icon(self) -> QIcon:
        bundled = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "assets" / "waky.ico"
        if bundled.exists():
            return QIcon(str(bundled))
        pixmap = QPixmap(64, 64)
        pixmap.fill()
        painter = QPainter(pixmap)
        painter.setPen("black")
        painter.setBrush("black")
        painter.drawEllipse(8, 8, 48, 48)
        painter.setPen("white")
        painter.drawText(pixmap.rect(), 0x84, "W")
        painter.end()
        return QIcon(pixmap)

    def _write_pid_file(self) -> None:
        try:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    def _delete_pid_file(self) -> None:
        try:
            if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PID_FILE.unlink()
        except Exception:
            pass

    @Slot(str)
    def set_mode(self, mode: str) -> None:
        self.mode_override = mode
        self.config.set("output.default_mode", mode)

    @Slot(int, int)
    def save_bar_position(self, x: int, y: int) -> None:
        floating = self.config.settings.setdefault("floating_bar", {})
        if floating.get("position_mode", "preset") != "remember":
            return  # the pill returns to its chosen preset spot on every launch
        floating.update({"x": x, "y": y})
        floating["position"] = {"x": x, "y": y}
        self.config.save_settings()

    def show_floating_bar(self, startup: bool = False, reset: bool = False) -> None:
        self.config.settings.setdefault("general", {})["show_floating_bar_on_startup"] = True
        self.bar.set_status("Idle")
        pos = self.config.settings.get("floating_bar", {})
        saved_position = pos.get("position") if isinstance(pos.get("position"), dict) else {}
        x = saved_position.get("x", pos.get("x"))
        y = saved_position.get("y", pos.get("y"))
        self.bar.ensure_on_screen(x, y, reset=reset, logger=self.logger)
        self.bar.present()
        if pos.get("position_mode", "preset") == "remember":
            self.config.settings["floating_bar"].update({"x": self.bar.x(), "y": self.bar.y()})
            self.config.settings["floating_bar"]["position"] = {"x": self.bar.x(), "y": self.bar.y()}
        self.config.save_settings()
        self.logger.info("[FLOATING_BAR] startup_show=%s", str(startup).lower())
        self.logger.info("[FLOATING_BAR] visible=%s", str(self.bar.isVisible()).lower())
        if reset:
            self.logger.info("[FLOATING_BAR] reset_position=true")

    @Slot()
    def reset_floating_bar_position(self) -> None:
        self.show_floating_bar(startup=False, reset=True)

    def set_bar_visibility(self, mode: str) -> None:
        floating = self.config.settings.setdefault("floating_bar", {})
        floating["visibility"] = mode
        floating.pop("hidden", None)
        self.config.save_settings()
        if mode != "hidden":
            self.bar.set_status("Idle")

    def is_paused(self) -> bool:
        return self.config.get("general.paused", False)

    def _log_info(self, message: str, *args) -> None:
        if args:
            message = message % args
        self.logger.info(message)
        print(message, flush=True)

    def _transition(self, new_state: AppState) -> None:
        with self._state_lock:
            old_state = self.state
            if old_state == new_state:
                return
            self.state = new_state
        self._log_info("[STATE] %s -> %s", old_state.value, new_state.value)
        cue = {AppState.LISTENING: "start", AppState.STOPPING: "stop", AppState.SUCCESS: "done", AppState.ERROR: "error"}.get(new_state)
        if cue and self.config.get("general.sound_effects", False):
            sounds.play(cue)
        ui_status = {
            AppState.IDLE: "Idle",
            AppState.LISTENING: "Listening",
            AppState.OFF: "Off",
            AppState.STOPPING: "Processing",
            AppState.TRANSCRIBING: "Processing",
            AppState.PASTING: "Processing",
            AppState.SUCCESS: "Pasted",
            AppState.ERROR: "Error",
            AppState.CANCELLED: "Cancelled",
        }[new_state]
        self.signals.status.emit(ui_status)

    def _next_pipeline_id(self) -> int:
        with self._state_lock:
            self.pipeline_id += 1
            self.active_pipeline_id = self.pipeline_id
            return self.pipeline_id

    def reset_pipeline(self, reason: str) -> None:
        with self._state_lock:
            if self.recorder.is_recording:
                self.recorder.cancel()
            else:
                self.recorder.frames = []
            self.cancel_requested.clear()
            self.processing_future = None
            self.toggle_recording = False
            self.active_pipeline_id = 0
            self.current_job_id = ""
            self.current_transcription_context = {}
            self.current_input_mode = None
            self.selected_text_context = None
            self.selected_previous_clipboard = ""
            self.selected_had_clipboard = False
        self._transition(AppState.IDLE)
        self.hotkeys.clear_lock()
        self._log_info("[RESET] reason=%s", reason)
        self.signals.status.emit("Idle" if not self.is_paused() else "Paused")

    def _finish_and_reset(self, final_state: AppState, reason: str, delay_ms: int = 500) -> None:
        self._transition(final_state)
        QTimer.singleShot(delay_ms, lambda: self.reset_pipeline(reason))

    @Slot()
    def pause(self) -> None:
        self.config.set("general.paused", True)
        self.cancel()
        self.signals.status.emit("Paused")

    @Slot()
    def resume(self) -> None:
        self.config.set("general.paused", False)
        self.signals.status.emit("Idle")

    @Slot()
    def toggle_pause(self) -> None:
        if self.is_paused():
            self.resume()
        else:
            self.pause()

    def start_push_recording(self) -> bool:
        if QThread.currentThread() != self.thread():
            self.signals.push_pressed.emit()
            return True
        return self._handle_push_pressed()

    @Slot()
    def _handle_push_pressed(self) -> bool:
        if self.is_paused():
            return False
        self._log_info("[SMART_HOTKEY] Ctrl+Win pressed")
        if self.state in (AppState.ERROR, AppState.CANCELLED):
            self._log_info("[RECOVERY] bad state detected, forcing IDLE")
            self.force_reset_to_idle("hotkey recovery")
        if self.state != AppState.IDLE:
            self._log_info("[WARN] ignored hotkey because state=%s", self.state.value)
            return False
        self._choose_input_mode()
        self.diagnostics.mark_hotkey("Dictation hotkey detected; recording start requested")
        return self._start_recording()

    def stop_push_recording(self) -> None:
        if QThread.currentThread() != self.thread():
            self.signals.push_released.emit()
            return
        self._handle_push_released()

    @Slot()
    def _handle_push_tap(self) -> None:
        """A very short press is a tap (used for double-tap lock), not dictation: drop it quietly instead of flashing 'too short'."""
        if self.state == AppState.LISTENING and not self.toggle_recording:
            self._log_info("[SMART_HOTKEY] tap ignored")
            self.reset_pipeline("tap")

    @Slot(bool)
    def _handle_lock_changed(self, on: bool) -> None:
        self._log_info("[SMART_HOTKEY] hands-free lock=%s", on)
        if on and self.config.get("general.sound_effects", False):
            sounds.play("lock")

    @Slot()
    def _handle_push_released(self) -> None:
        self._log_info("[SMART_HOTKEY] dictation released")
        if self.state != AppState.LISTENING:
            self._log_info("[WARN] ignored hotkey because state=%s", self.state.value)
            return
        self._stop_recording()

    def toggle_recording_hotkey(self) -> None:
        if QThread.currentThread() != self.thread():
            self.signals.toggle_requested.emit()
            return
        self._handle_toggle_requested()

    @Slot()
    def _handle_toggle_requested(self) -> None:
        if self.is_paused():
            return
        if self.state == AppState.LISTENING:
            self.toggle_recording = False
            self._stop_recording()
        elif self.state == AppState.IDLE:
            self.toggle_recording = True
            self._start_recording()
        else:
            self._log_info("[WARN] ignored hotkey because state=%s", self.state.value)

    def _choose_input_mode(self) -> None:
        self.current_input_mode = "normal_dictation"
        self.selected_text_context = None
        self.selected_previous_clipboard = ""
        self.selected_had_clipboard = False
        commands = self.config.settings.get("command_processing", {})
        if not commands.get("smart_selected_rewrite_enabled", True):
            self.logger.info("[SMART_HOTKEY] mode=normal_dictation")
            return
        # Ctrl+Win is still physically held at press time. Copying here can
        # become Ctrl+Win+C on Windows, so defer selection capture until after
        # release/transcription and fall back to normal dictation if no
        # selected text is found.
        self.current_input_mode = "smart_pending"
        self.logger.info("[SMART_HOTKEY] mode=smart_pending")

    def force_reset_to_idle(self, reason: str) -> None:
        self.reset_pipeline(reason)

    def _detected_command_keys(self, instruction: str) -> list[str]:
        text = f" {instruction.lower()} "
        builtins = {
            "write_email": ["write email", "write an email", "email mode", "make email", "draft email"],
            "prompt_mode": ["prompt mode", "make this prompt", "convert into prompt", "turn this into prompt", "ai prompt"],
            "bullet_points": ["bullet points", "bullet point", "make bullet points", "convert into bullet points", "turn this into points"],
            "rewrite_humanizer": ["rewrite and humanizer", "rewrite and humanize", "humanizer", "humanize this", "rewrite this"],
            "extend": ["extend", "expand this", "make it longer", "elaborate", "extend this"],
            "professional_tone": ["professional tone", "make professional", "professionally", "formal tone"],
            "casual_tone": ["casual tone", "make casual", "casually", "friendly tone"],
            "call_caps_small": ["call caps small", "all caps small", "caps small", "lowercase", "small letters"],
        }
        detected: list[str] = []
        for command_id, phrases in builtins.items():
            if any(f" {phrase} " in text for phrase in phrases):
                detected.append(command_id)

        custom_commands = self.config.custom_commands.get("commands", []) if isinstance(self.config.custom_commands, dict) else []
        for command in custom_commands:
            if not command.get("enabled", True):
                continue
            command_id = command.get("command_id") or command.get("display_name") or "custom"
            phrases = command.get("trigger_phrases", [])
            if any(f" {str(phrase).lower()} " in text for phrase in phrases):
                detected.append(str(command_id))
        return detected

    def _start_recording(self) -> bool:
        with self._state_lock:
            if self.state != AppState.IDLE or self.recorder.is_recording:
                self._log_info("[WARN] ignored hotkey because state=%s", self.state.value)
                return False
            try:
                self.logger.info("Recording start requested")
                focused = app_profiles.foreground_app()
                self.current_app_exe = focused.exe if focused else ""
                self.current_profile = app_profiles.match_profile(self.config.settings, focused)
                if self.current_profile:
                    self.logger.info("[PROFILE] using %s", self.current_profile.get("name"))
                self.cancel_requested.clear()
                self._next_pipeline_id()
                self.recorder.start()
                self._transition(AppState.LISTENING)
                return True
            except Exception as exc:
                self.signals.error.emit(f"Microphone unavailable: {exc}")
                self._finish_and_reset(AppState.ERROR, "recording start error", 700)
                return False

    def _stop_recording(self) -> None:
        """Keep listening briefly after release so the last word is never cut off."""
        self._transition(AppState.STOPPING)
        tail = min(int(self.config.get("audio.tail_ms", 300) or 0), 300)
        QTimer.singleShot(max(0, tail), self._finish_stop_recording)

    def _finish_stop_recording(self) -> None:
        if self.state != AppState.STOPPING:
            return  # cancelled during the tail
        stop_started = time.perf_counter()
        try:
            self.logger.info("Recording stop requested")
            audio = self.recorder.stop()
        except Exception as exc:
            self.signals.error.emit(f"Could not stop recording: {exc}")
            self._finish_and_reset(AppState.ERROR, "recording stop error", 700)
            return
        if time.perf_counter() - stop_started > 5:
            self.logger.warning("[TIMEOUT] recording stop exceeded 5 seconds")
            self._finish_and_reset(AppState.ERROR, "timeout", 700)
            return
        if audio is None:
            self.signals.diagnostics_message.emit("No speech detected: recording was too short or empty.")
            self._finish_and_reset(AppState.ERROR, "empty audio", 700)
            return
        self._log_info("recording duration=%.3fs audio sample count=%s", audio.duration, audio.samples.size)
        if audio.duration < 0.4 or audio.samples.size == 0:
            self.signals.diagnostics_message.emit("No speech detected: recording was under 0.4 seconds or empty.")
            self._finish_and_reset(AppState.ERROR, "empty audio", 700)
            return
        self.signals.recording_finished.emit(audio)

    @Slot(object)
    def _process_audio(self, audio: AudioResult) -> None:
        if self.processing_future and not self.processing_future.done():
            self._log_info("[HOTKEY] Ignored processing request because state=%s", self.state.value)
            return
        pipeline_id = self.active_pipeline_id
        job_id = f"dictation-{pipeline_id}"
        self.current_job_id = job_id
        self.current_transcription_context = self._transcription_context(job_id, audio)
        self._transition(AppState.TRANSCRIBING)
        self.processing_future = self.executor.submit(self._transcribe_process_paste, pipeline_id, audio)
        self.processing_future.add_done_callback(lambda future: self.signals.processing_done.emit((pipeline_id, future)))
        timeout_ms, timeout_label = self._transcription_timeout()
        QTimer.singleShot(timeout_ms, lambda: self._check_pipeline_timeout(pipeline_id, timeout_label, timeout_ms // 1000))

    def _transcribe_process_paste(self, pipeline_id: int, audio: AudioResult) -> dict:
        try:
            if self.cancel_requested.is_set():
                return {"pipeline_id": pipeline_id, "status": "cancelled"}
            job_id = f"dictation-{pipeline_id}"
            result = self.transcriber.transcribe(audio.samples, audio.sample_rate, job_id=job_id)
            transcript = result.text.strip()
            self._log_info("transcript length=%s", len(transcript))
            if self.config.get("privacy.include_transcript_in_logs", False):
                self.logger.debug("Transcript: %s", transcript)
            if not transcript:
                return {"pipeline_id": pipeline_id, "status": "empty_transcript"}

            clean_started = time.perf_counter()
            run_settings = app_profiles.apply_profile(self.config.settings, self.current_profile)
            if self.current_input_mode == "smart_pending":
                self._resolve_smart_input_mode()
            if self.current_input_mode == "selected_rewrite" and self.selected_text_context:
                self.logger.info("[COMMAND] mode=selected_rewrite")
                self.logger.info("[SELECTED_REWRITE] instruction_length=%s", len(transcript))
                self.logger.info("[SELECTED_REWRITE] commands_detected=%s", self._detected_command_keys(transcript))
                self.logger.info("[SELECTED_REWRITE] ai_mode=%s", self.config.settings.get("command_processing", {}).get("selected_rewrite_ai_mode", "auto"))
                final_text = rewrite_selected_text(
                    self.selected_text_context,
                    transcript,
                    run_settings,
                    self.config.custom_commands,
                ).strip()
                self.logger.info("[SELECTED_REWRITE] replacement_length=%s", len(final_text))
            else:
                self.logger.info("[COMMAND] mode=normal_dictation")
                final_text = process_voice_commands(
                    transcript,
                    run_settings,
                    custom_commands=self.config.custom_commands,
                    recent_context=self.history.recent_context(self.current_app_exe),
                ).strip()
            self.logger.info("Cleanup finished seconds=%.3f final_chars=%s", time.perf_counter() - clean_started, len(final_text))
            if not final_text:
                return {"pipeline_id": pipeline_id, "status": "empty_transcript"}
            self.last_result = final_text
            if self.current_input_mode != "selected_rewrite":
                self.history.add(transcript, final_text, self.current_app_exe, persist=bool(self.config.get("privacy.keep_history", True)))
            if self.cancel_requested.is_set():
                return {"pipeline_id": pipeline_id, "status": "cancelled"}

            self._transition(AppState.PASTING)
            self.signals.paste_started.emit(pipeline_id)
            paste_started = time.perf_counter()
            self.logger.info("Paste start chars=%s", len(final_text))
            old_preserve = self.inserter.settings.get("output", {}).get("preserve_clipboard", True)
            if self.current_input_mode == "selected_rewrite":
                self.inserter.settings.setdefault("output", {})["preserve_clipboard"] = self.config.settings.get("command_processing", {}).get(
                    "preserve_clipboard_after_selected_rewrite", True
                )
            try:
                pasted = self.inserter.paste_text(final_text)
            finally:
                self.inserter.settings.setdefault("output", {})["preserve_clipboard"] = old_preserve
            if time.perf_counter() - paste_started > 5:
                self.logger.warning("[TIMEOUT] paste exceeded 5 seconds")
                return {"pipeline_id": pipeline_id, "status": "timeout", "stage": "paste"}
            self._log_info("paste success=%s", pasted)
            try:
                self.stats.record(transcript, final_text, audio.duration, self.current_app_exe, track_phrases=bool(self.config.get("privacy.keep_history", True)))
            except Exception:
                self.logger.warning("[STATS] could not record", exc_info=True)
            if self.current_input_mode == "selected_rewrite":
                self.logger.info("[SELECTED_REWRITE] paste success=%s", pasted)
            return {"pipeline_id": pipeline_id, "status": "pasted" if pasted else "copied"}
        except Exception as exc:
            self.logger.exception("Dictation pipeline failed")
            return {"pipeline_id": pipeline_id, "status": "error", "error": str(exc)}

    def _resolve_smart_input_mode(self) -> None:
        commands = self.config.settings.get("command_processing", {})
        self.logger.info("[SMART_HOTKEY] checking selected text")
        try:
            capture = capture_selected_text_safely(
                preserve_clipboard=commands.get("preserve_clipboard_after_selected_rewrite", True),
                timeout_ms=int(commands.get("selected_capture_timeout_ms", 250) or 250),
            )
        except Exception:
            self.logger.exception("[SELECTED_REWRITE ERROR] selected capture crashed; falling back to normal dictation")
            capture = None

        if not capture or not capture.selected_text.strip():
            self.current_input_mode = "normal_dictation"
            self.selected_text_context = None
            self.selected_previous_clipboard = ""
            self.selected_had_clipboard = False
            self.logger.info("[SMART_HOTKEY] mode=normal_dictation")
            return

        self.current_input_mode = "selected_rewrite"
        self.selected_text_context = capture.selected_text
        self.selected_previous_clipboard = capture.previous_clipboard
        self.selected_had_clipboard = capture.had_clipboard
        self.logger.info("[SMART_HOTKEY] mode=selected_rewrite")
        self.logger.info("[SELECTED_REWRITE] selected_text_length=%s", len(capture.selected_text))

    def _uses_isolated_safe_transcription(self) -> bool:
        transcription = self.config.settings.get("transcription", {})
        return (
            transcription.get("engine_mode", "safe_cpu") == "safe_cpu"
            and transcription.get("safe_mode_implementation", "isolated_subprocess") == "isolated_subprocess"
        )

    def _transcription_timeout(self) -> tuple[int, str]:
        transcription = self.config.settings.get("transcription", {})
        backend = transcription.get("backend", "auto_fallback")
        groq_key = self.config.settings.get("providers", {}).get("groq", {}).get("api_key", "").strip()
        if backend == "groq":
            return 50_000, "groq transcription"
        if backend == "local":
            return 120_000, "local transcription"
        if groq_key:
            return 170_000, "groq transcription with local fallback"
        return 120_000, "local transcription"

    def _transcription_context(self, job_id: str, audio: AudioResult) -> dict:
        samples = audio.samples
        rms = float((samples.astype("float32") ** 2).mean() ** 0.5) if samples.size else 0.0
        transcription = self.config.settings.get("transcription", {})
        backend = transcription.get("backend", "auto_fallback")
        return {
            "backend": backend,
            "groq_model": transcription.get("groq_model", "whisper-large-v3-turbo"),
            "engine_mode": transcription.get("engine_mode", "safe_cpu"),
            "safe_mode_implementation": transcription.get("safe_mode_implementation", "isolated_subprocess"),
            "model": transcription.get("model", "base"),
            "device": "cpu" if transcription.get("engine_mode", "safe_cpu") == "safe_cpu" else transcription.get("device_preference", "auto"),
            "compute_type": "int8" if transcription.get("engine_mode", "safe_cpu") == "safe_cpu" else transcription.get("compute_type_cpu", "int8"),
            "language": transcription.get("language_mode", "english"),
            "task": "transcribe",
            "audio_duration": round(audio.duration, 3),
            "sample_count": int(samples.size),
            "rms": round(rms, 6),
            "job_id": job_id,
        }

    def _processing_done(self, payload: object) -> None:
        pipeline_id, future = payload
        if pipeline_id != self.active_pipeline_id:
            self._log_info("[WORKER] Ignored stale worker completion pipeline_id=%s active=%s", pipeline_id, self.active_pipeline_id)
            return
        try:
            result = future.result()
            self.processing_future = None
            status = result.get("status")
            if status in ("pasted", "copied"):
                self.logger.info("Paste %s", "succeeded" if status == "pasted" else "failed; copied fallback")
                self._finish_and_reset(AppState.SUCCESS, "success", 700)
            elif status == "empty_transcript":
                self.signals.diagnostics_message.emit("No speech detected: transcript was empty.")
                self._finish_and_reset(AppState.ERROR, "empty transcript", 700)
            elif status == "cancelled":
                self._finish_and_reset(AppState.CANCELLED, "cancel", 500)
            elif status == "timeout":
                self._finish_and_reset(AppState.ERROR, "timeout", 700)
            else:
                self.signals.error.emit(result.get("error", "Unknown pipeline error"))
                self._finish_and_reset(AppState.ERROR, "error", 700)
        except Exception as exc:
            self.processing_future = None
            self.signals.error.emit(str(exc))
            self._finish_and_reset(AppState.ERROR, "error", 700)

    @Slot()
    def cancel(self) -> None:
        if QThread.currentThread() != self.thread():
            self.signals.cancel_hotkey_requested.emit()
            return
        self._handle_cancel_requested()

    @Slot()
    def _handle_cancel_requested(self) -> None:
        self._log_info("[HOTKEY] Esc pressed")
        self.cancel_requested.set()
        self.recorder.cancel()
        if self.processing_future and not self.processing_future.done():
            self.processing_future.cancel()
        self.processing_future = None
        self.force_reset_to_idle("esc pressed")

    def _check_pipeline_timeout(self, pipeline_id: int, stage: str, seconds: int) -> None:
        if pipeline_id != self.active_pipeline_id:
            self.logger.info("[TIMEOUT] stale timeout ignored pipeline_id=%s active=%s stage=%s", pipeline_id, self.active_pipeline_id, stage)
            return
        if self.state in (AppState.TRANSCRIBING, AppState.PASTING) and self.processing_future and not self.processing_future.done():
            self.logger.error("[TIMEOUT] app timer fired stage=%s seconds=%s context=%s", stage, seconds, self.current_transcription_context)
            self.cancel_requested.set()
            self._finish_and_reset(AppState.ERROR, "timeout", 700)

    @Slot()
    def open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.config, self.recorder, self.transcriber, self.diagnostics, self.logger, self.bar)
            self.settings_window.settings_changed.connect(self.reload_settings)
            self.settings_window.pill_style_changed.connect(self.bar.apply_style)
            self.settings_window.appearance_changed.connect(self.theme.apply)
            self.settings_window.paste_test_requested.connect(self.run_paste_test)
            self.settings_window.transcription_test_requested.connect(self.run_transcription_test)
            self.settings_window.groq_test_requested.connect(self.run_groq_test)
            self.settings_window.hotkey_test_requested.connect(self.run_hotkey_test)
            self.settings_window.force_reset_requested.connect(lambda: self.reset_pipeline("manual diagnostics reset"))
            self.settings_window.welcome_requested.connect(self.open_onboarding)
            self.settings_window.set_updater(self.updater)
            self.settings_window.set_history(self.history)
            self.settings_window.set_stats(self.stats)
        self.settings_window.load_values()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    @Slot()
    def open_settings_audio(self) -> None:
        self.open_settings()
        if self.settings_window:
            self.settings_window.tabs.go(self.settings_window.tabs.index_of("Audio"))

    @Slot()
    def reload_settings(self) -> None:
        self.logger = setup_logging(self.config.get("privacy.logs_level", "warning"))
        self.recorder.settings = self.config.settings
        self.transcriber.settings = self.config.settings
        self.inserter.settings = self.config.settings
        self.hotkeys.reload(self.config.settings)
        self.mode_override = self.config.get("output.default_mode", "clean_casual")
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        self.bar.setWindowFlags(flags)
        signature = (self.config.get("audio.keep_ready", True), self.config.get("audio.microphone"))
        if signature != self._mic_signature:
            self._mic_signature = signature
            self.recorder.disarm()
            self._start_background_warmup()
        self.bar.settings = self.config.settings
        self.theme.apply(self.config.get("general.appearance", "system"))
        self.bar.apply_style()
        self.bar.present()

    def _hotkey_error(self, message: str) -> None:
        self.diagnostics.set_error(message)
        self.signals.error.emit(message)

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self.diagnostics.set_error(message)
        self.logger.warning(message)
        self.bar.set_status("Error")
        if self.settings_window:
            self.settings_window.append_diagnostics(f"Error: {message}")

    @Slot(str)
    def _append_diagnostics(self, message: str) -> None:
        if self.settings_window:
            self.settings_window.append_diagnostics(message)

    @Slot()
    def run_hotkey_test(self) -> None:
        self.diagnostics.mark_hotkey("Waiting. Press and release F8 now.")
        self.signals.diagnostics_message.emit("Hotkey test armed. Press and release F8.")

    @Slot()
    def run_paste_test(self) -> None:
        self.diagnostics.mark_paste("Paste test starts in 3 seconds")
        self.signals.diagnostics_message.emit("Paste test: click your target text box within 3 seconds.")
        QTimer.singleShot(3000, self._do_paste_test)

    def _do_paste_test(self) -> None:
        try:
            ok = self.inserter.paste_text("Waky paste test")
            message = "Paste test succeeded" if ok else "Paste test copied text to clipboard; auto-paste may have failed"
            self.diagnostics.mark_paste(message)
            self.logger.info(message)
            self.signals.status.emit("Pasted" if ok else "Copied")
            self.signals.diagnostics_message.emit(message)
        except Exception as exc:
            self.logger.exception("Paste test failed")
            self.diagnostics.mark_paste(f"Paste test failed: {exc}")
            self.signals.error.emit(f"Paste test failed: {exc}")

    @Slot()
    def run_transcription_test(self) -> None:
        if self.processing_future:
            self.signals.diagnostics_message.emit("Transcription test skipped: app is already processing.")
            return
        self.signals.status.emit("Listening")
        self.diagnostics.mark_transcription("Recording 3 seconds...")
        self.signals.diagnostics_message.emit("Transcription test: recording 3 seconds. Speak now.")
        self.processing_future = self.executor.submit(self._transcription_test_worker)
        self.processing_future.add_done_callback(lambda future: self.signals.transcription_test_done.emit(future))

    @Slot()
    def run_groq_test(self) -> None:
        if self.processing_future:
            self.signals.diagnostics_message.emit("Groq test skipped: app is already processing.")
            return
        self.signals.status.emit("Listening")
        self.diagnostics.mark_transcription("Groq test recording 3 seconds...")
        self.signals.diagnostics_message.emit("Groq API test: recording 3 seconds. Speak now.")
        self.processing_future = self.executor.submit(self._groq_test_worker)
        self.processing_future.add_done_callback(lambda future: self.signals.groq_test_done.emit(future))

    def _groq_test_worker(self) -> str:
        audio = self.recorder.record_fixed(3.0)
        self.signals.status.emit("Processing")
        key = self.transcriber._groq_api_key()
        if not key:
            raise RuntimeError("Groq API key missing")
        result = self.transcriber._transcribe_groq(audio.samples, audio.sample_rate, "groq-diagnostics-test", key)
        return f"Groq API OK: model={result.model}; transcript={result.text or '[empty transcript]'}"

    def _transcription_test_worker(self) -> str:
        audio = self.recorder.record_fixed(3.0)
        self.signals.status.emit("Processing")
        result = self.transcriber.transcribe(audio.samples, audio.sample_rate, job_id="diagnostics-test")
        return result.text

    def _transcription_test_done(self, future: Future) -> None:
        self.processing_future = None
        try:
            text = future.result()
            message = f"Transcription test result: {text or '[empty transcript]'}"
            self.diagnostics.mark_transcription(message)
            self.signals.status.emit("Idle")
            self.signals.diagnostics_message.emit(message)
        except Exception as exc:
            self.logger.exception("Transcription test failed")
            self.diagnostics.mark_transcription(f"Failed: {exc}")
            self.signals.error.emit(f"Transcription test failed: {exc}")

    def _groq_test_done(self, future: Future) -> None:
        self.processing_future = None
        try:
            message = future.result()
            self.diagnostics.mark_transcription(message)
            self.signals.status.emit("Idle")
            self.signals.diagnostics_message.emit(message)
        except Exception as exc:
            self.logger.exception("Groq API test failed")
            message = f"Groq API test failed: {exc}"
            self.diagnostics.mark_transcription(message)
            self.signals.error.emit(message)

    @Slot()
    def restart(self) -> None:
        launcher = PROJECT_ROOT / "start_waky_hidden.vbs"
        try:
            if FROZEN:
                subprocess.Popen([sys.executable], cwd=str(PROJECT_ROOT), close_fds=True)
            elif sys.platform == "win32" and launcher.exists():
                subprocess.Popen(["wscript.exe", str(launcher)], cwd=str(PROJECT_ROOT), close_fds=True)
            else:
                subprocess.Popen([sys.executable, str(PROJECT_ROOT / "main.py")], cwd=str(PROJECT_ROOT), close_fds=True)
        finally:
            self.quit()

    @Slot()
    def quit(self) -> None:
        self.cleanup()
        self.qt_app.quit()

    @Slot()
    def cleanup(self) -> None:
        if self.cleaned_up:
            return
        self.cleaned_up = True
        self.hotkeys.stop()
        self.recorder.cancel()
        self.recorder.disarm()
        self.executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.bar.animation.stop()
            self.bar.keep_on_top_timer.stop()
            self.bar.hide()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        self._delete_pid_file()


_MUTEX_HANDLE = None


def _already_running() -> bool:
    """Only one Waky at a time (autostart plus a manual launch used to create two pills)."""
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, "Waky.Dictation.Mutex")
        return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


SHOW_SERVER_NAME = "Waky.Dictation.Show"


def _ask_running_instance_to_show() -> bool:
    """Tell the Waky that is already running to open its Settings window. Returns True when it answered."""
    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtNetwork import QLocalSocket

        _core = QCoreApplication.instance() or QCoreApplication(sys.argv)  # noqa: F841
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: let the running Waky come to the front
        socket = QLocalSocket()
        socket.connectToServer(SHOW_SERVER_NAME)
        if not socket.waitForConnected(1500):
            return False
        socket.write(b"show")
        socket.waitForBytesWritten(1500)
        socket.disconnectFromServer()
        return True
    except Exception:
        return False


def _start_show_server(controller: "WakyApp") -> None:
    """Listen for a second launch (double-click, Start menu) and open Settings instead of starting another Waky."""
    from PySide6.QtNetwork import QLocalServer

    server = QLocalServer(controller)
    QLocalServer.removeServer(SHOW_SERVER_NAME)
    if not server.listen(SHOW_SERVER_NAME):
        return

    def on_connection() -> None:
        while server.hasPendingConnections():
            conn = server.nextPendingConnection()
            conn.readyRead.connect(conn.deleteLater)
            conn.disconnected.connect(conn.deleteLater)
        QTimer.singleShot(0, controller.open_settings)

    server.newConnection.connect(on_connection)
    controller._show_server = server


def _message_box(title: str, text: str) -> None:
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)
    except Exception:
        pass


def _install_crash_handlers() -> None:
    """Never die silently: log every uncaught error, and tell the user once if the UI thread hit one."""
    import logging
    import traceback

    log = logging.getLogger("waky")
    shown = {"done": False}

    def hook(exc_type, exc, tb) -> None:
        log.error("Uncaught exception: %s", "".join(traceback.format_exception(exc_type, exc, tb)))
        if not shown["done"] and threading.current_thread() is threading.main_thread():
            shown["done"] = True
            _message_box("Waky", "Waky hit an unexpected problem but is still running.\n\nDetails were saved to:\n" + str(LOG_DIR / "error.log"))

    sys.excepthook = hook
    threading.excepthook = lambda args: log.error("Thread %s failed", args.thread.name if args.thread else "?", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def main() -> int:
    if _already_running():
        if _ask_running_instance_to_show():
            return 0
        _message_box("Waky", "Waky is already running. Look for its icon in the system tray (bottom right of the taskbar).")
        return 0
    _install_crash_handlers()
    if sys.platform == "win32":
        try:  # own taskbar identity, so Windows uses Waky's icon instead of a cached one
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Waky.Dictation")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from app.utils import asset_path

    icon_file = asset_path("waky.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    controller = WakyApp(app)
    app.aboutToQuit.connect(controller.cleanup)
    _start_show_server(controller)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
