"""Unit tests for OCRProcessor stage (task 7.4)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image as PILImage

from smart_pdf_scanner.engines.ocr.base import OCRResult
from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, Image, ImageType, TextBlock
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.ocr_processor import OCRProcessor


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_ocr_result(text: str = "text", confidence: float = 0.9) -> OCRResult:
    return OCRResult(text=text, confidence=confidence, engine_name="mock")


def _make_page(is_image_based: bool = False, elements=None) -> Page:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    page.is_image_based = is_image_based
    if elements:
        for el in elements:
            page.add_element(el)
    return page


def _text_block() -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
        page_number=0,
        text="existing text",
    )


def _make_doc(pages=None, pdf_path: Path | None = None) -> Document:
    doc = Document(
        metadata=DocumentMetadata(page_count=len(pages or []), file_size_bytes=0),
        assets_folder=Path("/tmp/assets"),
    )
    for page in (pages or []):
        doc.add_page(page)
    if pdf_path:
        doc._pdf_path = pdf_path  # type: ignore[attr-defined]
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOCRProcessorName:
    def test_name(self) -> None:
        mock_engine = MagicMock()
        assert OCRProcessor(primary_engine=mock_engine).name == "ocr_processor"


class TestOCRProcessorValidate:
    def test_no_pages_emits_warning(self) -> None:
        mock_engine = MagicMock()
        doc = _make_doc(pages=[])
        warnings = OCRProcessor(primary_engine=mock_engine).validate(doc, Config())
        assert any(w.code == "no_pages" for w in warnings)

    def test_with_pages_no_warnings(self) -> None:
        mock_engine = MagicMock()
        doc = _make_doc(pages=[_make_page()])
        assert OCRProcessor(primary_engine=mock_engine).validate(doc, Config()) == []


class TestOCRProcessorHasText:
    def test_page_with_text_block_has_text(self) -> None:
        page = _make_page(elements=[_text_block()])
        assert OCRProcessor._has_text(page) is True

    def test_empty_page_has_no_text(self) -> None:
        page = _make_page()
        assert OCRProcessor._has_text(page) is False


class TestRunWithFallback:
    def test_primary_used_when_confident(self) -> None:
        primary = MagicMock()
        primary.extract_text.return_value = _make_ocr_result("primary text", 0.95)
        fallback = MagicMock()
        processor = OCRProcessor(primary_engine=primary, fallback_engine=fallback)
        img = PILImage.new("RGB", (200, 100))
        from smart_pdf_scanner.models.config import OCRConfig
        cfg = OCRConfig(engine="mock", languages=["eng"], confidence_threshold=0.7, preprocess=False)
        result = processor._run_with_fallback(img, cfg)
        assert result.text == "primary text"
        assert not fallback.extract_text.called

    def test_fallback_used_on_low_confidence(self) -> None:
        primary = MagicMock()
        primary.extract_text.return_value = _make_ocr_result("weak", 0.3)
        fallback = MagicMock()
        fallback.extract_text.return_value = _make_ocr_result("strong", 0.9)
        processor = OCRProcessor(primary_engine=primary, fallback_engine=fallback)
        img = PILImage.new("RGB", (200, 100))
        from smart_pdf_scanner.models.config import OCRConfig
        cfg = OCRConfig(engine="mock", languages=["eng"], confidence_threshold=0.7, preprocess=False)
        result = processor._run_with_fallback(img, cfg)
        assert result.text == "strong"

    def test_primary_kept_when_fallback_is_worse(self) -> None:
        primary = MagicMock()
        primary.extract_text.return_value = _make_ocr_result("ok", 0.4)
        fallback = MagicMock()
        fallback.extract_text.return_value = _make_ocr_result("worse", 0.2)
        processor = OCRProcessor(primary_engine=primary, fallback_engine=fallback)
        img = PILImage.new("RGB", (200, 100))
        from smart_pdf_scanner.models.config import OCRConfig
        cfg = OCRConfig(engine="mock", languages=["eng"], confidence_threshold=0.7, preprocess=False)
        result = processor._run_with_fallback(img, cfg)
        assert result.text == "ok"

    def test_no_fallback_primary_always_returned(self) -> None:
        primary = MagicMock()
        primary.extract_text.return_value = _make_ocr_result("primary", 0.1)
        processor = OCRProcessor(primary_engine=primary, fallback_engine=None)
        img = PILImage.new("RGB", (200, 100))
        from smart_pdf_scanner.models.config import OCRConfig
        cfg = OCRConfig(engine="mock", languages=["eng"], confidence_threshold=0.7, preprocess=False)
        result = processor._run_with_fallback(img, cfg)
        assert result.text == "primary"


class TestOCRProcessorProcess:
    def test_image_based_page_gets_text_block_added(self, tmp_path: Path) -> None:
        page = _make_page(is_image_based=True)
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 dummy")

        mock_engine = MagicMock()
        mock_engine.extract_text.return_value = _make_ocr_result("OCR text", 0.9)

        from unittest.mock import patch
        with patch.object(OCRProcessor, "_render_page", return_value=PILImage.new("RGB", (595, 842))):
            doc = _make_doc(pages=[page], pdf_path=pdf)
            result = OCRProcessor(primary_engine=mock_engine).process(doc, Config())

        text_blocks = [
            el for el in result.pages[0].elements
            if el.element_type == ElementType.TEXT_BLOCK
        ]
        assert len(text_blocks) == 1
        assert text_blocks[0].text == "OCR text"

    def test_page_with_text_skips_page_ocr(self) -> None:
        page = _make_page(elements=[_text_block()])
        mock_engine = MagicMock()

        from unittest.mock import patch
        with patch.object(OCRProcessor, "_ocr_page") as mock_ocr_page:
            doc = _make_doc(pages=[page])
            OCRProcessor(primary_engine=mock_engine).process(doc, Config())
            assert not mock_ocr_page.called

    def test_image_elements_get_ocr_text(self, tmp_path: Path) -> None:
        img_file = tmp_path / "img.png"
        PILImage.new("RGB", (200, 100), "white").save(str(img_file))
        img_el = Image(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.IMAGE,
            bbox=BoundingBox(x0=50, y0=50, x1=250, y1=150),
            page_number=0,
            image_type=ImageType.PHOTOGRAPH,
            image_path=img_file,
            description="",
        )
        # Page has text so _ocr_page won't run; _ocr_images_on_page will
        page = _make_page(elements=[_text_block(), img_el])
        mock_engine = MagicMock()
        mock_engine.extract_text.return_value = _make_ocr_result("image text", 0.85)
        doc = _make_doc(pages=[page])
        OCRProcessor(primary_engine=mock_engine).process(doc, Config())
        assert getattr(img_el, "ocr_text", None) == "image text"
