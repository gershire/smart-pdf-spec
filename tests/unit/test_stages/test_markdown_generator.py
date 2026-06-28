"""Unit tests for MarkdownGenerator stage (task 7.4)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    ElementType,
    Heading,
    Image,
    ImageType,
    Table,
    TableRow,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.models.structure import DocumentStructure, TableOfContents
from smart_pdf_scanner.stages.base import ValidationWarning
from smart_pdf_scanner.stages.markdown_generator import MarkdownGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(*elements, structure=None) -> Document:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    for el in elements:
        page.add_element(el)
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=Path("/tmp"),
    )
    doc.add_page(page)
    if structure:
        doc.structure = structure
    return doc


def _heading(text: str, level: int = 1, y0: float = 50.0) -> Heading:
    return Heading(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.HEADING,
        bbox=BoundingBox(x0=50, y0=y0, x1=400, y1=y0 + 20),
        page_number=0,
        text=text,
        level=level,
    )


def _text(text: str, y0: float = 100.0) -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=50, y0=y0, x1=400, y1=y0 + 20),
        page_number=0,
        text=text,
    )


def _table(rows_data: list[list[str]]) -> Table:
    rows = [TableRow(cells=r) for r in rows_data]
    return Table(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TABLE,
        bbox=BoundingBox(x0=50, y0=200, x1=400, y1=300),
        page_number=0,
        rows=rows,
        markdown="",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMarkdownGeneratorName:
    def test_name(self) -> None:
        assert MarkdownGenerator().name == "markdown_generator"


class TestMarkdownGeneratorValidate:
    def test_no_pages_emits_warning(self) -> None:
        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=Path("/tmp"),
        )
        warnings = MarkdownGenerator().validate(doc, Config())
        assert any(w.code == "no_pages" for w in warnings)

    def test_with_pages_no_warnings(self) -> None:
        doc = _doc(_text("hello"))
        assert MarkdownGenerator().validate(doc, Config()) == []


class TestFormatHeading:
    def test_h1(self) -> None:
        md = MarkdownGenerator()
        assert md.format_heading(_heading("Title", level=1)) == "# Title"

    def test_h2(self) -> None:
        md = MarkdownGenerator()
        assert md.format_heading(_heading("Section", level=2)) == "## Section"

    def test_h6_max(self) -> None:
        md = MarkdownGenerator()
        assert md.format_heading(_heading("Sub", level=6)) == "###### Sub"

    def test_level_6_uses_six_hashes(self) -> None:
        h = _heading("x", level=6)
        result = MarkdownGenerator().format_heading(h)
        assert result.startswith("######")

    def test_level_1_uses_one_hash(self) -> None:
        h = _heading("x", level=1)
        result = MarkdownGenerator().format_heading(h)
        assert result.startswith("# ")


class TestFormatTable:
    def test_basic_table(self) -> None:
        tbl = _table([["Name", "Age"], ["Alice", "30"], ["Bob", "25"]])
        result = MarkdownGenerator().format_table(tbl)
        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result

    def test_empty_table_returns_empty(self) -> None:
        tbl = Table(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TABLE,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
            page_number=0,
            rows=[],
            markdown="",
        )
        assert MarkdownGenerator().format_table(tbl) == ""

    def test_uses_precomputed_markdown(self) -> None:
        tbl = _table([["A", "B"]])
        tbl.markdown = "pre-computed"  # type: ignore[attr-defined]
        assert MarkdownGenerator().format_table(tbl) == "pre-computed"

    def test_pipe_escaped_in_cells(self) -> None:
        tbl = _table([["A|B", "C"]])
        result = MarkdownGenerator().format_table(tbl)
        assert "A\\|B" in result


class TestFormatImage:
    def test_image_with_file_path(self, tmp_path: Path) -> None:
        img = Image(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.IMAGE,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
            page_number=0,
            image_type=ImageType.PHOTOGRAPH,
            image_path=tmp_path / "test.png",
            description="A cat photo",
        )
        result = MarkdownGenerator().format_image(img)
        assert "![A cat photo]" in result
        assert "test.png" in result

    def test_image_without_file_path(self) -> None:
        img = Image(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.IMAGE,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
            page_number=0,
            image_type=ImageType.DIAGRAM,
            description="",
        )
        result = MarkdownGenerator().format_image(img)
        assert "*[Image:" in result

    def test_image_with_caption(self, tmp_path: Path) -> None:
        img = Image(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.IMAGE,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
            page_number=0,
            image_type=ImageType.PHOTOGRAPH,
            image_path=tmp_path / "fig1.png",
            description="A chart",
            caption="Figure 1: Example",
        )
        result = MarkdownGenerator().format_image(img)
        assert "Figure 1: Example" in result


class TestAssembleMarkdown:
    def test_heading_and_text(self) -> None:
        h = _heading("Intro", level=1, y0=50.0)
        t = _text("Body text.", y0=100.0)
        doc = _doc(h, t)
        config = Config(include_page_numbers=False)
        md = MarkdownGenerator().assemble_markdown(doc, config)
        assert "# Intro" in md
        assert "Body text." in md

    def test_page_numbers_inserted_when_enabled(self) -> None:
        doc = _doc(_text("hello"))
        config = Config(include_page_numbers=True)
        md = MarkdownGenerator().assemble_markdown(doc, config)
        assert "Page" in md

    def test_page_numbers_omitted_when_disabled(self) -> None:
        doc = _doc(_text("hello"))
        config = Config(include_page_numbers=False)
        md = MarkdownGenerator().assemble_markdown(doc, config)
        assert "Page" not in md

    def test_reading_order_respected(self) -> None:
        first = _text("FIRST", y0=50.0)
        second = _text("SECOND", y0=200.0)
        # Reversed in page elements; reading_order should fix it
        doc = _doc(second, first)
        ids = [el.element_id for el in doc.pages[0].elements]
        from smart_pdf_scanner.models.structure import DocumentStructure, TableOfContents
        doc.structure = DocumentStructure(
            headings=[],
            toc=TableOfContents(entries=[]),
            reading_order=[first.element_id, second.element_id],
        )
        config = Config(include_page_numbers=False)
        md = MarkdownGenerator().assemble_markdown(doc, config)
        assert md.index("FIRST") < md.index("SECOND")


class TestWriteOutput:
    def test_writes_to_file(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        MarkdownGenerator().write_output("# Hello", out)
        assert out.read_text() == "# Hello"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "subdir" / "nested" / "output.md"
        MarkdownGenerator().write_output("content", out)
        assert out.exists()


class TestProcess:
    def test_process_sets_markdown_on_document(self) -> None:
        doc = _doc(_text("hello"))
        MarkdownGenerator().process(doc, Config())
        assert hasattr(doc, "_markdown")
        assert "hello" in doc._markdown  # type: ignore[attr-defined]

    def test_process_writes_file_when_output_path_set(self, tmp_path: Path) -> None:
        doc = _doc(_text("hello"))
        out = tmp_path / "out.md"
        MarkdownGenerator(output_path=out).process(doc, Config())
        assert out.exists()
        assert "hello" in out.read_text()
