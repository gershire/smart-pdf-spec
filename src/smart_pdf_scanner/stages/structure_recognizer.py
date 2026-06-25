"""StructureRecognizer stage — heading hierarchy and reading order.

Promotes :class:`~smart_pdf_scanner.models.elements.TextBlock` elements to
:class:`~smart_pdf_scanner.models.elements.Heading` based on font-size
analysis, builds the H1–H6 heading hierarchy, determines the logical reading
order of all elements, and links any existing table-of-contents entries to the
corresponding headings (Requirement 5: Structure Recognition).
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    AnyElement,
    Element,
    ElementType,
    FontInfo,
    Heading,
    TextBlock,
)
from smart_pdf_scanner.models.structure import DocumentStructure, TableOfContents, TOCEntry
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning
from smart_pdf_scanner.utils.text_utils import looks_like_heading

__all__ = ["StructureRecognizer"]

logger = logging.getLogger(__name__)

_HEADING_SIZE_RATIO = 1.2


class StructureRecognizer(ProcessingStage):
    """Pipeline stage that identifies document structure.

    Operates in four passes:
    1. Estimate the median body font size across all text blocks.
    2. Promote eligible text blocks to :class:`~smart_pdf_scanner.models.elements.Heading`.
    3. Build reading order from top-left → bottom-right spatial sort.
    4. Populate :attr:`~smart_pdf_scanner.models.document.Document.structure`.

    Args:
        heading_size_ratio: Font-size ratio relative to the median body size
            at which a text block is promoted to a heading (default 1.2×).
    """

    def __init__(self, *, heading_size_ratio: float = _HEADING_SIZE_RATIO) -> None:
        self._heading_ratio = heading_size_ratio

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "structure_recognizer"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if not document.pages:
            warnings.append(
                ValidationWarning(
                    code="no_pages",
                    message="StructureRecognizer received a document with no pages.",
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Identify headings, build hierarchy, and set reading order.

        Args:
            document: Document with layout-classified pages.
            config: Active pipeline configuration.

        Returns:
            Document with ``structure`` populated.
        """
        all_elements: List[AnyElement] = []
        for page in document.pages:
            all_elements.extend(page.elements)

        median_size = self._median_font_size(all_elements)
        logger.debug("Median body font size: %.1f pt", median_size)

        # Pass 1: promote text blocks to headings in place on each page
        headings: List[Heading] = []
        for page in document.pages:
            new_elements: List[AnyElement] = []
            for el in page.elements:
                promoted = self._maybe_promote(el, median_size)
                new_elements.append(promoted)
                if isinstance(promoted, Heading):
                    headings.append(promoted)
            page.elements = new_elements  # type: ignore[assignment]

        # Pass 2: determine reading order (spatial top-left sort)
        reading_order = self._determine_reading_order(document)

        # Pass 3: build TOC from extracted headings
        toc = self._build_toc(headings)

        document.structure = DocumentStructure(
            headings=headings,
            toc=toc,
            reading_order=reading_order,
        )
        logger.info(
            "StructureRecognizer: %d headings, %d reading-order entries",
            len(headings),
            len(reading_order),
        )
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _maybe_promote(self, element: AnyElement, median_size: float) -> AnyElement:
        """Return a Heading if element qualifies, otherwise return unchanged."""
        if element.element_type not in (ElementType.TEXT_BLOCK, ElementType.HEADING):
            return element
        text: str = getattr(element, "text", "") or ""
        if not text.strip():
            return element
        font_info: FontInfo | None = getattr(element, "font_info", None)
        font_size: float = font_info.size if font_info else 0.0

        is_heading = (
            (median_size > 0 and font_size >= median_size * self._heading_ratio)
            or looks_like_heading(text)
        )
        if not is_heading:
            return element

        level = self._estimate_level(font_size, median_size)
        return Heading(
            element_id=element.element_id,
            element_type=ElementType.HEADING,
            bbox=element.bbox,
            page_number=element.page_number,
            confidence=element.confidence,
            text=text,
            font_info=font_info,
            level=level,
        )

    def _estimate_level(self, font_size: float, median_size: float) -> int:
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
    def _median_font_size(elements: List[AnyElement]) -> float:
        sizes: List[float] = []
        for el in elements:
            fi: FontInfo | None = getattr(el, "font_info", None)
            if fi and fi.size > 0:
                sizes.append(fi.size)
        if not sizes:
            return 0.0
        sizes.sort()
        mid = len(sizes) // 2
        return sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2

    @staticmethod
    def _determine_reading_order(document: Document) -> List[str]:
        """Sort all elements top-to-bottom, left-to-right within each page."""
        ordered: List[str] = []
        for page in document.pages:
            sorted_els = sorted(
                page.elements,
                key=lambda el: (el.bbox.y0, el.bbox.x0),
            )
            ordered.extend(el.element_id for el in sorted_els)
        return ordered

    @staticmethod
    def _build_toc(headings: List[Heading]) -> TableOfContents:
        entries: List[TOCEntry] = [
            TOCEntry(
                title=h.text or "",
                page_number=h.page_number,
                level=h.level,
                linked_heading_id=h.element_id,
            )
            for h in headings
        ]
        return TableOfContents(entries=entries)
