"""Structured logging utilities.

Provides a JSON log formatter and a :func:`setup_logging` helper that configures
the package logger for console and/or file output in either JSON or plain-text
format (Requirement 12). Arbitrary contextual fields (stage, page number,
element type, coordinates, confidence, ...) can be attached to log records via
the standard ``extra=`` argument and are included in the JSON output.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

LOGGER_NAME = "smart_pdf_scanner"

# Attributes present on every ``logging.LogRecord``; anything else is treated as
# user-supplied contextual data and emitted alongside the message.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Formatter that renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a compact JSON string."""
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _build_handler(log_format: str, stream_path: Path | None) -> logging.Handler:
    """Create a configured stream or file handler for the given format."""
    handler: logging.Handler
    if stream_path is not None:
        handler = logging.FileHandler(stream_path, encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    return handler


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure and return the package logger.

    Args:
        level: Log level name (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
        log_format: Output format, ``"json"`` or ``"text"``.
        log_file: Optional path; when given, logs are written to this file in
            addition to the console.

    Returns:
        The configured :class:`logging.Logger` for the package.

    Raises:
        ValueError: If ``level`` or ``log_format`` is not recognized.
    """
    if log_format not in ("json", "text"):
        raise ValueError(f"Unsupported log_format: {log_format!r} (expected 'json' or 'text')")

    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unsupported log level: {level!r}")

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(numeric_level)
    logger.propagate = False

    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    logger.addHandler(_build_handler(log_format, None))
    if log_file is not None:
        logger.addHandler(_build_handler(log_format, Path(log_file)))

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the package namespace.

    Args:
        name: Optional child logger name; when omitted the package logger is
            returned.

    Returns:
        The requested :class:`logging.Logger`.
    """
    if name is None:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
