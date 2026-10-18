from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class AudioResult:
    samples: np.ndarray
    sample_rate: int
    duration: float


@dataclass
class MicrophoneTestResult:
    ok: bool
    message: str
    level: float
    sample_rate: int | None


class AudioRecorder:
    def __init__(self, settings: dict, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.stream: sd.InputStream | None = None
        self.frames: list[np.ndarray] = []
        self.started_at = 0.0
        self.is_recording = False
        self.current_sample_rate = int(settings.get("audio", {}).get("sample_rate", 16000))
        self.current_device = settings.get("audio", {}).get("microphone")
        self._lock = threading.Lock()

    def list_microphones(self) -> list[dict]:
        devices = sd.query_devices()
        result = []
        for index, device in enumerate(devices):
            if device.get("max_input_channels", 0) > 0:
                result.append(
                    {
                        "index": index,
                        "name": device.get("name", f"Input {index}"),
                        "default_samplerate": int(device.get("default_samplerate", 0) or 0),
                        "channels": int(device.get("max_input_channels", 0) or 0),
                    }
                )
        self.logger.info("Microphone devices listed count=%s", len(result))
        return result

    def default_input_device(self) -> dict | None:
        try:
            default_index = sd.default.device[0]
            if default_index is None or default_index < 0:
                return None
            device = sd.query_devices(default_index)
            return {"index": default_index, "name": device.get("name", "Default input"), "default_samplerate": int(device.get("default_samplerate", 0) or 0)}
        except Exception:
            self.logger.warning("Could not query default input device", exc_info=True)
            return None

    def start(self) -> None:
        with self._lock:
            if self.is_recording:
                return
            audio_settings = self.settings.get("audio", {})
            self.frames = []
            self.started_at = time.perf_counter()
            try:
                self.stream, sample_rate, device = self._open_input_stream(self._callback)
                self.stream.start()
                self.is_recording = True
                self.current_sample_rate = sample_rate
                self.current_device = device
                audio_settings["sample_rate"] = sample_rate
                audio_settings["channels"] = 1
                audio_settings["microphone"] = device
                self.logger.info("Recording started sample_rate=%s device=%s", sample_rate, device)
            except Exception:
                self.stream = None
                self.logger.exception("Microphone unavailable")
                raise

    def _device_exists_and_input(self, device: int | None) -> bool:
        if device is None:
            return True
        try:
            info = sd.query_devices(int(device))
            return int(info.get("max_input_channels", 0) or 0) > 0
        except Exception:
            self.logger.warning("Configured microphone index is invalid: %s", device, exc_info=True)
            return False

    def _candidate_devices(self) -> list[int | None]:
        audio_settings = self.settings.get("audio", {})
        configured = audio_settings.get("microphone")
        candidates: list[int | None] = []
        if self._device_exists_and_input(configured):
            candidates.append(configured)
        else:
            self.logger.warning("Configured microphone %s is unavailable; falling back to available inputs", configured)
        if None not in candidates:
            candidates.append(None)
        default = self.default_input_device()
        if default and default.get("index") not in candidates:
            candidates.append(default.get("index"))
        try:
            devices = sd.query_devices()
            scored: list[tuple[int, int]] = []
            for index, device in enumerate(devices):
                if int(device.get("max_input_channels", 0) or 0) <= 0:
                    continue
                name = str(device.get("name", "")).lower()
                hostapi = int(device.get("hostapi", -1))
                score = 0
                if "microphone array" in name:
                    score += 30
                if "realtek" in name:
                    score += 20
                if hostapi == 2:  # WASAPI is usually the most stable Windows shared-mode input.
                    score += 12
                if "mapper" in name or "primary" in name:
                    score += 3
                scored.append((score, index))
            for _, index in sorted(scored, reverse=True):
                if index not in candidates:
                    candidates.append(index)
        except Exception:
            self.logger.warning("Could not build microphone fallback list", exc_info=True)
        return candidates

    def _candidate_rates(self, device: int | None) -> list[int]:
        audio_settings = self.settings.get("audio", {})
        rates: list[int] = []
        configured = int(audio_settings.get("sample_rate", 16000) or 16000)
        for rate in (configured, 48000, 44100, 16000):
            if rate and rate not in rates:
                rates.append(rate)
        if device is not None:
            try:
                info = sd.query_devices(int(device))
                default_rate = int(info.get("default_samplerate", 0) or 0)
                if default_rate and default_rate not in rates:
                    rates.insert(0, default_rate)
            except Exception:
                pass
        return rates

    def _open_input_stream(self, callback):
        last_error: Exception | None = None
        for device in self._candidate_devices():
            for sample_rate in self._candidate_rates(device):
                try:
                    self.logger.info("Trying microphone device=%s sample_rate=%s channels=1", device, sample_rate)
                    stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=1,
                        dtype="float32",
                        device=device,
                        callback=callback,
                    )
                    self.logger.info("Microphone selected device=%s sample_rate=%s channels=1", device, sample_rate)
                    return stream, sample_rate, device
                except Exception as exc:
                    last_error = exc
                    self.logger.warning("Microphone open failed device=%s sample_rate=%s: %s", device, sample_rate, exc)
        raise RuntimeError(f"No working microphone input found. Last error: {last_error}")

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            self.logger.warning("Audio input status: %s", status)
        self.frames.append(indata.copy())

    def stop(self) -> AudioResult | None:
        with self._lock:
            if not self.is_recording:
                return None
            stream = self.stream
            self.stream = None
            self.is_recording = False
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                self.logger.warning("Failed closing audio stream", exc_info=True)

        duration = time.perf_counter() - self.started_at
        min_duration = float(self.settings.get("audio", {}).get("min_record_seconds", 0.25))
        if duration < min_duration or not self.frames:
            self.frames = []
            self.logger.info("Recording ignored duration=%.3fs frames=%s", duration, len(self.frames))
            return None

        samples = np.concatenate(self.frames, axis=0).reshape(-1).astype(np.float32)
        self.frames = []
        if self.settings.get("audio", {}).get("silence_trimming", True):
            samples = self.trim_silence(samples)
        sample_rate = int(self.current_sample_rate or self.settings.get("audio", {}).get("sample_rate", 16000))
        self.logger.info("Recording stopped duration=%.3fs samples=%s", duration, samples.size)
        return AudioResult(samples=samples, sample_rate=sample_rate, duration=duration)

    def cancel(self) -> None:
        with self._lock:
            stream = self.stream
            self.stream = None
            self.is_recording = False
            self.frames = []
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                self.logger.warning("Failed cancelling audio stream", exc_info=True)

    def trim_silence(self, samples: np.ndarray, threshold: float = 0.012, padding_ms: int = 120) -> np.ndarray:
        if samples.size == 0:
            return samples
        mask = np.abs(samples) > threshold
        if not mask.any():
            return samples
        start = int(np.argmax(mask))
        end = int(len(mask) - np.argmax(mask[::-1]))
        pad = int(self.settings.get("audio", {}).get("sample_rate", 16000) * padding_ms / 1000)
        start = max(0, start - pad)
        end = min(len(samples), end + pad)
        return samples[start:end]

    def test_microphone_level(self, seconds: float = 1.0) -> float:
        return self.record_test(seconds).level

    def record_test(self, seconds: float = 3.0) -> MicrophoneTestResult:
        last_error: Exception | None = None
        for device in self._candidate_devices():
            for sample_rate in self._candidate_rates(device):
                try:
                    self.logger.info("Microphone test start seconds=%.1f sample_rate=%s device=%s", seconds, sample_rate, device)
                    data = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32", device=device)
                    sd.wait()
                    level = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
                    ok = level > 0.01
                    message = "Mic OK" if ok else "No sound detected"
                    self.current_sample_rate = sample_rate
                    self.current_device = device
                    self.settings.setdefault("audio", {})["sample_rate"] = sample_rate
                    self.settings.setdefault("audio", {})["channels"] = 1
                    self.settings.setdefault("audio", {})["microphone"] = device
                    self.logger.info("Microphone test finished level=%.4f sample_rate=%s device=%s message=%s", level, sample_rate, device, message)
                    return MicrophoneTestResult(ok=ok, message=message, level=level, sample_rate=sample_rate)
                except Exception as exc:
                    last_error = exc
                    self.logger.warning("Microphone test failed device=%s sample_rate=%s: %s", device, sample_rate, exc)
        help_text = (
            "Microphone failed. Enable microphone access: Windows Settings > Privacy & security > Microphone > "
            "turn on Microphone access and Let desktop apps access your microphone."
        )
        return MicrophoneTestResult(ok=False, message=f"{help_text} Last error: {last_error}", level=0.0, sample_rate=None)

    def record_fixed(self, seconds: float = 3.0) -> AudioResult:
        stream, sample_rate, device = self._open_input_stream(None)
        stream.close()
        data = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32", device=device)
        sd.wait()
        samples = data.reshape(-1).astype(np.float32)
        self.current_sample_rate = sample_rate
        self.current_device = device
        audio_settings = self.settings.setdefault("audio", {})
        audio_settings["sample_rate"] = sample_rate
        audio_settings["channels"] = 1
        audio_settings["microphone"] = device
        if audio_settings.get("silence_trimming", True):
            samples = self.trim_silence(samples)
        return AudioResult(samples=samples, sample_rate=sample_rate, duration=seconds)
