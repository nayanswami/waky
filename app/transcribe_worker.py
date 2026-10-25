from __future__ import annotations

import argparse
import json
import sys
import time
import traceback

import numpy as np
from scipy.io import wavfile


def _read_audio(path: str) -> tuple[int, np.ndarray]:
    sample_rate, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.dtype == np.int16:
        samples = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        samples = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        samples = (data.astype(np.float32) - 128.0) / 128.0
    else:
        samples = data.astype(np.float32)
    return sample_rate, np.clip(samples, -1.0, 1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe one temporary Waky WAV file.")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--model", default="base")
    parser.add_argument("--language", default="")
    parser.add_argument("--task", default="transcribe")
    parser.add_argument("--job-id", default="manual")
    parser.add_argument("--prompt", default="", help="vocabulary hint for the speech model")
    parser.add_argument("--out", default="", help="write the JSON result here (packaged exe has no stdout)")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    try:
        from faster_whisper import WhisperModel

        sample_rate, samples = _read_audio(args.wav)
        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            samples,
            language=args.language or None,
            task=args.task,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 450},
            beam_size=3,
            condition_on_previous_text=False,
            initial_prompt=args.prompt or None,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        payload = {
            "ok": True,
            "job_id": args.job_id,
            "text": text,
            "language": getattr(info, "language", None),
            "sample_rate": sample_rate,
            "seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "job_id": args.job_id,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    encoded = json.dumps(payload, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    elif sys.stdout is not None:
        print(encoded, flush=True)
    return 0 if payload["ok"] else 1
