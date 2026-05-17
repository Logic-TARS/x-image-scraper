"""Logging configuration helpers."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _ensure_utf8_output() -> None:
    """Configure stdout/stderr to use UTF-8 to avoid UnicodeEncodeError on Windows with CJK text."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and stream.encoding and stream.encoding.lower() != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def configure_logging(log_file: str = "logs/scraper.log", level: int = logging.INFO) -> None:
    """Configure shared console and file logging once."""
    _ensure_utf8_output()
    if getattr(configure_logging, "_configured", False):
        return

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3, 
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    try:
        from rich.logging import RichHandler
        console_handler = RichHandler(rich_tracebacks=True, show_time=False, show_path=False)
    except ImportError:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[console_handler, file_handler],
    )
    configure_logging._configured = True
