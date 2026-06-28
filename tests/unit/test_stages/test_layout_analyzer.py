"""Unit tests for LayoutAnalyzer stage (task 7.4)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, FontInfo, TextBlock
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.base import ValidationWarning
from smart_pdf_scanner.stages.layout_analyzer import LayoutAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_with_page(*elements) -> tuple[Document, Page]:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    for el in elements:
        page.add_element(el)
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=__file__,  # type: ignore[arg-type]
    )
    doc.add_page(page)
    return doc, page


def _text_block(text: str = "hello", font_size: float = 12.0) -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=50.0, y0=50.0, x1=400.0, y1=100.0),
        page_number=0,
        text=text,
        font_info=FontInfo(name="Helvetica", size=font_size, weight="normal", style="normal"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLayoutAnalyzerName:
    def test_name(self) -> None:
        analyzer = LayoutAnalyzer(primary_engine=HeuristicEngine())
        assert analyzer.name == "layout_analyzer"


class TestLayoutAnalyzerValidate:
    def test_no_pages_emits_warning(self) -> None:
        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=__file__,  # type: ignore[arg-type]
        )
        analyzer = LayoutAnalyzer(primary_engine=HeuristicEngine())
        warnings = analyzer.validate(doc, Config())
        assert any(w.code == "no_pages" for w in warnings)

    def test_with_pages_no_warnings(self) -> None:
        doc, _ = _doc_with_page(_text_block())
        analyzer = LayoutAnalyzer(primary_engine=HeuristicEngine())
        assert analyzer.validate(doc, Config()) == []


class TestLayoutAnalyzerProcess:
    def test_processes_all_pages(self) -> None:
        doc, page = _doc_with_page(_text_block())
        analyzer = LayoutAnalyzer(primary_engine=HeuristicEngine())
        result = analyzer.process(doc, Config())
        assert len(result.pages) == 1
        assert result.pages[0].elements  # elements set by engine

    def test_primary_engine_called(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock_primary"
        mock_engine.detect_layout.return_value = []
        mock_engine.get_confidence.return_value = 0.9
        doc, _ = _doc_with_page(_text_block())
        analyzer = LayoutAnalyzer(primary_engine=mock_engine)
        analyzer.process(doc, Config())
        assert mock_engine.detect_layout.called

    def test_falls_back_when_primary_fails(self) -> None:
        failing_engine = MagicMock()
        failing_engine.name = "failing"
        failing_engine.detect_layout.side_effect = RuntimeError("engine crash")
        fallback = HeuristicEngine()
        doc, _ = _doc_with_page(_text_block("fallback text", 12.0))
        analyzer = LayoutAnalyzer(primary_engine=failing_engine, fallback_engine=fallback)
        result = analyzer.process(doc, Config())
        # Fallback should have run; elements should exist
        assert isinstance(result.pages[0].elements, list)

    def test_falls_back_when_primary_returns_empty(self) -> None:
        primary = MagicMock()
        primary.name = "primary"
        primary.detect_layout.return_value = []
        primary.get_confidence.return_value = 0.0
        fallback = MagicMock()
        fallback.name = "fallback"
        fallback_el = _text_block("from fallback")
        fallback.detect_layout.return_value = [fallback_el]
        doc, _ = _doc_with_page(_text_block())
        analyzer = LayoutAnalyzer(primary_engine=primary, fallback_engine=fallback)
        analyzer.process(doc, Config())
        assert fallback.detect_layout.called

    def test_does_not_fall_back_when_primary_confident(self) -> None:
        primary = MagicMock()
        primary.name = "primary"
        el = _text_block("primary result")
        el.confidence = 0.95
        primary.detect_layout.return_value = [el]
        primary.get_confidence.return_value = 0.95
        fallback = MagicMock()
        fallback.name = "fallback"
        fallback.detect_layout.return_value = []
        doc, _ = _doc_with_page(_text_block())
        analyzer = LayoutAnalyzer(primary_engine=primary, fallback_engine=fallback)
        analyzer.process(doc, Config(layout_confidence_threshold=0.5))
        assert not fallback.detect_layout.called

    def test_default_fallback_is_heuristic(self) -> None:
        primary = MagicMock()
        primary.name = "primary"
        primary.detect_layout.return_value = []
        primary.get_confidence.return_value = 0.0
        analyzer = LayoutAnalyzer(primary_engine=primary)
        assert isinstance(analyzer._fallback, HeuristicEngine)
