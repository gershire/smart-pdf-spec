"""Configuration models for the PDF processing pipeline.

Defines the pipeline :class:`Config` together with the processing-mode
enumeration and the per-component configuration models (Requirement 10). All
models use Pydantic for validation; numeric thresholds and counts carry
constraints so invalid configuration is rejected on construction.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProcessingMode(str, Enum):
    """Preset processing modes trading speed against fidelity."""

    FAST = "fast"
    BALANCED = "balanced"
    HIGH_FIDELITY = "high_fidelity"


def _default_stages() -> list[str]:
    """Return the default ordered list of enabled processing stages."""
    return [
        "pdf_parser",
        "layout_analyzer",
        "ocr_processor",
        "structure_recognizer",
        "table_processor",
        "image_processor",
        "semantic_enhancer",
        "markdown_generator",
    ]


class Config(BaseModel):
    """Top-level pipeline configuration.

    The defaults mirror ``config/default.yaml`` and correspond to the
    ``balanced`` processing mode.
    """

    # General
    processing_mode: ProcessingMode = ProcessingMode.BALANCED
    max_file_size_mb: int = Field(default=150, ge=1)

    # Stages
    enabled_stages: list[str] = Field(default_factory=_default_stages)

    # OCR
    ocr_engine: str = "tesseract"
    ocr_languages: list[str] = Field(default_factory=lambda: ["eng"])
    ocr_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # Layout
    layout_engine: str = "layoutparser"
    layout_model: str = "lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config"
    layout_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # LLM
    llm_provider: str | None = "openai"
    llm_model: str = "gpt-4-turbo"
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    # Output
    output_format: str = "markdown"
    include_page_numbers: bool = True
    export_tables_csv: bool = False

    # Performance
    parallel_pages: bool = False
    max_workers: int = Field(default=4, ge=1)
    cache_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"


class OCRConfig(BaseModel):
    """OCR-specific configuration.

    Attributes:
        engine: OCR engine identifier.
        languages: Languages to recognize.
        confidence_threshold: Minimum acceptable OCR confidence.
        preprocess: Whether to preprocess images before OCR.
    """

    engine: str
    languages: list[str]
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    preprocess: bool = True


class LayoutConfig(BaseModel):
    """Layout-analysis-specific configuration.

    Attributes:
        engine: Layout engine identifier.
        model: Layout model identifier.
        confidence_threshold: Minimum acceptable detection confidence.
    """

    engine: str
    model: str
    confidence_threshold: float = Field(ge=0.0, le=1.0)


class LLMConfig(BaseModel):
    """LLM-provider-specific configuration.

    Attributes:
        provider: LLM provider identifier.
        model: Model name.
        max_tokens: Maximum tokens per request.
        temperature: Sampling temperature.
        api_key: Optional API key (sourced from the environment when omitted).
    """

    provider: str
    model: str
    max_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0.0, le=2.0)
    api_key: str | None = None
