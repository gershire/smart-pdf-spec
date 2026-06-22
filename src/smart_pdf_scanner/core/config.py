"""Configuration loading and validation.

The :class:`ConfigManager` builds a validated :class:`Config` from multiple
sources with a well-defined precedence (Requirement 10)::

    defaults -> YAML file -> environment variables -> explicit overrides

Environment variables are read from process environment (and an optional
``.env`` file) using the ``SMART_PDF_`` prefix; the remainder of the variable
name, lower-cased, is matched against :class:`Config` field names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from smart_pdf_scanner.models.config import Config, ProcessingMode

ENV_PREFIX = "SMART_PDF_"

# Maps nested ``config/default.yaml`` keys (dotted paths) to flat Config fields.
_YAML_KEY_MAP: dict[str, str] = {
    "processing.mode": "processing_mode",
    "processing.max_file_size_mb": "max_file_size_mb",
    "processing.parallel_pages": "parallel_pages",
    "processing.max_workers": "max_workers",
    "stages.enabled": "enabled_stages",
    "ocr.engine": "ocr_engine",
    "ocr.languages": "ocr_languages",
    "ocr.confidence_threshold": "ocr_confidence_threshold",
    "layout.engine": "layout_engine",
    "layout.model": "layout_model",
    "layout.confidence_threshold": "layout_confidence_threshold",
    "llm.provider": "llm_provider",
    "llm.model": "llm_model",
    "llm.max_tokens": "llm_max_tokens",
    "llm.temperature": "llm_temperature",
    "output.format": "output_format",
    "output.include_page_numbers": "include_page_numbers",
    "table.export_csv": "export_tables_csv",
    "cache.enabled": "cache_enabled",
    "logging.level": "log_level",
    "logging.format": "log_format",
}


class ConfigManager:
    """Loads, validates, and provides preset pipeline configurations."""

    @staticmethod
    def load(
        config_path: Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> Config:
        """Load configuration with hierarchy ``defaults -> file -> env -> overrides``.

        Args:
            config_path: Optional path to a YAML configuration file.
            overrides: Optional mapping of flat :class:`Config` field names to
                values that take highest precedence.

        Returns:
            A validated :class:`Config` instance.

        Raises:
            FileNotFoundError: If ``config_path`` is provided but does not exist.
            pydantic.ValidationError: If the merged configuration is invalid.
        """
        data: dict[str, Any] = {}

        if config_path is not None:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"Configuration file not found: {path}")
            data.update(ConfigManager._load_yaml(path))

        data.update(ConfigManager._load_env())

        if overrides:
            data.update(overrides)

        return Config(**data)

    @staticmethod
    def validate(config: Config) -> list[str]:
        """Validate a configuration and return a list of error messages.

        The list is empty when the configuration is valid. In addition to
        re-running Pydantic field validation, this performs semantic checks
        that span multiple fields.

        Args:
            config: The configuration to validate.

        Returns:
            Human-readable error messages, or an empty list when valid.
        """
        errors: list[str] = []
        try:
            Config.model_validate(config.model_dump())
        except ValidationError as exc:
            errors.extend(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )

        if not config.enabled_stages:
            errors.append("enabled_stages: at least one stage must be enabled")

        unknown = set(config.enabled_stages) - set(_KNOWN_STAGES)
        if unknown:
            errors.append(f"enabled_stages: unknown stages {sorted(unknown)}")

        return errors

    @staticmethod
    def get_preset(mode: ProcessingMode) -> Config:
        """Return a preset configuration for a processing mode.

        Args:
            mode: The processing mode to build a preset for.

        Returns:
            A :class:`Config` tuned for the requested mode.
        """
        if mode is ProcessingMode.FAST:
            return Config(
                processing_mode=ProcessingMode.FAST,
                enabled_stages=[
                    "pdf_parser",
                    "layout_analyzer",
                    "ocr_processor",
                    "table_processor",
                    "markdown_generator",
                ],
                llm_provider=None,
                parallel_pages=True,
                cache_enabled=True,
            )
        if mode is ProcessingMode.HIGH_FIDELITY:
            return Config(
                processing_mode=ProcessingMode.HIGH_FIDELITY,
                llm_provider="openai",
                ocr_confidence_threshold=0.85,
                layout_confidence_threshold=0.85,
                export_tables_csv=True,
                parallel_pages=False,
            )
        return Config(processing_mode=ProcessingMode.BALANCED)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Read a YAML config file and flatten it to Config field names."""
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Configuration file must contain a mapping: {path}")
        return ConfigManager._flatten(raw)

    @staticmethod
    def _flatten(raw: dict[str, Any]) -> dict[str, Any]:
        """Map a nested YAML mapping to flat Config field values."""
        flat: dict[str, Any] = {}
        for dotted, field in _YAML_KEY_MAP.items():
            section, _, key = dotted.partition(".")
            sub = raw.get(section)
            if isinstance(sub, dict) and key in sub:
                flat[field] = sub[key]
        return flat

    @staticmethod
    def _load_env() -> dict[str, Any]:
        """Read ``SMART_PDF_`` prefixed environment variables into Config fields."""
        import os

        load_dotenv()
        list_fields = {
            name
            for name, info in Config.model_fields.items()
            if info.annotation in (list[str], list)
        }
        env_values: dict[str, Any] = {}
        for raw_key, value in os.environ.items():
            if not raw_key.startswith(ENV_PREFIX):
                continue
            field = raw_key[len(ENV_PREFIX) :].lower()
            if field not in Config.model_fields:
                continue
            if field in list_fields:
                env_values[field] = [item.strip() for item in value.split(",") if item.strip()]
            else:
                env_values[field] = value
        return env_values


_KNOWN_STAGES = frozenset(
    {
        "pdf_parser",
        "layout_analyzer",
        "ocr_processor",
        "structure_recognizer",
        "table_processor",
        "image_processor",
        "semantic_enhancer",
        "markdown_generator",
    }
)
