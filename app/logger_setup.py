from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .utils import LOG_DIR


def setup_logging(level_name: str = "warning") -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    debug_enabled = str(level_name).lower() == "debug"
    logger = logging.getLogger("waky")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    error_handler = RotatingFileHandler(LOG_DIR / "error.log", maxBytes=512_000, backupCount=3, encoding="utf-8")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(error_handler)

    if debug_enabled:
        debug_handler = RotatingFileHandler(LOG_DIR / "debug.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(debug_handler)

    logger.propagate = False
    return logger
