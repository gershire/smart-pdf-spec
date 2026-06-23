"""OCR engine base interface and result model.

Defines the abstract contract that all OCR engine implementations must follow
(Requirement 4: OCR Processing) and the :class:`OCRResult` / :class:`OCRWord`
Pydantic models used to carry results between the engine layer and the
:class:`OCRProcessor` stage.

Engine implementations live in sibling modules:
- ``tesseract.py``  — primary Tesseract engine
- ``easyocr.py``    — EasyOCR fallback engine
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from PIL import Image as PILImage
from pydantic import BaseModel, Field

from smart_pdf_scanner.models.config import OCRConfig
from smart_pdf_scanner.models.elements import BoundingBox

__all__ = [
    "OCRWord",
    "OCRResult",
    "OCREngine",
]


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class OCRWord(BaseModel):
    """A single word token produced by an OCR engine.

    Attributes:
        text: The recognised word string.
        bbox: Bounding box of the word in page-image coordinates (pixels).
        confidence: Per-word confidence score in ``[0.0, 1.0]``.
    """

    text: str
    bbox: BoundingBox
    confidence: float = Field(ge=0.0, le=1.0)


class OCRResult(BaseModel):
    """Aggregated output from a single OCR engine run on one image.

    Attributes:
        text: Full extracted text (words joined with appropriate whitespace).
        confidence: Mean word-level confidence in ``[0.0, 1.0]``.  Engines
            that do not expose per-word confidence should use a single global
            estimate here.
        words: Ordered list of individual word tokens with bboxes.  May be
            empty for engines that only return full-page text.
        language: ISO 639-1 language code detected or configured (e.g.
            ``"en"``), or ``None`` if the engine did not report one.
        engine_name: Name of the engine that produced this result, for
            logging and fallback bookkeeping.
    """

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    words: List[OCRWord] = Field(default_factory=list)
    language: Optional[str] = None
    engine_name: str


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class OCREngine(ABC):
    """Abstract interface for OCR engine implementations.

    Concrete subclasses accept a PIL image, run text recognition, and return
    an :class:`OCRResult`.  The :class:`OCRProcessor` stage drives engines
    through this interface, enabling transparent primary/fallback switching.

    Implementing a new engine requires:
    1. Subclass :class:`OCREngine`.
    2. Implement :meth:`extract_text` to call the underlying library and map
       its output to an :class:`OCRResult`.
    3. Implement :meth:`get_confidence` to return the overall confidence from
       a result (usually ``result.confidence``).
    4. Expose the engine name via the :attr:`name` property.

    Example::

        class MyEngine(OCREngine):
            @property
            def name(self) -> str:
                return "my_engine"

            def extract_text(self, image, config):
                ...

            def get_confidence(self, result):
                return result.confidence
    """

    @abstractmethod
    def extract_text(self, image: PILImage.Image, config: OCRConfig) -> OCRResult:
        """Run OCR on ``image`` and return structured results.

        Args:
            image: RGB PIL image of a page or cropped region to recognise.
            config: Active OCR configuration (languages, confidence threshold,
                preprocessing flags, etc.).

        Returns:
            :class:`OCRResult` with full text, per-word tokens, and overall
            confidence.
        """

    @abstractmethod
    def get_confidence(self, result: OCRResult) -> float:
        """Return the overall confidence score for *result*.

        Engines may compute this differently (mean word confidence, global
        score, etc.).  The :class:`OCRProcessor` uses this to decide whether
        to invoke the fallback engine.

        Args:
            result: A result previously returned by :meth:`extract_text`.

        Returns:
            Confidence in ``[0.0, 1.0]``.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier used in logging and configuration."""
