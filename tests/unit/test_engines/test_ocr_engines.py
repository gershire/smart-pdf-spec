"""Unit tests for OCR engine implementations (task 7.3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage
from pydantic import ValidationError

from smart_pdf_scanner.engines.ocr.base import OCREngine, OCRResult, OCRWord
from smart_pdf_scanner.models.config import OCRConfig
from smart_pdf_scanner.models.elements import BoundingBox


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ocr_config() -> OCRConfig:
    return OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)


@pytest.fixture
def blank_image() -> PILImage.Image:
    return PILImage.new("RGB", (200, 100), color="white")


def _make_tesseract_data(
    texts: list[str],
    confs: list[int],
    line_nums: list[int] | None = None,
) -> dict:
    n = len(texts)
    return {
        "text": texts,
        "conf": [str(c) for c in confs],
        "left": list(range(0, n * 50, 50)),
        "top": [5] * n,
        "width": [40] * n,
        "height": [20] * n,
        "line_num": line_nums if line_nums else [1] * n,
    }


# ---------------------------------------------------------------------------
# Base interface / models
# ---------------------------------------------------------------------------


class TestOCRModels:
    def test_ocr_result_defaults(self) -> None:
        r = OCRResult(text="hello", confidence=0.9, engine_name="test")
        assert r.words == []
        assert r.language is None

    def test_ocr_result_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            OCRResult(text="x", confidence=1.5, engine_name="t")
        with pytest.raises(ValidationError):
            OCRResult(text="x", confidence=-0.1, engine_name="t")

    def test_ocr_word_model(self) -> None:
        word = OCRWord(
            text="hello",
            bbox=BoundingBox(x0=0, y0=0, x1=50, y1=20),
            confidence=0.95,
        )
        assert word.text == "hello"
        assert word.confidence == 0.95

    def test_ocr_engine_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            OCREngine()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# TesseractEngine
# ---------------------------------------------------------------------------


class TestTesseractEngine:
    def test_name(self) -> None:
        from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
        assert TesseractEngine().name == "tesseract"

    def test_extract_text_success(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        data = _make_tesseract_data(["Hello", "world"], [90, 85])
        with patch("pytesseract.image_to_data", return_value=data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            result = TesseractEngine().extract_text(blank_image, ocr_config)
        assert result.engine_name == "tesseract"
        assert "Hello" in result.text or "world" in result.text
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.words) == 2

    def test_extract_text_language_forwarded(
        self, blank_image: PILImage.Image
    ) -> None:
        config = OCRConfig(engine="tesseract", languages=["fra", "eng"], confidence_threshold=0.5)
        data = _make_tesseract_data(["Bonjour"], [80])
        captured: list[dict] = []

        def fake_image_to_data(img, lang, config, output_type):
            captured.append({"lang": lang})
            return data

        with patch("pytesseract.image_to_data", side_effect=fake_image_to_data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            TesseractEngine().extract_text(blank_image, config)
        assert captured[0]["lang"] == "fra+eng"

    def test_extract_text_tesseract_error_returns_empty(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        import pytesseract
        with patch("pytesseract.image_to_data", side_effect=pytesseract.TesseractError("e", "e")):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            result = TesseractEngine().extract_text(blank_image, ocr_config)
        assert result.text == ""
        assert result.confidence == 0.0

    def test_skips_invalid_conf_sentinel(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        data = _make_tesseract_data(["Good", "Bad"], [90, -1])
        with patch("pytesseract.image_to_data", return_value=data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            result = TesseractEngine().extract_text(blank_image, ocr_config)
        assert len(result.words) == 1
        assert result.words[0].text == "Good"

    def test_skips_whitespace_only_text(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        data = _make_tesseract_data(["  ", "Word"], [90, 88])
        with patch("pytesseract.image_to_data", return_value=data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            result = TesseractEngine().extract_text(blank_image, ocr_config)
        assert len(result.words) == 1
        assert result.words[0].text == "Word"

    def test_mean_confidence_empty_words(self) -> None:
        from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
        assert TesseractEngine._mean_confidence([]) == 0.0

    def test_mean_confidence_multiple_words(self) -> None:
        from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
        words = [
            OCRWord(text="a", bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10), confidence=0.8),
            OCRWord(text="b", bbox=BoundingBox(x0=20, y0=0, x1=30, y1=10), confidence=0.6),
        ]
        assert TesseractEngine._mean_confidence(words) == pytest.approx(0.7)

    def test_get_confidence(self) -> None:
        from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
        result = OCRResult(text="hi", confidence=0.85, engine_name="tesseract")
        assert TesseractEngine().get_confidence(result) == 0.85

    def test_multiline_text_preserved(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        data = _make_tesseract_data(["Line1", "Line2"], [90, 88], line_nums=[1, 2])
        with patch("pytesseract.image_to_data", return_value=data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            result = TesseractEngine().extract_text(blank_image, ocr_config)
        assert "\n" in result.text

    def test_custom_psm_passed_in_config_string(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        data = _make_tesseract_data([], [])
        captured: list[str] = []

        def fake_image_to_data(img, lang, config, output_type):
            captured.append(config)
            return data

        with patch("pytesseract.image_to_data", side_effect=fake_image_to_data):
            from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine
            TesseractEngine(page_segmentation_mode=6).extract_text(blank_image, ocr_config)
        assert "--psm 6" in captured[0]


# ---------------------------------------------------------------------------
# EasyOCREngine
# ---------------------------------------------------------------------------


class TestEasyOCREngine:
    def _mock_easyocr(self, detections: list) -> tuple[MagicMock, MagicMock]:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = detections
        mock_module = MagicMock()
        mock_module.Reader.return_value = mock_reader
        return mock_module, mock_reader

    def test_name(self) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        assert EasyOCREngine().name == "easyocr"

    def test_extract_text_success(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        detections = [([[0, 0], [60, 0], [60, 20], [0, 20]], "Hello world", 0.95)]
        mock_module, _ = self._mock_easyocr(detections)
        with patch.dict("sys.modules", {"easyocr": mock_module}):
            result = EasyOCREngine().extract_text(blank_image, ocr_config)
        assert "Hello world" in result.text
        assert result.engine_name == "easyocr"
        assert result.confidence == pytest.approx(0.95)

    def test_extract_text_multiple_words(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        detections = [
            ([[0, 0], [40, 0], [40, 20], [0, 20]], "Hello", 0.9),
            ([[50, 0], [90, 0], [90, 20], [50, 20]], "world", 0.8),
        ]
        mock_module, _ = self._mock_easyocr(detections)
        with patch.dict("sys.modules", {"easyocr": mock_module}):
            result = EasyOCREngine().extract_text(blank_image, ocr_config)
        assert result.confidence == pytest.approx(0.85)
        assert len(result.words) == 2

    def test_extract_text_easyocr_error_returns_empty(
        self, blank_image: PILImage.Image, ocr_config: OCRConfig
    ) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        mock_reader = MagicMock()
        mock_reader.readtext.side_effect = RuntimeError("EasyOCR fail")
        mock_module = MagicMock()
        mock_module.Reader.return_value = mock_reader
        with patch.dict("sys.modules", {"easyocr": mock_module}):
            result = EasyOCREngine().extract_text(blank_image, ocr_config)
        assert result.text == ""
        assert result.confidence == 0.0

    def test_parse_detections_skips_empty_text(self) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        raw = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "", 0.9),
            ([[60, 0], [110, 0], [110, 20], [60, 20]], "Word", 0.8),
        ]
        words = EasyOCREngine._parse_detections(raw)
        assert len(words) == 1
        assert words[0].text == "Word"

    def test_bbox_conversion(self) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        raw = [([[10, 20], [110, 20], [110, 70], [10, 70]], "test", 0.9)]
        words = EasyOCREngine._parse_detections(raw)
        assert words[0].bbox.x0 == pytest.approx(10.0)
        assert words[0].bbox.y0 == pytest.approx(20.0)
        assert words[0].bbox.x1 == pytest.approx(110.0)
        assert words[0].bbox.y1 == pytest.approx(70.0)

    def test_get_confidence(self) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
        result = OCRResult(text="test", confidence=0.7, engine_name="easyocr")
        assert EasyOCREngine().get_confidence(result) == 0.7

    def test_reader_reinitialised_on_language_change(
        self, blank_image: PILImage.Image
    ) -> None:
        from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine

        reader1 = MagicMock()
        reader1.readtext.return_value = []
        reader2 = MagicMock()
        reader2.readtext.return_value = []
        mock_module = MagicMock()
        mock_module.Reader.side_effect = [reader1, reader2]

        with patch.dict("sys.modules", {"easyocr": mock_module}):
            engine = EasyOCREngine(languages=["en"])
            cfg_en = OCRConfig(engine="easyocr", languages=["en"], confidence_threshold=0.5)
            cfg_fr = OCRConfig(engine="easyocr", languages=["fr"], confidence_threshold=0.5)
            engine.extract_text(blank_image, cfg_en)
            engine.extract_text(blank_image, cfg_fr)
        assert mock_module.Reader.call_count == 2
