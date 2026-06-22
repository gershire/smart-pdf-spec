"""Unit tests for structured logging utilities (task 1.7)."""

import json
import logging
from pathlib import Path

import pytest

from smart_pdf_scanner.utils.logging import (
    LOGGER_NAME,
    JsonFormatter,
    get_logger,
    setup_logging,
)


def _format(record_kwargs: dict[str, object]) -> dict[str, object]:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="smart_pdf_scanner.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="processing %s",
        args=("page",),
        exc_info=None,
    )
    for key, value in record_kwargs.items():
        setattr(record, key, value)
    return json.loads(formatter.format(record))


def test_json_formatter_basic_fields() -> None:
    payload = _format({})
    assert payload["level"] == "INFO"
    assert payload["logger"] == "smart_pdf_scanner.test"
    assert payload["message"] == "processing page"
    assert "timestamp" in payload


def test_json_formatter_includes_context() -> None:
    payload = _format({"stage": "ocr_processor", "page_number": 3, "confidence": 0.42})
    assert payload["stage"] == "ocr_processor"
    assert payload["page_number"] == 3
    assert payload["confidence"] == 0.42


def test_setup_logging_returns_package_logger() -> None:
    logger = setup_logging(level="DEBUG", log_format="json")
    assert logger.name == LOGGER_NAME
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1


def test_setup_logging_is_idempotent() -> None:
    setup_logging()
    logger = setup_logging()
    assert len(logger.handlers) == 1


def test_setup_logging_writes_json_file(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    logger = setup_logging(level="INFO", log_format="json", log_file=log_file)
    logger.info("hello", extra={"stage": "pdf_parser"})
    for handler in logger.handlers:
        handler.flush()

    contents = log_file.read_text(encoding="utf-8").strip()
    record = json.loads(contents.splitlines()[-1])
    assert record["message"] == "hello"
    assert record["stage"] == "pdf_parser"


def test_setup_logging_text_format(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    logger = setup_logging(level="INFO", log_format="text", log_file=log_file)
    logger.warning("careful")
    for handler in logger.handlers:
        handler.flush()
    assert "careful" in log_file.read_text(encoding="utf-8")


def test_setup_logging_rejects_bad_format() -> None:
    with pytest.raises(ValueError):
        setup_logging(log_format="xml")


def test_setup_logging_rejects_bad_level() -> None:
    with pytest.raises(ValueError):
        setup_logging(level="LOUD")


def test_get_logger_namespacing() -> None:
    assert get_logger().name == LOGGER_NAME
    assert get_logger("ocr").name == f"{LOGGER_NAME}.ocr"
