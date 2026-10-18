from __future__ import annotations

import logging

LOGGER = logging.getLogger("waky")

# Approximate download sizes, shown to the user before they opt in.
MODEL_SIZES_MB = {
    "tiny": 75,
    "base": 145,
    "small": 480,
    "medium": 1500,
    "large-v3-turbo": 1600,
    "large-v3": 3000,
}


def size_label(model: str) -> str:
    mb = MODEL_SIZES_MB.get(model)
    if mb is None:
        return "size unknown"
    return f"~{mb / 1000:.1f} GB" if mb >= 1000 else f"~{mb} MB"


def is_downloaded(model: str) -> bool:
    try:
        from faster_whisper.utils import download_model

        download_model(model, local_files_only=True)
        return True
    except Exception:
        return False


def download(model: str) -> str:
    """Download a faster-whisper model into the Hugging Face cache. Blocking; run in a worker thread."""
    from faster_whisper.utils import download_model

    LOGGER.info("[MODEL] download start model=%s", model)
    path = download_model(model)
    LOGGER.info("[MODEL] download finished model=%s", model)
    return str(path)
