from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ghelper.paths import state_dir


def get_logger(name: str = "ghelper") -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    log.addHandler(stream)
    try:
        path = state_dir() / "ghelper.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(fmt)
        log.addHandler(handler)
    except OSError:
        pass
    return log
