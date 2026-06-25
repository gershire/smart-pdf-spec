"""Engine factory classes for the PDF processing pipeline.

Creates OCR, layout, and LLM engine instances from configuration, handling
missing optional dependencies gracefully (Requirement 10: Configuration
Management).
"""

from __future__ import annotations

import logging
from typing import Optional

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.engines.ocr.base import OCREngine
from smart_pdf_scanner.models.config import Config

__all__ = [
    "OCREngineFactory",
    "LayoutEngineFactory",
    "LLMProviderFactory",
]

logger = logging.getLogger(__name__)

# Registry mappings: config name → dotted import path
_OCR_ENGINES: dict[str, str] = {
    "tesseract": "smart_pdf_scanner.engines.ocr.tesseract.TesseractEngine",
    "easyocr": "smart_pdf_scanner.engines.ocr.easyocr.EasyOCREngine",
}

_LAYOUT_ENGINES: dict[str, str] = {
    "layoutparser": "smart_pdf_scanner.engines.layout.layoutparser.LayoutParserEngine",
    "heuristic": "smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine",
}

_LLM_PROVIDERS: dict[str, str] = {
    "openai": "smart_pdf_scanner.engines.llm.openai.OpenAIProvider",
    "anthropic": "smart_pdf_scanner.engines.llm.anthropic.AnthropicProvider",
}


def _import_class(dotted_path: str) -> type:
    """Import and return a class from its fully qualified dotted path."""
    module_path, _, class_name = dotted_path.rpartition(".")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class OCREngineFactory:
    """Creates OCR engine instances from configuration."""

    @staticmethod
    def create(config: Config) -> OCREngine:
        """Create the primary OCR engine specified in *config*.

        Args:
            config: Active pipeline configuration.

        Returns:
            An :class:`~smart_pdf_scanner.engines.ocr.base.OCREngine` instance.

        Raises:
            ValueError: If ``config.ocr_engine`` names an unknown engine.
            ImportError: If the engine's dependencies are not installed.
        """
        engine_name = config.ocr_engine
        if engine_name not in _OCR_ENGINES:
            raise ValueError(
                f"Unknown OCR engine '{engine_name}'. "
                f"Available: {sorted(_OCR_ENGINES)}"
            )
        cls = _import_class(_OCR_ENGINES[engine_name])
        if engine_name == "tesseract":
            return cls()
        if engine_name == "easyocr":
            return cls(config.ocr_languages)
        return cls()

    @staticmethod
    def create_fallback(config: Config) -> Optional[OCREngine]:
        """Create a fallback OCR engine for low-confidence results.

        When the primary engine is Tesseract the fallback is EasyOCR (if
        available).  Returns ``None`` if no suitable fallback exists or if the
        required dependency is not installed.

        Args:
            config: Active pipeline configuration.

        Returns:
            A fallback :class:`~smart_pdf_scanner.engines.ocr.base.OCREngine`,
            or ``None``.
        """
        if config.ocr_engine == "tesseract":
            try:
                cls = _import_class(_OCR_ENGINES["easyocr"])
                return cls(config.ocr_languages)
            except ImportError:
                logger.debug("EasyOCR not installed; OCR fallback disabled")
                return None
        return None


class LayoutEngineFactory:
    """Creates layout engine instances from configuration."""

    @staticmethod
    def create(config: Config) -> LayoutEngine:
        """Create the primary layout engine specified in *config*.

        Args:
            config: Active pipeline configuration.

        Returns:
            A :class:`~smart_pdf_scanner.engines.layout.base.LayoutEngine` instance.

        Raises:
            ValueError: If ``config.layout_engine`` names an unknown engine.
            ImportError: If the engine's dependencies are not installed.
        """
        engine_name = config.layout_engine
        if engine_name not in _LAYOUT_ENGINES:
            raise ValueError(
                f"Unknown layout engine '{engine_name}'. "
                f"Available: {sorted(_LAYOUT_ENGINES)}"
            )
        cls = _import_class(_LAYOUT_ENGINES[engine_name])
        return cls()

    @staticmethod
    def create_fallback(config: Config) -> LayoutEngine:
        """Create the heuristic fallback layout engine.

        Always returns a :class:`~smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine`
        which has no external dependencies.

        Args:
            config: Active pipeline configuration (unused, kept for API consistency).

        Returns:
            A :class:`~smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine` instance.
        """
        from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine

        return HeuristicEngine()


class LLMProviderFactory:
    """Creates LLM provider instances from configuration."""

    @staticmethod
    def create(config: Config) -> Optional[LLMProvider]:
        """Create the LLM provider specified in *config*.

        Returns ``None`` when ``config.llm_provider`` is ``None`` (LLM
        enhancement disabled) or when the required dependency is not installed
        (logs a warning and continues without LLM support).

        Args:
            config: Active pipeline configuration.

        Returns:
            An :class:`~smart_pdf_scanner.engines.llm.base.LLMProvider` instance,
            or ``None`` if LLM support is disabled or unavailable.

        Raises:
            ValueError: If ``config.llm_provider`` names an unknown provider.
        """
        if config.llm_provider is None:
            return None

        provider_name = config.llm_provider
        if provider_name not in _LLM_PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider '{provider_name}'. "
                f"Available: {sorted(_LLM_PROVIDERS)}"
            )

        try:
            cls = _import_class(_LLM_PROVIDERS[provider_name])
            return cls()
        except ImportError:
            logger.warning(
                "LLM provider '%s' dependencies not installed; "
                "semantic enhancement will be disabled",
                provider_name,
            )
            return None
