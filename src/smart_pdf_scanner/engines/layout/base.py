"""Layout engine base interface.

Defines the abstract contract that all layout-detection engine implementations
must follow (Requirement 3: Layout Analysis).

Engine implementations live in sibling modules:
- ``layoutparser.py`` — LayoutParser / Detectron2 engine (primary)
- ``heuristic.py``    — rule-based heuristic engine (fallback)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from smart_pdf_scanner.models.config import LayoutConfig
from smart_pdf_scanner.models.elements import Element
from smart_pdf_scanner.models.page import Page

__all__ = ["LayoutEngine"]


class LayoutEngine(ABC):
    """Abstract interface for layout-detection engine implementations.

    A layout engine receives a :class:`~smart_pdf_scanner.models.page.Page`
    and returns an ordered list of :class:`~smart_pdf_scanner.models.elements.Element`
    objects with classified types and confidence scores.

    The :class:`LayoutAnalyzer` stage drives engines through this interface,
    calling :meth:`get_confidence` on each returned element to decide whether
    to invoke the fallback engine.

    Implementing a new engine requires:
    1. Subclass :class:`LayoutEngine`.
    2. Implement :meth:`detect_layout` to analyse the page and return
       classified elements with ``confidence`` set on each.
    3. Implement :meth:`get_confidence` (typically just ``element.confidence``).
    4. Expose a unique identifier via the :attr:`name` property.

    Example::

        class MyEngine(LayoutEngine):
            @property
            def name(self) -> str:
                return "my_engine"

            def detect_layout(self, page, config):
                ...

            def get_confidence(self, element):
                return element.confidence
    """

    @abstractmethod
    def detect_layout(self, page: Page, config: LayoutConfig) -> List[Element]:
        """Detect and classify layout elements on *page*.

        Args:
            page: The page to analyse.  May already contain raw elements
                from the PDF parser stage which the engine can reclassify,
                or the engine may produce its own element list from a
                rendered page image.
            config: Active layout configuration (engine name, model path,
                confidence threshold, etc.).

        Returns:
            Ordered list of :class:`~smart_pdf_scanner.models.elements.Element`
            objects (or subclasses) with ``element_type`` and ``confidence``
            set by the engine.
        """

    @abstractmethod
    def get_confidence(self, element: Element) -> float:
        """Return the detection confidence for *element*.

        Args:
            element: An element previously returned by :meth:`detect_layout`.

        Returns:
            Confidence score in ``[0.0, 1.0]``.  The
            :class:`LayoutAnalyzer` stage uses this to decide whether to
            fall back to a secondary engine.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier used in logging and configuration."""
