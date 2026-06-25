"""LayoutAnalyzer stage — layout detection and element classification.

Takes a document whose pages have been populated by the PDFParser stage and
runs a pluggable :class:`~smart_pdf_scanner.engines.layout.base.LayoutEngine`
to detect and classify layout elements.  Falls back to a secondary engine
when primary detections fall below the configured confidence threshold
(Requirement 3: Layout Analysis).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
from smart_pdf_scanner.models.config import Config, LayoutConfig
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import Element
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning

__all__ = ["LayoutAnalyzer"]

logger = logging.getLogger(__name__)


class LayoutAnalyzer(ProcessingStage):
    """Pipeline stage that detects and classifies document layout elements.

    The stage drives a primary :class:`~smart_pdf_scanner.engines.layout.base.LayoutEngine`
    and, when element confidence falls below ``config.layout_confidence_threshold``,
    replaces low-confidence results with detections from an optional fallback
    engine (defaults to :class:`~smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine`).

    Args:
        primary_engine: The primary layout detection engine.
        fallback_engine: Secondary engine used when primary confidence is low.
            Defaults to :class:`~smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine`.
    """

    def __init__(
        self,
        primary_engine: LayoutEngine,
        fallback_engine: Optional[LayoutEngine] = None,
    ) -> None:
        self._primary = primary_engine
        self._fallback = fallback_engine or HeuristicEngine()

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "layout_analyzer"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if not document.pages:
            warnings.append(
                ValidationWarning(
                    code="no_pages",
                    message="LayoutAnalyzer received a document with no pages.",
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Detect layout on every page and update page elements.

        Args:
            document: Document whose pages will have their elements
                replaced by the engine's detections.
            config: Active pipeline configuration.

        Returns:
            The document with classified elements on each page.
        """
        layout_cfg = LayoutConfig(
            engine=config.layout_engine,
            model=config.layout_model,
            confidence_threshold=config.layout_confidence_threshold,
        )
        for page in document.pages:
            elements = self._analyze_page(page, layout_cfg)
            page.elements = elements  # type: ignore[assignment]
            logger.debug(
                "Page %d: %d elements detected by %s",
                page.page_number,
                len(elements),
                self._primary.name,
            )
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _analyze_page(self, page: Page, config: LayoutConfig) -> List[Element]:
        """Run layout detection on a single page with optional fallback."""
        try:
            elements = self._primary.detect_layout(page, config)
        except Exception as exc:
            logger.warning(
                "Primary layout engine '%s' failed on page %d: %s — using fallback",
                self._primary.name,
                page.page_number,
                exc,
            )
            elements = []

        low_confidence = [
            el for el in elements
            if self._primary.get_confidence(el) < config.confidence_threshold
        ]

        if not elements or len(low_confidence) > len(elements) / 2:
            logger.debug(
                "Page %d: falling back to '%s' (low confidence)",
                page.page_number,
                self._fallback.name,
            )
            try:
                elements = self._fallback.detect_layout(page, config)
            except Exception as exc:
                logger.warning(
                    "Fallback layout engine '%s' failed on page %d: %s",
                    self._fallback.name,
                    page.page_number,
                    exc,
                )
                # Return whatever the primary produced (even if empty)

        return elements
