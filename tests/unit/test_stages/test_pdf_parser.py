"""Unit tests for PDFParser stage (task 7.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import ElementType
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.stages.base import WarningSeverity
from smart_pdf_scanner.stages.pdf_parser import PDFParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_doc(tmp_path: Path) -> Document:
    return Document(
        metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
        assets_folder=tmp_path / "assets",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPDFParserName:
    def test_name(self) -> None:
        assert PDFParser().name == "pdf_parser"


class TestPDFParserValidate:
    def test_no_path_emits_error(self, tmp_path: Path) -> None:
        doc = _empty_doc(tmp_path)
        warnings = PDFParser().validate(doc, Config())
        assert any(w.code == "missing_pdf_path" for w in warnings)
        assert all(w.severity == WarningSeverity.ERROR for w in warnings)

    def test_missing_file_emits_error(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "missing.pdf"
        doc = _empty_doc(tmp_path)
        warnings = PDFParser(pdf_path=nonexistent).validate(doc, Config())
        assert any(w.code == "pdf_not_found" for w in warnings)

    def test_oversized_file_emits_warning(self, tmp_path: Path) -> None:
        big = tmp_path / "big.pdf"
        big.write_bytes(b"%PDF" + b"x" * (2 * 1024 * 1024))  # 2 MB
        config = Config(max_file_size_mb=1)
        doc = _empty_doc(tmp_path)
        warnings = PDFParser(pdf_path=big).validate(doc, config)
        assert any(w.code == "pdf_too_large" for w in warnings)

    def test_valid_pdf_no_warnings(self, tmp_path: Path) -> None:
        pdf = tmp_path / "ok.pdf"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        doc = _empty_doc(tmp_path)
        warnings = PDFParser(pdf_path=pdf).validate(doc, Config())
        assert warnings == []

    def test_resolves_path_from_document_attribute(self, tmp_path: Path) -> None:
        pdf = tmp_path / "ok.pdf"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        doc = _empty_doc(tmp_path)
        doc._pdf_path = pdf  # type: ignore[attr-defined]
        warnings = PDFParser().validate(doc, Config())
        assert warnings == []


class TestExtractTextBlocks:
    def test_extracts_text_from_page_dict(self) -> None:
        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [50, 50, 400, 70],
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Hello world",
                                    "font": "Helvetica",
                                    "size": 12.0,
                                    "flags": 0,
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        blocks = PDFParser._extract_text_blocks(mock_fitz_page)
        assert len(blocks) == 1
        assert "Hello world" in blocks[0].text
        assert blocks[0].font_info is not None
        assert blocks[0].font_info.size == 12.0

    def test_skips_non_text_blocks(self) -> None:
        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = {
            "blocks": [{"type": 1, "bbox": [0, 0, 100, 100]}]  # type 1 = image block
        }
        blocks = PDFParser._extract_text_blocks(mock_fitz_page)
        assert blocks == []

    def test_skips_empty_text(self) -> None:
        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [0, 0, 100, 20],
                    "lines": [{"spans": [{"text": "   ", "font": "Arial", "size": 10.0, "flags": 0}]}],
                }
            ]
        }
        blocks = PDFParser._extract_text_blocks(mock_fitz_page)
        assert blocks == []

    def test_detects_bold_font_by_name(self) -> None:
        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [0, 0, 100, 20],
                    "lines": [
                        {"spans": [{"text": "Bold", "font": "Helvetica-Bold", "size": 12.0, "flags": 0}]}
                    ],
                }
            ]
        }
        blocks = PDFParser._extract_text_blocks(mock_fitz_page)
        assert blocks[0].font_info.weight == "bold"


class TestPDFParserProcessWithRealPDF:
    def test_process_extracts_pages(self, tmp_path: Path) -> None:
        pytest.importorskip("fitz")
        import fitz

        pdf_path = tmp_path / "test.pdf"
        doc_fitz = fitz.open()
        page = doc_fitz.new_page(width=595, height=842)
        page.insert_text((72, 100), "Hello World", fontsize=12)
        doc_fitz.save(str(pdf_path))
        doc_fitz.close()

        doc = _empty_doc(tmp_path)
        result = PDFParser(pdf_path=pdf_path).process(doc, Config())
        assert len(result.pages) == 1

    def test_process_sets_metadata(self, tmp_path: Path) -> None:
        pytest.importorskip("fitz")
        import fitz

        pdf_path = tmp_path / "meta.pdf"
        doc_fitz = fitz.open()
        doc_fitz.new_page(width=595, height=842)
        doc_fitz.set_metadata({"title": "Test Title", "author": "Test Author"})
        doc_fitz.save(str(pdf_path))
        doc_fitz.close()

        doc = _empty_doc(tmp_path)
        result = PDFParser(pdf_path=pdf_path).process(doc, Config())
        assert result.metadata.title == "Test Title"
        assert result.metadata.author == "Test Author"

    def test_process_extracts_text_elements(self, tmp_path: Path) -> None:
        pytest.importorskip("fitz")
        import fitz

        pdf_path = tmp_path / "text.pdf"
        doc_fitz = fitz.open()
        page = doc_fitz.new_page(width=595, height=842)
        page.insert_text((72, 100), "Extractable text here", fontsize=12)
        doc_fitz.save(str(pdf_path))
        doc_fitz.close()

        doc = _empty_doc(tmp_path)
        result = PDFParser(pdf_path=pdf_path).process(doc, Config())
        text_elements = result.get_all_elements()
        texts = [getattr(el, "text", "") for el in text_elements]
        assert any("Extractable" in t for t in texts)
