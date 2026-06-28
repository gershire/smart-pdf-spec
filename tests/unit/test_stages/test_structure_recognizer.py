"""Unit tests for StructureRecognizer stage (task 7.4)."""

from __future__ import annotations

import uuid

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    ElementType,
    FontInfo,
    Heading,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.structure_recognizer import StructureRecognizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(*pages: Page) -> Document:
    doc = Document(
        metadata=DocumentMetadata(page_count=len(pages), file_size_bytes=0),
        assets_folder=__file__,  # type: ignore[arg-type]
    )
    for page in pages:
        doc.add_page(page)
    return doc


def _make_page(*elements) -> Page:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    for el in elements:
        page.add_element(el)
    return page


def _tb(text: str, font_size: float, y0: float = 100.0) -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=50.0, y0=y0, x1=400.0, y1=y0 + 20.0),
        page_number=0,
        text=text,
        font_info=FontInfo(name="Helvetica", size=font_size, weight="normal", style="normal"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStructureRecognizerName:
    def test_name(self) -> None:
        assert StructureRecognizer().name == "structure_recognizer"


class TestStructureRecognizerValidate:
    def test_no_pages_emits_warning(self) -> None:
        doc = _make_doc()
        warnings = StructureRecognizer().validate(doc, Config())
        assert any(w.code == "no_pages" for w in warnings)

    def test_with_pages_no_warnings(self) -> None:
        doc = _make_doc(_make_page(_tb("text", 12.0)))
        assert StructureRecognizer().validate(doc, Config()) == []


class TestStructureRecognizerProcess:
    def test_populates_structure(self) -> None:
        body = _tb("Normal text.", 12.0, y0=100.0)
        big = _tb("Chapter One", 24.0, y0=50.0)
        doc = _make_doc(_make_page(body, big))
        result = StructureRecognizer().process(doc, Config())
        assert result.structure is not None
        assert len(result.structure.headings) >= 1

    def test_promotes_large_font_to_heading(self) -> None:
        body = _tb("body text", 12.0, y0=100.0)
        title = _tb("Big Title", 24.0, y0=50.0)
        doc = _make_doc(_make_page(body, title))
        result = StructureRecognizer().process(doc, Config())
        heading_texts = [h.text for h in result.structure.headings]
        assert "Big Title" in heading_texts

    def test_heading_level_assigned(self) -> None:
        body = _tb("body", 12.0, y0=200.0)
        h1 = _tb("H1 Title", 30.0, y0=50.0)
        h2 = _tb("H2 Title", 20.0, y0=100.0)
        doc = _make_doc(_make_page(body, h1, h2))
        result = StructureRecognizer().process(doc, Config())
        levels = {h.text: h.level for h in result.structure.headings}
        assert levels["H1 Title"] < levels["H2 Title"]  # H1 should have lower level number

    def test_toc_built_from_headings(self) -> None:
        title = _tb("Introduction", 24.0, y0=50.0)
        body = _tb("Some text.", 12.0, y0=100.0)
        doc = _make_doc(_make_page(body, title))
        result = StructureRecognizer().process(doc, Config())
        toc_titles = [e.title for e in result.structure.toc.entries]
        assert "Introduction" in toc_titles

    def test_reading_order_top_to_bottom(self) -> None:
        el1 = _tb("first", 12.0, y0=50.0)
        el2 = _tb("second", 12.0, y0=200.0)
        el3 = _tb("third", 12.0, y0=400.0)
        doc = _make_doc(_make_page(el3, el1, el2))  # deliberately out of order
        result = StructureRecognizer().process(doc, Config())
        order = result.structure.reading_order
        ids = [el.element_id for el in [el1, el2, el3]]
        assert order.index(ids[0]) < order.index(ids[1]) < order.index(ids[2])

    def test_empty_document_structure_has_no_headings(self) -> None:
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        doc = _make_doc(page)
        result = StructureRecognizer().process(doc, Config())
        assert result.structure is not None
        assert result.structure.headings == []

    def test_heading_like_text_promoted_by_content(self) -> None:
        el = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TEXT_BLOCK,
            bbox=BoundingBox(x0=50, y0=50, x1=400, y1=70),
            page_number=0,
            text="1. Introduction",
        )
        doc = _make_doc(_make_page(el))
        result = StructureRecognizer().process(doc, Config())
        assert len(result.structure.headings) >= 1

    def test_median_font_size_empty(self) -> None:
        assert StructureRecognizer._median_font_size([]) == 0.0

    def test_median_font_size_odd(self) -> None:
        elements = [_tb("x", s) for s in [10.0, 12.0, 14.0]]
        assert StructureRecognizer._median_font_size(elements) == pytest.approx(12.0)

    def test_median_font_size_even(self) -> None:
        elements = [_tb("x", s) for s in [10.0, 12.0, 14.0, 16.0]]
        assert StructureRecognizer._median_font_size(elements) == pytest.approx(13.0)
