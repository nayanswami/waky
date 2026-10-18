from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass

import pyperclip

from .local_memory import memory_summary
from .utils import CONFIG_DIR, LOG_DIR, PROJECT_ROOT


MIC_HELP_TEXT = (
    "Enable microphone access:\n"
    "Windows Settings → Privacy & security → Microphone → turn ON:\n"
    "1. Microphone access\n"
    "2. Let apps access your microphone\n"
    "3. Let desktop apps access your microphone"
)


@dataclass
class DiagnosticsState:
    hotkey_status: str = "Not tested"
    microphone_status: str = "Not tested"
    paste_status: str = "Not tested"
    transcription_status: str = "Not tested"
    last_error: str = ""


class DiagnosticsService:
    def __init__(self, config_manager, recorder, transcriber, logger) -> None:
        self.config_manager = config_manager
        self.recorder = recorder
        self.transcriber = transcriber
        self.logger = logger
        self.state = DiagnosticsState()

    def summary(self) -> str:
        settings = self.config_manager.settings
        try:
            mic_count = len(self.recorder.list_microphones())
        except Exception as exc:
            mic_count = f"error: {exc}"
        faster_whisper = importlib.util.find_spec("faster_whisper") is not None
        cuda_available = self.transcriber.cuda_available()
        memory = memory_summary(settings)
        lines = [
            "Waky diagnostics",
            f"Python: {sys.version.split()[0]} ({sys.executable})",
            f"OS: {platform.platform()}",
            f"App path: {PROJECT_ROOT}",
            f"Config path: {CONFIG_DIR}",
            f"Logs path: {LOG_DIR}",
            f"Push-to-talk hotkey: {settings.get('hotkeys', {}).get('push_to_talk')}",
            f"Toggle hotkey: {settings.get('hotkeys', {}).get('toggle_recording')}",
            f"Transcription backend: {settings.get('transcription', {}).get('backend')}",
            f"Groq model: {settings.get('transcription', {}).get('groq_model')}",
            f"Transcription engine mode: {settings.get('transcription', {}).get('engine_mode')}",
            f"Safe mode implementation: {settings.get('transcription', {}).get('safe_mode_implementation')}",
            f"Selected model: {settings.get('transcription', {}).get('model')}",
            f"Device selected: {settings.get('transcription', {}).get('device_preference')}",
            f"CUDA available: {'yes' if cuda_available else 'no'}",
            f"faster-whisper installed: {'yes' if faster_whisper else 'no'}",
            f"Microphone devices: {mic_count}",
            f"Default input: {self.recorder.default_input_device()}",
            f"Model load status: {self.transcriber.model_load_status}",
            f"Model device: {self.transcriber.device_display()}",
            f"Last model error: {self.transcriber.last_error or 'none'}",
            f"Hotkey test: {self.state.hotkey_status}",
            f"Microphone test: {self.state.microphone_status}",
            f"Paste test: {self.state.paste_status}",
            f"Transcription test: {self.state.transcription_status}",
            f"Local memory enabled: {memory['memory_enabled']}",
            f"Memory active project: {memory['active_project']}",
            f"Memory custom vocabulary: {memory['custom_vocabulary_count']}",
            f"Memory corrections: {memory['corrections_count']}",
            f"Memory preferences: {memory['preferences_count']}",
            f"Memory forbidden phrases: {memory['forbidden_phrases_count']}",
            f"Memory project summary exists: {memory['project_summary_exists']}",
            f"Last app error: {self.state.last_error or 'none'}",
            "",
            MIC_HELP_TEXT,
        ]
        return "\n".join(lines)

    def copy_summary(self) -> None:
        pyperclip.copy(self.summary())

    def set_error(self, message: str) -> None:
        self.state.last_error = message

    def mark_hotkey(self, message: str) -> None:
        self.state.hotkey_status = message

    def mark_microphone(self, message: str) -> None:
        self.state.microphone_status = message

    def mark_paste(self, message: str) -> None:
        self.state.paste_status = message

    def mark_transcription(self, message: str) -> None:
        self.state.transcription_status = message
