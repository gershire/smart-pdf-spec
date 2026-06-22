"""Unit tests for ProcessingResult and ProcessingStatistics (task 1.7)."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.result import ProcessingResult, ProcessingStatistics


def _stats() -> ProcessingStatistics:
    return ProcessingStatistics(
        total_pages=2,
        pages_processed=2,
        elements_detected=10,
        tables_extracted=1,
        images_extracted=3,
        processing_time_seconds=4.2,
        start_time=datetime(2024, 1, 1, 0, 0, 0),
        end_time=datetime(2024, 1, 1, 0, 0, 4),
    )


def test_statistics_rejects_negative_metric() -> None:
    with pytest.raises(ValidationError):
        ProcessingStatistics(
            total_pages=-1,
            pages_processed=0,
            elements_detected=0,
            tables_extracted=0,
            images_extracted=0,
            processing_time_seconds=0.0,
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1),
        )


def test_result_defaults() -> None:
    result = ProcessingResult(success=True, statistics=_stats())
    assert result.document is None
    assert result.warnings == []
    assert result.errors == []


def test_result_with_document_and_paths() -> None:
    doc = Document(
        metadata=DocumentMetadata(page_count=2, file_size_bytes=100),
        assets_folder=Path("assets"),
    )
    result = ProcessingResult(
        success=True,
        document=doc,
        markdown_path="out/doc.md",
        assets_folder="out/assets",
        warnings=["low confidence on page 1"],
        statistics=_stats(),
    )
    assert result.markdown_path == Path("out/doc.md")
    assert result.assets_folder == Path("out/assets")


def test_result_json_round_trip() -> None:
    result = ProcessingResult(success=False, errors=["boom"], statistics=_stats())
    restored = ProcessingResult.model_validate(json.loads(result.model_dump_json()))
    assert restored.success is False
    assert restored.errors == ["boom"]
    assert restored.statistics == result.statistics
