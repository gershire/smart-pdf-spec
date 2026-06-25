"""Unit tests for engine factory classes."""

from __future__ import annotations

import pytest

from smart_pdf_scanner.engines.factories import (
    LayoutEngineFactory,
    LLMProviderFactory,
    OCREngineFactory,
)
from smart_pdf_scanner.models.config import Config
from unittest.mock import patch


# ---------------------------------------------------------------------------
# OCREngineFactory
# ---------------------------------------------------------------------------


class TestOCREngineFactory:
    def test_create_tesseract(self):
        config = Config(ocr_engine="tesseract")
        engine = OCREngineFactory.create(config)
        assert engine.name == "tesseract"

    def test_create_easyocr(self):
        config = Config(ocr_engine="easyocr", ocr_languages=["en"])
        engine = OCREngineFactory.create(config)
        assert engine.name == "easyocr"

    def test_create_unknown_raises(self):
        config = Config(ocr_engine="unknown_ocr_engine")
        with pytest.raises(ValueError, match="Unknown OCR engine"):
            OCREngineFactory.create(config)

    def test_create_fallback_returns_easyocr_for_tesseract(self):
        config = Config(ocr_engine="tesseract", ocr_languages=["en"])
        fallback = OCREngineFactory.create_fallback(config)
        assert fallback is not None
        assert fallback.name == "easyocr"

    def test_create_fallback_returns_none_when_easyocr_missing(self):
        config = Config(ocr_engine="tesseract")
        with patch(
            "smart_pdf_scanner.engines.factories._import_class",
            side_effect=ImportError("easyocr not installed"),
        ):
            fallback = OCREngineFactory.create_fallback(config)
        assert fallback is None

    def test_create_fallback_returns_none_for_non_tesseract_primary(self):
        config = Config(ocr_engine="easyocr")
        fallback = OCREngineFactory.create_fallback(config)
        assert fallback is None


# ---------------------------------------------------------------------------
# LayoutEngineFactory
# ---------------------------------------------------------------------------


class TestLayoutEngineFactory:
    def test_create_heuristic(self):
        config = Config(layout_engine="heuristic")
        engine = LayoutEngineFactory.create(config)
        assert engine.name == "heuristic"

    def test_create_layoutparser(self):
        config = Config(layout_engine="layoutparser")
        engine = LayoutEngineFactory.create(config)
        assert engine.name == "layoutparser"

    def test_create_unknown_raises(self):
        config = Config(layout_engine="nonexistent_engine")
        with pytest.raises(ValueError, match="Unknown layout engine"):
            LayoutEngineFactory.create(config)

    def test_create_fallback_always_returns_heuristic(self):
        config = Config(layout_engine="layoutparser")
        fallback = LayoutEngineFactory.create_fallback(config)
        assert fallback.name == "heuristic"


# ---------------------------------------------------------------------------
# LLMProviderFactory
# ---------------------------------------------------------------------------


class TestLLMProviderFactory:
    def test_create_returns_none_when_disabled(self):
        config = Config(llm_provider=None)
        provider = LLMProviderFactory.create(config)
        assert provider is None

    def test_create_openai(self):
        config = Config(llm_provider="openai")
        provider = LLMProviderFactory.create(config)
        assert provider is not None
        assert provider.name == "openai"

    def test_create_anthropic(self):
        config = Config(llm_provider="anthropic")
        provider = LLMProviderFactory.create(config)
        assert provider is not None
        assert provider.name == "anthropic"

    def test_create_unknown_raises(self):
        config = Config(llm_provider="nonexistent_llm")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMProviderFactory.create(config)

    def test_create_returns_none_on_import_error(self):
        config = Config(llm_provider="openai")
        with patch(
            "smart_pdf_scanner.engines.factories._import_class",
            side_effect=ImportError("openai not installed"),
        ):
            provider = LLMProviderFactory.create(config)
        assert provider is None
