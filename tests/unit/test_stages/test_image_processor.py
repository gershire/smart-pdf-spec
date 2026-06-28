"""Unit tests for ImageProcessor stage (task 7.4)."""

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
from smart_pdf_scanner.stages.image_processor import ImageProcessor


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    path = tmp_path / "img.png"
    PILImage.new("RGB", (200, 100), color=(128, 128, 128)).save(str(path))
    return path


@pytest.fixture
def narrow_image_file(tmp_path: Path) -> Path:
    """Very wide image → expected to be classified as CHART."""
    path = tmp_path / "narrow.png"
    PILImage.new("RGB", (500, 100), color=(100, 100, 100)).save(str(path))
    return path


@pytest.fixture
def tall_image_file(tmp_path: Path) -> Path:
    """Very tall image → expected to be classified as PHOTO."""
    path = tmp_path / "tall.png"
    PILImage.new("RGB", (100, 500), color=(50, 50, 50)).save(str(path))
    return path


def _image_element(file_path: Path | None = None) -> Image:
    return Image(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.IMAGE,
        bbox=BoundingBox(x0=50, y0=50, x1=200, y1=200),
        page_number=0,
        image_type=ImageType.OTHER,
        image_path=file_path,
        description="",
    )


def _doc_with_image(image_el: Image, tmp_path: Path) -> Document:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    page.add_element(image_el)
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=tmp_path / "assets",
    )
    doc.add_page(page)
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestImageProcessorName:
    def test_name(self) -> None:
        assert ImageProcessor().name == "image_processor"


class TestImageProcessorValidate:
    def test_validate_returns_empty(self) -> None:
        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=Path("/tmp"),
        )
        assert ImageProcessor().validate(doc, Config()) == []


class TestClassifyImage:
    def test_wide_image_classified_as_chart(self, narrow_image_file: Path) -> None:
        img = PILImage.open(narrow_image_file)
        result = ImageProcessor().classify_image(img)
        assert result == ImageType.CHART

    def test_tall_image_classified_as_photo(self, tall_image_file: Path) -> None:
        img = PILImage.open(tall_image_file)
        result = ImageProcessor().classify_image(img)
        assert result == ImageType.PHOTOGRAPH

    def test_zero_height_returns_other(self) -> None:
        processor = ImageProcessor()
        mock_img = MagicMock()
        mock_img.size = (100, 0)
        result = processor.classify_image(mock_img)
        assert result == ImageType.OTHER


class TestExtractTextFromImage:
    def test_returns_empty_without_engine(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        config = Config()
        from smart_pdf_scanner.models.config import OCRConfig
        ocr_cfg = OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)
        result = ImageProcessor(ocr_engine=None).extract_text_from_image(img, ocr_cfg)
        assert result == ""

    def test_returns_empty_for_tiny_image(self) -> None:
        tiny = PILImage.new("RGB", (50, 50), color="white")
        from smart_pdf_scanner.models.config import OCRConfig
        ocr_cfg = OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)
        mock_engine = MagicMock()
        result = ImageProcessor(ocr_engine=mock_engine).extract_text_from_image(tiny, ocr_cfg)
        assert result == ""
        assert not mock_engine.extract_text.called

    def test_calls_ocr_engine_for_large_image(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        from smart_pdf_scanner.models.config import OCRConfig
        ocr_cfg = OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)
        mock_engine = MagicMock()
        mock_engine.extract_text.return_value = OCRResult(
            text="extracted text", confidence=0.9, engine_name="tesseract"
        )
        result = ImageProcessor(ocr_engine=mock_engine).extract_text_from_image(img, ocr_cfg)
        assert result == "extracted text"

    def test_returns_empty_on_ocr_exception(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        from smart_pdf_scanner.models.config import OCRConfig
        ocr_cfg = OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)
        mock_engine = MagicMock()
        mock_engine.extract_text.side_effect = RuntimeError("OCR crash")
        result = ImageProcessor(ocr_engine=mock_engine).extract_text_from_image(img, ocr_cfg)
        assert result == ""


