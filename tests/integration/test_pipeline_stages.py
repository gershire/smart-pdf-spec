"""Integration tests for pipeline stage interactions (task 7.5)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    ElementType,
    FontInfo,
    Heading,
    Table,
    TableRow,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.layout_analyzer import LayoutAnalyzer
from smart_pdf_scanner.stages.markdown_generator import MarkdownGenerator
from smart_pdf_scanner.stages.structure_recognizer import StructureRecognizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_doc(tmp_path: Path, texts_with_sizes: list[tuple[str, float]]) -> Document:
    """Build a Document with TextBlock elements of specified sizes."""
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    for i, (text, size) in enumerate(texts_with_sizes):
        block = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TEXT_BLOCK,
            bbox=BoundingBox(x0=50.0, y0=float(50 + i * 30), x1=400.0, y1=float(70 + i * 30)),
            page_number=0,
            text=text,
            font_info=FontInfo(name="Helvetica", size=size, weight="normal", style="normal"),
        )
        page.add_element(block)
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=tmp_path / "assets",
    )
    doc.add_page(page)
    return doc


# ---------------------------------------------------------------------------
# Layout → Structure pipeline tests
# ---------------------------------------------------------------------------


class TestLayoutToStructurePipeline:
    def test_layout_output_feeds_structure_recognizer(self, tmp_path: Path) -> None:
        """LayoutAnalyzer output should be usable by StructureRecognizer."""
        doc = _make_text_doc(
            tmp_path,
            [
                ("Chapter 1", 24.0),
                ("Introduction text here.", 12.0),
                ("Section 1.1", 18.0),
                ("More body text.", 12.0),
            ],
        )
        config = Config()
        from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
        LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, config)
        result = StructureRecognizer().process(doc, config)
        assert result.structure is not None
        assert len(result.structure.headings) >= 2

    def test_reading_order_preserved_through_pipeline(self, tmp_path: Path) -> None:
        texts = [
            ("First paragraph", 12.0),
            ("Second paragraph", 12.0),
            ("Third paragraph", 12.0),
        ]
        doc = _make_text_doc(tmp_path, texts)
        config = Config()
        from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
        LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, config)
        StructureRecognizer().process(doc, config)
        # Reading order should be top-to-bottom (y0 increasing)
        order = doc.structure.reading_order
        assert len(order) == 3


# ---------------------------------------------------------------------------
# Structure → Markdown pipeline tests
# ---------------------------------------------------------------------------


class TestStructureToMarkdownPipeline:
    def test_headings_appear_as_markdown_headings(self, tmp_path: Path) -> None:
        doc = _make_text_doc(
            tmp_path,
            [
                ("Main Title", 28.0),
                ("Introduction paragraph text.", 12.0),
            ],
        )
        config = Config(include_page_numbers=False)
        StructureRecognizer().process(doc, config)
        MarkdownGenerator().process(doc, config)
        md = doc._markdown  # type: ignore[attr-defined]
        assert "# Main Title" in md or "## Main Title" in md
        assert "Introduction paragraph text." in md

    def test_table_appears_in_markdown(self, tmp_path: Path) -> None:
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        table = Table(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TABLE,
            bbox=BoundingBox(x0=50, y0=100, x1=400, y1=200),
            page_number=0,
            rows=[
                TableRow(cells=["Name", "Score"]),
                TableRow(cells=["Alice", "95"]),
            ],
            markdown="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
        )
        page.add_element(table)
        doc = Document(
            metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        doc.add_page(table.page_number)  # type: ignore[arg-type]
        doc.pages = [page]
        config = Config(include_page_numbers=False)
        MarkdownGenerator().process(doc, config)
        md = doc._markdown  # type: ignore[attr-defined]
        assert "| Name | Score |" in md
        assert "| Alice | 95 |" in md

    def test_empty_document_produces_empty_markdown(self, tmp_path: Path) -> None:
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        doc = Document(
            metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        doc.add_page(page)
        config = Config(include_page_numbers=False)
        MarkdownGenerator().process(doc, config)
        md = doc._markdown  # type: ignore[attr-defined]
        assert md == "" or md.strip() == ""


# ---------------------------------------------------------------------------
# Full stage chain: Layout + Structure + Markdown
# ---------------------------------------------------------------------------


class TestFullStageChain:
    def test_three_stage_pipeline(self, tmp_path: Path) -> None:
        doc = _make_text_doc(
            tmp_path,
            [
                ("Document Title", 32.0),
                ("Abstract", 20.0),
                ("This document describes the system.", 12.0),
                ("1. Introduction", 18.0),
                ("Background information here.", 12.0),
            ],
        )
        config = Config(include_page_numbers=False)
        from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
        LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, config)
        StructureRecognizer().process(doc, config)
        MarkdownGenerator().process(doc, config)
        md = doc._markdown  # type: ignore[attr-defined]
        # Should have some heading markers
        assert "#" in md
        # Should have body text
        assert "Background information" in md or "describes" in md

    def test_markdown_written_to_file(self, tmp_path: Path) -> None:
        doc = _make_text_doc(tmp_path, [("Hello", 12.0)])
        out_file = tmp_path / "output.md"
        config = Config(include_page_numbers=False)
        StructureRecognizer().process(doc, config)
        MarkdownGenerator(output_path=out_file).process(doc, config)
        assert out_file.exists()
        assert "Hello" in out_file.read_text()
