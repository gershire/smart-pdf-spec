"""Unit tests for TableProcessor stage (task 7.4)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, TableRow, TextBlock
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.table_processor import TableProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(tmp_path: Path, with_pdf_path: bool = True) -> Document:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=tmp_path / "assets",
    )
    doc.add_page(page)
    if with_pdf_path:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 dummy")
        doc._pdf_path = pdf  # type: ignore[attr-defined]
    return doc


def _raw_table() -> list[list[str | None]]:
    return [
        ["Name", "Age", "City"],
        ["Alice", "30", "London"],
        ["Bob", None, "Paris"],
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTableProcessorName:
    def test_name(self) -> None:
        assert TableProcessor().name == "table_processor"


class TestTableProcessorValidate:
    def test_no_pages_warning(self, tmp_path: Path) -> None:
        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        warnings = TableProcessor().validate(doc, Config())
        assert any(w.code == "no_pages" for w in warnings)

    def test_missing_pdf_path_warning(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path, with_pdf_path=False)
        warnings = TableProcessor().validate(doc, Config())
        assert any(w.code == "missing_pdf_path" for w in warnings)

    def test_valid_doc_no_warnings(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path)
        warnings = TableProcessor().validate(doc, Config())
        assert warnings == []


class TestConvertToMarkdown:
    def test_basic_table(self) -> None:
        rows = [
            TableRow(cells=["Name", "Age"]),
            TableRow(cells=["Alice", "30"]),
        ]
        result = TableProcessor.convert_to_markdown(rows)
        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result

    def test_empty_rows_returns_empty(self) -> None:
        assert TableProcessor.convert_to_markdown([]) == ""

    def test_pipe_escaped_in_cells(self) -> None:
        rows = [
            TableRow(cells=["A|B", "C"]),
            TableRow(cells=["x", "y"]),
        ]
        result = TableProcessor.convert_to_markdown(rows)
        assert "A\\|B" in result

    def test_uneven_rows_padded(self) -> None:
        rows = [
            TableRow(cells=["A", "B", "C"]),
            TableRow(cells=["x"]),
        ]
        result = TableProcessor.convert_to_markdown(rows)
        line_count = len(result.strip().split("\n"))
        assert line_count == 3  # header + separator + data row


class TestExportToCSV:
    def test_creates_csv_file(self, tmp_path: Path) -> None:
        rows = [
            TableRow(cells=["Name", "Age"]),
            TableRow(cells=["Alice", "30"]),
        ]
        out = tmp_path / "out.csv"
        TableProcessor.export_to_csv(rows, out)
        content = out.read_text()
        assert "Name,Age" in content
        assert "Alice,30" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "subdir" / "tables.csv"
        TableProcessor.export_to_csv([], out)
        assert out.parent.exists()


class TestTableProcessorProcess:
    def test_skips_when_no_pdf_path(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path, with_pdf_path=False)
        result = TableProcessor().process(doc, Config())
        assert result is doc  # document unchanged

    def test_skips_when_pdfplumber_not_installed(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path)
        with patch.dict("sys.modules", {"pdfplumber": None}):
            result = TableProcessor().process(doc, Config())
        # Should return document without crashing
        assert result is doc

    def test_extracts_table_from_page(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path)
        mock_plumber_page = MagicMock()
        mock_plumber_page.extract_tables.return_value = [_raw_table()]
        mock_table_obj = MagicMock()
        mock_table_obj.bbox = (50.0, 100.0, 400.0, 300.0)
        mock_plumber_page.find_tables.return_value = [mock_table_obj]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_plumber_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict("sys.modules", {"pdfplumber": mock_pdfplumber}):
            result = TableProcessor().process(doc, Config())

        from smart_pdf_scanner.models.elements import Table
        tables = [
            el for el in result.pages[0].elements if el.element_type == ElementType.TABLE
        ]
        assert len(tables) == 1

    def test_csv_export_when_configured(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path)
        doc.assets_folder.mkdir(parents=True, exist_ok=True)
        mock_plumber_page = MagicMock()
        mock_plumber_page.extract_tables.return_value = [_raw_table()]
        mock_plumber_page.find_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_plumber_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        config = Config(export_tables_csv=True)
        with patch.dict("sys.modules", {"pdfplumber": mock_pdfplumber}):
            TableProcessor().process(doc, config)

        csv_files = list(doc.assets_folder.glob("*.csv"))
        assert len(csv_files) == 1

    def test_page_out_of_range_skipped(self, tmp_path: Path) -> None:
        doc = _doc(tmp_path)
        # pdfplumber has 0 pages, but doc has 1
        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict("sys.modules", {"pdfplumber": mock_pdfplumber}):
            result = TableProcessor().process(doc, Config())
        assert result is doc