class TestGenerateDescription:
    def test_basic_heuristic_description_no_llm(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        el = _image_element(image_file)
        el.image_type = ImageType.PHOTOGRAPH  # type: ignore[attr-defined]
        el.ocr_text = ""  # type: ignore[attr-defined]
        desc = ImageProcessor().generate_description(img, el, None)
        assert "photograph" in desc.lower() or "200" in desc

    def test_heuristic_description_includes_ocr_text(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        el = _image_element(image_file)
        el.image_type = ImageType.DIAGRAM  # type: ignore[attr-defined]
        el.ocr_text = "OCR extracted text"  # type: ignore[attr-defined]
        desc = ImageProcessor().generate_description(img, el, None)
        assert "OCR extracted text" in desc

    def test_llm_description_used_when_available(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        el = _image_element(image_file)
        el.image_type = ImageType.CHART  # type: ignore[attr-defined]
        el.ocr_text = ""  # type: ignore[attr-defined]
        mock_llm = MagicMock()
        mock_llm.generate_with_vision.return_value = "LLM description"
        from smart_pdf_scanner.models.config import LLMConfig
        llm_cfg = LLMConfig(provider="openai", model="gpt-4o", max_tokens=256, temperature=0.0)
        desc = ImageProcessor(llm_provider=mock_llm).generate_description(img, el, llm_cfg)
        assert desc == "LLM description"

    def test_falls_back_to_heuristic_on_llm_error(self, image_file: Path) -> None:
        img = PILImage.open(image_file)
        el = _image_element(image_file)
        el.image_type = ImageType.PHOTOGRAPH  # type: ignore[attr-defined]
        el.ocr_text = ""  # type: ignore[attr-defined]
        mock_llm = MagicMock()
        mock_llm.generate_with_vision.side_effect = RuntimeError("LLM error")
        from smart_pdf_scanner.models.config import LLMConfig
        llm_cfg = LLMConfig(provider="openai", model="gpt-4o", max_tokens=256, temperature=0.0)
        desc = ImageProcessor(llm_provider=mock_llm).generate_description(img, el, llm_cfg)
        assert desc  # should produce some description


class TestImageProcessorProcess:
    def test_process_skips_missing_file(self, tmp_path: Path) -> None:
        el = _image_element(file_path=None)
        doc = _doc_with_image(el, tmp_path)
        ImageProcessor().process(doc, Config())
        # Should not crash, element stays unchanged
        assert doc.pages[0].elements[0].element_type == ElementType.IMAGE

    def test_process_classifies_existing_image(self, tmp_path: Path, image_file: Path) -> None:
        el = _image_element(file_path=image_file)
        doc = _doc_with_image(el, tmp_path)
        ImageProcessor().process(doc, Config())
        assert el.image_type != ImageType.OTHER  # type: ignore[attr-defined]

    def test_process_sets_description(self, tmp_path: Path, image_file: Path) -> None:
        el = _image_element(file_path=image_file)
        doc = _doc_with_image(el, tmp_path)
        ImageProcessor().process(doc, Config())
        assert hasattr(el, "description")
        assert el.description  # type: ignore[attr-defined]

    def test_caption_associated_when_nearby(self, tmp_path: Path, image_file: Path) -> None:
        el = _image_element(file_path=image_file)
        caption_el = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.CAPTION,
            bbox=BoundingBox(x0=50, y0=205, x1=300, y1=220),  # just below image (y1=200)
            page_number=0,
            text="Figure 1: Test image",
        )
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        page.add_element(el)
        page.add_element(caption_el)
        doc = Document(
            metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        doc.add_page(page)
        ImageProcessor().process(doc, Config())
        assert getattr(el, "caption", None) == "Figure 1: Test image"
