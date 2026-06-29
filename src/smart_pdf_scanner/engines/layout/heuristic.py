"""Heuristic layout engine — rule-based fallback.

Classifies document elements using font-size thresholds, spatial position,
and bounding-box geometry rather than a trained model. Used when
LayoutParser is unavailable or returns low-confidence detections
(Requirement 3: Layout Analysis).

No external ML dependencies: relies only on the page's pre-parsed elements
and the bbox utilities from Phase 2.
"""

from __future__ import annotations

import logging
from typing import List

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.models.config import LayoutConfig
from smart_pdf_scanner.models.elements import (
    Element,
    ElementType,
    FontInfo,
    Heading,
)
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.utils.text_utils import looks_like_heading

__all__ = ["HeuristicEngine"]

logger = logging.getLogger(__name__)

# Elements whose bounding-box width is narrower than this fraction of the
# page width are unlikely to be full-width text blocks.
_NARROW_RATIO = 0.25

# Font-size ratio relative to the median body font at which a text block is
# promoted to a heading.
_HEADING_SIZE_RATIO = 1.2

# High confidence assigned to all heuristic detections (no model uncertainty).
_CONFIDENCE = 0.75


class HeuristicEngine(LayoutEngine):
    """Rule-based layout engine that reclassifies pre-parsed page elements.

    The engine operates in two passes:

    1. **Median font size estimation** — computes the median font size across
       all :class:`~smart_pdf_scanner.models.elements.TextBlock` elements to
       establish a baseline for heading detection.
    2. **Classification** — each element is reclassified as ``HEADING`` if its
       font size exceeds the median by :attr:`heading_size_ratio`, or if the
       text passes the :func:`~smart_pdf_scanner.utils.text_utils.looks_like_heading`
       heuristic.  All other text elements remain ``TEXT_BLOCK``.  Non-text
       elements (tables, images) are passed through unchanged.

    Args:
        heading_size_ratio: Font-size multiplier threshold for heading
            promotion (default 1.2 × median body size).
    """

    def __init__(self, *, heading_size_ratio: float = _HEADING_SIZE_RATIO) -> None:
        self._heading_ratio = heading_size_ratio

    # ------------------------------------------------------------------
    # LayoutEngine interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "heuristic"

    def detect_layout(self, page: Page, config: LayoutConfig) -> List[Element]:
        """Reclassify *page* elements using heuristic rules.

        Args:
            page: Page whose elements were populated by the PDF parser stage.
            config: Active layout configuration (confidence threshold used
                by the caller, not internally).

        Returns:
            Reclassified element list.  Each returned element has
            ``confidence`` set to :data:`_CONFIDENCE` (0.75).
        """
        if not page.elements:
            return []

        median_size = self._median_font_size(page.elements)
        result: List[Element] = []

        for el in page.elements:
            result.append(self._reclassify(el, median_size, page))

        return result

    def get_confidence(self, element: Element) -> float:
        """Return ``element.confidence`` (always :data:`_CONFIDENCE` for this engine)."""
        return element.confidence

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reclassify(
        self, element: Element, median_size: float, page: Page
    ) -> Element:
        """Return a (possibly reclassified) copy of *element*."""
        # Pass non-text elements through unchanged, just update confidence.
        if element.element_type not in (ElementType.TEXT_BLOCK, ElementType.HEADING):
            element.confidence = _CONFIDENCE
            return element

        text = getattr(element, "text", "") or ""
        font_info: FontInfo | None = getattr(element, "font_info", None)
        font_size: float = font_info.size if font_info else 0.0

        is_heading = (
            (median_size > 0 and font_size >= median_size * self._heading_ratio)
            or looks_like_heading(text)
        )

        if is_heading and element.element_type != ElementType.HEADING:
            level = self._estimate_level(font_size, median_size)
            return Heading(
                element_id=element.element_id,
                element_type=ElementType.HEADING,
                bbox=element.bbox,
                page_number=element.page_number,
                confidence=_CONFIDENCE,
                text=text,
                font_info=font_info,
                level=level,
            )

        element.confidence = _CONFIDENCE
        return element

    def _estimate_level(self, font_size: float, median_size: float) -> int:
        """Map relative font size to a heading level (1–6)."""
        if median_size <= 0:
            return 2
        ratio = font_size / median_size
        if ratio >= 2.0:
            return 1
        if ratio >= 1.6:
            return 2
        if ratio >= 1.4:
            return 3
        if ratio >= 1.2:
            return 4
        return 5

    @staticmethod
    def _median_font_size(elements: List[Element]) -> float:
        """Compute median font size across text elements, or 0 if unavailable."""
        sizes: List[float] = []
        for el in elements:
            font_info: FontInfo | None = getattr(el, "font_info", None)
            if font_info and font_info.size > 0:
                sizes.append(font_info.size)
        if not sizes:
            return 0.0
        sizes.sort()
        mid = len(sizes) // 2
        if len(sizes) % 2 == 0:
            return (sizes[mid - 1] + sizes[mid]) / 2
        return sizes[mid]
