"""Unit tests for configuration models (task 1.6)."""

import json

import pytest
from pydantic import ValidationError

from smart_pdf_scanner.models.config import (
    Config,
    LayoutConfig,
    LLMConfig,
    OCRConfig,
    ProcessingMode,
)


def test_processing_mode_values() -> None:
    assert {m.value for m in ProcessingMode} == {"fast", "balanced", "high_fidelity"}


def test_config_defaults() -> None:
    config = Config()
    assert config.processing_mode is ProcessingMode.BALANCED
    assert config.ocr_languages == ["eng"]
    assert "markdown_generator" in config.enabled_stages
    assert config.log_format == "json"


def test_config_threshold_bounds() -> None:
    with pytest.raises(ValidationError):
        Config(ocr_confidence_threshold=1.5)
    with pytest.raises(ValidationError):
        Config(layout_confidence_threshold=-0.1)


def test_config_max_workers_positive() -> None:
    with pytest.raises(ValidationError):
        Config(max_workers=0)


def test_config_llm_provider_optional() -> None:
    config = Config(llm_provider=None)
    assert config.llm_provider is None


def test_config_json_round_trip() -> None:
    config = Config(processing_mode=ProcessingMode.FAST, max_workers=8)
    restored = Config.model_validate(json.loads(config.model_dump_json()))
    assert restored == config


def test_ocr_config_validation() -> None:
    ocr = OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=0.7)
    assert ocr.preprocess is True
    with pytest.raises(ValidationError):
        OCRConfig(engine="tesseract", languages=["eng"], confidence_threshold=2.0)


def test_layout_config_validation() -> None:
    layout = LayoutConfig(engine="layoutparser", model="m", confidence_threshold=0.5)
    assert layout.confidence_threshold == 0.5


def test_llm_config_temperature_bounds() -> None:
    with pytest.raises(ValidationError):
        LLMConfig(provider="openai", model="gpt", max_tokens=10, temperature=3.0)
