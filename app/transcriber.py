from __future__ import annotations

import logging
import http.client
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from scipy.io import wavfile

from . import http_pool, llm_engine, model_manager, speech_hints
from .utils import DATA_DIR, FROZEN, PROJECT_ROOT


class GroqRateLimited(RuntimeError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Groq rate limit reached; retry in {retry_after:.0f}s")
        self.retry_after = retry_after


@dataclass
class TranscriptionResult:
    text: str
    language: str | None
    device: str
    model: str


class FasterWhisperTranscriber:
    GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, settings: dict, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.model = None
        self.loaded_signature: tuple[str, str, str] | None = None
        self.device_used = "unknown"
        self.compute_type_used = "unknown"
        self.model_load_status = "Not loaded"
        self.last_error = ""
        self.transcriber_lock = threading.Lock()
        self.on_notice = None  # optional callable(str) used to tell the user about fallbacks

    def _notice(self, message: str) -> None:
        self.logger.warning("[TRANSCRIBE] %s", message)
        if callable(self.on_notice):
            try:
                self.on_notice(message)
            except Exception:
                pass

    def prewarm(self) -> None:
        """Load the local model in the background so the first fallback or offline dictation is not slow."""
        try:
            transcription = self.settings.get("transcription", {})
            if transcription.get("backend", "auto_fallback") == "groq" or not self.faster_whisper_installed():
                return
            if transcription.get("engine_mode") == "safe_cpu" or not model_manager.is_downloaded(transcription.get("model", "base")):
                return
            with self.transcriber_lock:
                self._load_model()
        except Exception:
            self.logger.warning("Local model prewarm failed", exc_info=True)

    def faster_whisper_installed(self) -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def cuda_available(self) -> bool:
        try:
            import ctranslate2

            return bool(ctranslate2.get_cuda_device_count())
        except Exception:
            return False

    def _load_model(self) -> None:
        from faster_whisper import WhisperModel

        model_name = self.settings.get("transcription", {}).get("model", "base")
        transcription = self.settings.get("transcription", {})
        engine_mode = transcription.get("engine_mode", "safe_cpu")
        preferred = transcription.get("device_preference", "cpu" if engine_mode == "safe_cpu" else "auto")
        if engine_mode == "safe_cpu":
            preferred = "cpu"
        elif engine_mode == "fast_cuda":
            preferred = "cuda"
        attempts: list[tuple[str, str]] = []
        if preferred in ("auto", "cuda"):
            attempts.append(("cuda", self.settings.get("transcription", {}).get("compute_type_gpu", "float16")))
            attempts.append(("cuda", "int8_float16"))
        if preferred in ("auto", "cpu"):
            attempts.append(("cpu", self.settings.get("transcription", {}).get("compute_type_cpu", "int8")))

        last_error: Exception | None = None
        for device, compute_type in attempts:
            signature = (model_name, device, compute_type)
            if self.model is not None and self.loaded_signature == signature:
                return
            try:
                self.model_load_status = f"Loading {model_name} on {device} ({compute_type})"
                self.logger.info("Model load start model=%s device=%s compute_type=%s", model_name, device, compute_type)
                self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
                self.loaded_signature = signature
                self.device_used = device.upper()
                self.compute_type_used = compute_type
                self.model_load_status = f"Loaded {model_name} on {self.device_used} ({compute_type})"
                self.last_error = ""
                self.logger.info("Model load success %s", self.model_load_status)
                return
            except Exception as exc:
                last_error = exc
                self.last_error = str(exc)
                self.logger.warning("Could not load Whisper model on %s/%s: %s", device, compute_type, exc)
        self.model_load_status = "Load failed"
        raise RuntimeError(f"Could not load faster-whisper model. Last error: {last_error}")

    def transcribe(self, audio: np.ndarray, sample_rate: int, job_id: str | int | None = None) -> TranscriptionResult:
        job_id = str(job_id or "manual")
        transcription = self.settings.get("transcription", {})
        backend = transcription.get("backend", "auto_fallback")
        groq_key = self._groq_api_key()
        if backend == "groq":
            if not groq_key:
                raise RuntimeError("Groq API key missing")
            return self._transcribe_groq(audio, sample_rate, job_id, groq_key)
        if backend == "auto_fallback" and groq_key:
            status = llm_engine.STT_STATUS
            if status.rate_limited:
                self._notice(f"Groq limit reached; using local Whisper for {status.cooldown_until - time.time():.0f}s more.")
            else:
                try:
                    return self._transcribe_groq(audio, sample_rate, job_id, groq_key)
                except GroqRateLimited as exc:
                    self._notice(f"Groq limit reached; switching to local Whisper (retry in {exc.retry_after:.0f}s).")
                except Exception:
                    self.logger.error("[TRANSCRIBE ERROR] Groq failed; retrying local fallback. traceback=%s", traceback.format_exc())
            self._require_local_model()
        return self._transcribe_local(audio, sample_rate, job_id)

    def _require_local_model(self) -> None:
        """Avoid a silent multi-minute download when falling back: fail fast with a clear message."""
        model = self.settings.get("transcription", {}).get("model", "base")
        if self.faster_whisper_installed() and not model_manager.is_downloaded(model):
            raise RuntimeError(
                f"Groq is unavailable and the local '{model}' model is not downloaded "
                f"({model_manager.size_label(model)}). Open Settings > Transcription > Download local model."
            )

    def _transcribe_local(self, audio: np.ndarray, sample_rate: int, job_id: str) -> TranscriptionResult:
        transcription = self.settings.get("transcription", {})
        engine_mode = transcription.get("engine_mode", "safe_cpu")
        safe_mode = transcription.get("safe_mode_implementation", "isolated_subprocess")
        model_name = transcription.get("model", "base")
        compute_type = "int8" if engine_mode == "safe_cpu" else transcription.get("compute_type_cpu", "int8")
        device = "cpu" if engine_mode == "safe_cpu" else transcription.get("device_preference", "auto")
        language_mode = transcription.get("language_mode", "english" if engine_mode == "safe_cpu" else "auto")
        language = None
        task = "transcribe"
        if language_mode == "english":
            language = "en"
        elif language_mode == "hindi":
            language = "hi"
        elif language_mode in ("hinglish", "hindi_hinglish_to_english"):
            language = None
        rms = self._rms(audio)
        context = {
            "backend": "local-faster-whisper",
            "engine_mode": engine_mode,
            "safe_mode": safe_mode,
            "model": model_name,
            "device": device,
            "compute_type": compute_type,
            "language": language or "auto",
            "task": task,
            "audio_duration": round(float(audio.size / sample_rate), 3) if sample_rate else 0,
            "sample_count": int(audio.size),
            "rms": round(rms, 6),
            "job_id": job_id,
        }
        if not self.transcriber_lock.acquire(timeout=2):
            self.last_error = "transcriber busy"
            self.logger.error("Transcription lock timeout context=%s", context)
            raise TimeoutError("transcriber busy")
        try:
            self.logger.info("[TRANSCRIBE] backend=local-faster-whisper")
            self.logger.info("[TRANSCRIBE] local model=%s", model_name)
            self.logger.info("[TRANSCRIBE] device=%s", device)
            self.logger.info("[TRANSCRIBE] compute_type=%s", compute_type)
            self.logger.info("[TRANSCRIBE] language=%s", language or "auto")
            self.logger.info("[TRANSCRIBE] audio_duration=%s", context["audio_duration"])
            self.logger.info("[TRANSCRIBE] request started")
            self.logger.info("Transcription job start context=%s", context)
            if engine_mode == "safe_cpu" and safe_mode == "isolated_subprocess":
                result = self._transcribe_subprocess(audio, sample_rate, language, task, job_id, context)
                self.logger.info("[TRANSCRIBE] request finished")
                self.logger.info("[TRANSCRIBE] transcript length=%s", len(result.text))
                return result
            if engine_mode == "safe_cpu":
                result = self._transcribe_fresh_cpu(audio, sample_rate, language, task, job_id, context)
                self.logger.info("[TRANSCRIBE] request finished")
                self.logger.info("[TRANSCRIBE] transcript length=%s", len(result.text))
                return result
            self._load_model()
            try:
                result = self._run_transcribe(audio, sample_rate, language, task, job_id)
                self.logger.info("[TRANSCRIBE] request finished")
                self.logger.info("[TRANSCRIBE] transcript length=%s", len(result.text))
                return result
            except Exception as exc:
                self.last_error = str(exc)
                if self.device_used == "CUDA" and engine_mode == "auto":
                    self.logger.warning("CUDA inference failed; retrying on CPU. context=%s error=%s", context, exc, exc_info=True)
                    self.model = None
                    self.loaded_signature = None
                    original_preference = self.settings.setdefault("transcription", {}).get("device_preference", "auto")
                    self.settings["transcription"]["device_preference"] = "cpu"
                    try:
                        self._load_model()
                        result = self._run_transcribe(audio, sample_rate, language, task, job_id)
                        self.logger.info("[TRANSCRIBE] request finished")
                        self.logger.info("[TRANSCRIBE] transcript length=%s", len(result.text))
                        return result
                    finally:
                        self.settings["transcription"]["device_preference"] = original_preference
                raise
        except Exception:
            self.last_error = traceback.format_exc()
            self.logger.error("[TRANSCRIBE ERROR] context=%s traceback=%s", context, self.last_error)
            raise
        finally:
            self.transcriber_lock.release()

    def _transcribe_groq(self, audio: np.ndarray, sample_rate: int, job_id: str, api_key: str) -> TranscriptionResult:
        transcription = self.settings.get("transcription", {})
        model = transcription.get("groq_model", "whisper-large-v3-turbo")
        language_mode = transcription.get("language_mode", "english")
        language = {"english": "en", "hindi": "hi"}.get(language_mode)
        prompt = speech_hints.stt_prompt(self.settings)
        temp_path: Path | None = None
        context = {
            "backend": "groq",
            "model": model,
            "language": language or "auto",
            "task": "transcribe",
            "audio_duration": round(float(audio.size / sample_rate), 3) if sample_rate else 0,
            "sample_count": int(audio.size),
            "rms": round(self._rms(audio), 6),
            "job_id": job_id,
        }
        try:
            with tempfile.NamedTemporaryFile(prefix=f"waky_groq_{job_id}_", suffix=".wav", delete=False) as handle:
                temp_path = Path(handle.name)
            wavfile.write(temp_path, sample_rate, self._to_int16(audio))
            self.logger.info("[TRANSCRIBE] backend=groq")
            self.logger.info("[TRANSCRIBE] model=%s", model)
            self.logger.info("[TRANSCRIBE] language=%s", language or "auto")
            self.logger.info("[TRANSCRIBE] audio_duration=%s", context["audio_duration"])
            self.logger.info("[TRANSCRIBE] request started")
            payload = self._post_groq_wav(temp_path, api_key, model, language, job_id, prompt)
            text = str(payload.get("text", "")).strip()
            self.device_used = "Groq API"
            self.compute_type_used = "remote"
            self.model_load_status = f"Groq {model}"
            self.last_error = ""
            self.logger.info("[TRANSCRIBE] request finished")
            self.logger.info("[TRANSCRIBE] transcript length=%s", len(text))
            return TranscriptionResult(text=text, language=language, device="Groq API", model=model)
        except Exception:
            self.last_error = traceback.format_exc()
            self.logger.error("[TRANSCRIBE ERROR] context=%s traceback=%s", context, self.last_error)
            raise
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    self.logger.warning("Could not delete temporary Groq wav %s", temp_path, exc_info=True)

    def _post_groq_wav(self, wav_path: Path, api_key: str, model: str, language: str | None, job_id: str, prompt: str = "") -> dict:
        boundary = f"----Waky{uuid.uuid4().hex}"

        def field(name: str, value: str) -> bytes:
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")

        body = bytearray()
        body.extend(field("model", model))
        body.extend(field("temperature", "0"))
        body.extend(field("response_format", "json"))
        if language:
            body.extend(field("language", language))
        if prompt:
            body.extend(field("prompt", prompt))
        file_bytes = wav_path.read_bytes()
        body.extend(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{wav_path.name}"\r\n'
                "Content-Type: audio/wav\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(file_bytes)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Waky/1.0",
        }
        try:
            status, hdrs, data = http_pool.STT.request("POST", "/openai/v1/audio/transcriptions", bytes(body), headers, timeout=45)
        except (OSError, http.client.HTTPException) as exc:
            raise RuntimeError(f"Groq API network error job_id={job_id}: {exc}") from exc
        if status == 429:
            try:
                retry_after = float(hdrs.get("retry-after", "60"))
            except (TypeError, ValueError):
                retry_after = 60.0
            llm_engine.STT_STATUS.cooldown_until = time.time() + retry_after
            raise GroqRateLimited(retry_after)
        if status != 200:
            raise RuntimeError(f"Groq API error status={status} job_id={job_id} body={data.decode('utf-8', 'replace')}")
        return json.loads(data.decode("utf-8"))

    def _groq_api_key(self) -> str:
        provider_key = self.settings.get("providers", {}).get("groq", {}).get("api_key", "").strip()
        if provider_key:
            return provider_key
        env_path = DATA_DIR / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    clean = line.strip()
                    if not clean or clean.startswith("#") or "=" not in clean:
                        continue
                    key, value = clean.split("=", 1)
                    if key.strip() == "GROQ_API_KEY":
                        return value.strip().strip('"').strip("'")
            except Exception:
                self.logger.warning("Could not read .env for GROQ_API_KEY", exc_info=True)
        return os.environ.get("GROQ_API_KEY", "").strip()

    def _run_transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None, task: str, job_id: str) -> TranscriptionResult:
        started = time.perf_counter()
        self.logger.info("Transcription started job_id=%s duration_samples=%s sample_rate=%s device=%s", job_id, audio.size, sample_rate, self.device_used)
        segments, info = self.model.transcribe(
            audio,
            language=language,
            task=task,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 450},
            beam_size=3,
            condition_on_previous_text=False,
            initial_prompt=speech_hints.stt_prompt(self.settings) or None,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        detected_language = getattr(info, "language", None)
        self.logger.info(
            "Transcription finished job_id=%s seconds=%.3f chars=%s language=%s device=%s",
            job_id,
            time.perf_counter() - started,
            len(text),
            detected_language,
            self.device_used,
        )
        return TranscriptionResult(
            text=text,
            language=detected_language,
            device=self.device_used,
            model=self.settings.get("transcription", {}).get("model", "base"),
        )

    def _transcribe_fresh_cpu(self, audio: np.ndarray, sample_rate: int, language: str | None, task: str, job_id: str, context: dict) -> TranscriptionResult:
        from faster_whisper import WhisperModel

        started = time.perf_counter()
        model_name = context.get("model", "base")
        self.model_load_status = f"Loading {model_name} on CPU (int8) for isolated in-process job"
        self.device_used = "CPU"
        self.compute_type_used = "int8"
        self.logger.info("Fresh CPU model load start context=%s", context)
        model = WhisperModel(str(model_name), device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            audio,
            language=language,
            task=task,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 450},
            beam_size=3,
            condition_on_previous_text=False,
            initial_prompt=speech_hints.stt_prompt(self.settings) or None,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        detected_language = getattr(info, "language", None)
        self.model_load_status = "Safe CPU in-process job completed"
        self.logger.info("Fresh CPU transcription finished job_id=%s seconds=%.3f chars=%s language=%s", job_id, time.perf_counter() - started, len(text), detected_language)
        return TranscriptionResult(text=text, language=detected_language, device="CPU", model=str(model_name))

    def _transcribe_subprocess(self, audio: np.ndarray, sample_rate: int, language: str | None, task: str, job_id: str, context: dict) -> TranscriptionResult:
        temp_path: Path | None = None
        started = time.perf_counter()
        try:
            with tempfile.NamedTemporaryFile(prefix=f"waky_{job_id}_", suffix=".wav", delete=False) as handle:
                temp_path = Path(handle.name)
            wavfile.write(temp_path, sample_rate, self._to_int16(audio))
            out_path = temp_path.with_suffix(".json")
            script = Path(__file__).resolve().parents[1] / "tools" / "transcribe_once.py"
            # Packaged build: the exe itself is the worker (see main.py), there is no script file.
            launcher = [sys.executable, "--transcribe-once"] if FROZEN else [sys.executable, str(script)]
            command = [
                *launcher,
                "--wav",
                str(temp_path),
                "--model",
                str(context.get("model", "base")),
                "--language",
                language or "",
                "--task",
                task,
                "--job-id",
                job_id,
                "--prompt",
                speech_hints.stt_prompt(self.settings),
                "--out",
                str(out_path),
            ]
            self.device_used = "CPU"
            self.compute_type_used = "int8"
            self.model_load_status = "Safe CPU subprocess running"
            self.logger.info("Subprocess transcription start context=%s command=%s", context, command)
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=90, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            result_text = out_path.read_text(encoding="utf-8") if out_path.exists() else completed.stdout.strip()
            if completed.returncode != 0 and not result_text:
                raise RuntimeError(f"subprocess transcription failed rc={completed.returncode} stderr={completed.stderr.strip()}")
            payload = json.loads(result_text)
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error", "subprocess transcription failed"))
            text = str(payload.get("text", "")).strip()
            detected_language = payload.get("language")
            self.model_load_status = "Safe CPU subprocess completed"
            self.logger.info("Subprocess transcription finished job_id=%s seconds=%.3f chars=%s language=%s", job_id, time.perf_counter() - started, len(text), detected_language)
            return TranscriptionResult(text=text, language=detected_language, device="CPU", model=str(context.get("model", "base")))
        except subprocess.TimeoutExpired as exc:
            self.last_error = f"subprocess timeout after 90s: {exc}"
            self.logger.error("Subprocess transcription timeout context=%s traceback=%s", context, traceback.format_exc())
            raise TimeoutError("subprocess transcription timed out after 90 seconds") from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                    temp_path.with_suffix(".json").unlink(missing_ok=True)
                except Exception:
                    self.logger.warning("Could not delete temporary transcription wav %s", temp_path, exc_info=True)

    def _to_int16(self, audio: np.ndarray) -> np.ndarray:
        clipped = np.clip(audio.astype(np.float32), -1.0, 1.0)
        return (clipped * 32767).astype(np.int16)

    def _rms(self, audio: np.ndarray) -> float:
        if audio.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio.astype(np.float32)))))

    def device_display(self) -> str:
        if self.device_used == "unknown":
            transcription = self.settings.get("transcription", {})
            if transcription.get("engine_mode", "safe_cpu") == "safe_cpu":
                return "Safe CPU (base/int8)"
            return "CUDA if available, else CPU"
        return f"{self.device_used} ({self.compute_type_used})"
