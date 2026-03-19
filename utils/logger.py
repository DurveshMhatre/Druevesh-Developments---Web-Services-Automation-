"""
Structured logging with rotating file handler and colored console output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR

# ── Color codes for console output ───────────────────────────────
_COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes based on log level."""

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        message = super().format(record)
        return f"{color}{message}{_RESET}" if color else message


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger with file + console handlers.

    Args:
        name: Module name (typically ``__name__``).

    Returns:
        A ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on multiple calls
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # ── File handler (rotating, 5 MB, 3 backups) ─────────────────
    log_file = LOGS_DIR / "automation.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

    # ── Console handler (colored) ────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_ColorFormatter(log_format, datefmt=date_format))
    logger.addHandler(console_handler)

    return logger
