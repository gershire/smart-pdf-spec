"""Unit tests for ConfigManager (task 1.6)."""

from pathlib import Path

import pytest

from smart_pdf_scanner.core.config import ConfigManager
from smart_pdf_scanner.models.config import Config, ProcessingMode

YAML_CONTENT = """
processing:
  mode: fast
  max_workers: 7
ocr:
  engine: easyocr
  languages:
    - eng
    - fra
  confidence_threshold: 0.5
llm:
  provider: null
logging:
  level: DEBUG
  format: text
"""


def test_load_defaults() -> None:
    config = ConfigManager.load()
    assert config == Config()


def test_load_from_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(YAML_CONTENT, encoding="utf-8")
    config = ConfigManager.load(config_path=path)
    assert config.processing_mode is ProcessingMode.FAST
    assert config.max_workers == 7
    assert config.ocr_engine == "easyocr"
    assert config.ocr_languages == ["eng", "fra"]
    assert config.ocr_confidence_threshold == 0.5
    assert config.llm_provider is None
    assert config.log_level == "DEBUG"
    assert config.log_format == "text"


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ConfigManager.load(config_path=tmp_path / "nope.yaml")


def test_overrides_take_precedence_over_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(YAML_CONTENT, encoding="utf-8")
    config = ConfigManager.load(config_path=path, overrides={"max_workers": 2})
    assert config.max_workers == 2


def test_env_overrides_file_and_is_overridden_by_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(YAML_CONTENT, encoding="utf-8")
    monkeypatch.setenv("SMART_PDF_MAX_WORKERS", "5")
    monkeypatch.setenv("SMART_PDF_OCR_LANGUAGES", "eng,deu,spa")

    env_config = ConfigManager.load(config_path=path)
    assert env_config.max_workers == 5  # env beats file (7)
    assert env_config.ocr_languages == ["eng", "deu", "spa"]

    override_config = ConfigManager.load(config_path=path, overrides={"max_workers": 1})
    assert override_config.max_workers == 1  # overrides beat env


def test_env_ignores_unknown_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_PDF_NOT_A_FIELD", "x")
    config = ConfigManager.load()
    assert config == Config()


def test_validate_clean_config() -> None:
    assert ConfigManager.validate(Config()) == []


def test_validate_reports_empty_stages() -> None:
    errors = ConfigManager.validate(Config(enabled_stages=[]))
    assert any("at least one stage" in e for e in errors)


def test_validate_reports_unknown_stage() -> None:
    errors = ConfigManager.validate(Config(enabled_stages=["pdf_parser", "bogus_stage"]))
    assert any("unknown stages" in e for e in errors)


def test_get_preset_fast() -> None:
    config = ConfigManager.get_preset(ProcessingMode.FAST)
    assert config.processing_mode is ProcessingMode.FAST
    assert config.llm_provider is None
    assert "semantic_enhancer" not in config.enabled_stages


def test_get_preset_balanced_matches_defaults() -> None:
    assert ConfigManager.get_preset(ProcessingMode.BALANCED) == Config()


def test_get_preset_high_fidelity() -> None:
    config = ConfigManager.get_preset(ProcessingMode.HIGH_FIDELITY)
    assert config.processing_mode is ProcessingMode.HIGH_FIDELITY
    assert config.export_tables_csv is True
    assert config.ocr_confidence_threshold == 0.85
