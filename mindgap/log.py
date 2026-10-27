"""Logging: logs/tick.log (shared, rotating) and work/<DAY>/run.log (per day)."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from .config import Config
from . import paths

_FMT = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")


def get_logger(cfg: Config, name: str = "mindgap", day: str | None = None, console: bool = True) -> logging.Logger:
    logger = logging.getLogger(f"{name}.{day}" if day else name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    d = paths.logs_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(d / "tick.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(_FMT)
    logger.addHandler(fh)
    if day:
        w = paths.work_dir(cfg, day)
        w.mkdir(parents=True, exist_ok=True)
        rh = logging.FileHandler(w / "run.log", encoding="utf-8")
        rh.setFormatter(_FMT)
        logger.addHandler(rh)
    if console:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(_FMT)
        logger.addHandler(sh)
    return logger
