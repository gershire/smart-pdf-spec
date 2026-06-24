"""EasyOCR engine implementation — fallback OCR engine.

Used when Tesseract confidence falls below the configured threshold.
EasyOCR handles handwritten text and complex scripts better than Tesseract
and supports GPU acceleration transparently.

Requires:
    pip install easyocr
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PIL import Image as PILImage

from smart_pdf_scanner.engines.ocr.base import OCREngine, OCRResult, OCRWord
from smart_pdf_scanner.models.config import OCRConfig
from smart_pdf_scanner.models.elements import BoundingBox

__all__ = ["EasyOCREngine"]

logger = logging.getLogger(__name__)


class EasyOCREngine(OCREngine):
    """OCR engine backed by EasyOCR.

    EasyOCR returns a list of ``(bbox_points, text, confidence)`` tuples.
    Each bounding box is four corner points ``[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]``
    which we convert to axis-aligned :class:`~smart_pdf_scanner.models.elements.BoundingBox`.

    The :class:`easyocr.Reader` is initialised lazily on the first call to
    :meth:`extract_text` so that importing the module is cheap even when
    EasyOCR is not used.

    Args:
        languages: ISO 639-1 language codes to load (e.g. ``["en", "fr"]``).
            Overridden at call time by ``config.languages`` if provided.
        gpu: Use GPU if ``True``, CPU otherwise. Defaults to ``False`` for
            broad compatibility.
    """

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        *,
        gpu: bool = False,
    ) -> None:
        self._init_languages = languages or ["en"]
        self._gpu = gpu
        self._reader: Optional[object] = None  # easyocr.Reader, loaded lazily

    # ------------------------------------------------------------------
    # OCREngine interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "easyocr"

    def extract_text(self, image: PILImage.Image, config: OCRConfig) -> OCRResult:
        """Run EasyOCR on *image* and return structured results.

        The reader is (re)initialised if the requested languages differ from
        the current initialisation.

        Args:
            image: RGB PIL image.
            config: Active OCR configuration; ``config.languages`` takes
                precedence over the constructor ``languages`` argument.

        Returns:
            :class:`~smart_pdf_scanner.engines.ocr.base.OCRResult` with
            word-level tokens and mean confidence.
        """
        import easyocr  # imported here to keep startup cost low

        langs = config.languages if config.languages else self._init_languages
        self._ensure_reader(easyocr, langs)

        try:
            raw = self._reader.readtext(  # type: ignore[union-attr]
                image,
                detail=1,
                paragraph=False,
            )
        except Exception as exc:
            logger.warning("EasyOCR failed: %s", exc)
            return OCRResult(text="", confidence=0.0, engine_name=self.name)

        words = self._parse_detections(raw)
        full_text = " ".join(w.text for w in words)
        confidence = self._mean_confidence(words)

        return OCRResult(
            text=full_text,
            confidence=confidence,
            words=words,
            language=langs[0] if langs else "en",
            engine_name=self.name,
        )

    def get_confidence(self, result: OCRResult) -> float:
        """Return the pre-computed mean word confidence from *result*."""
        return result.confidence

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_reader(self, easyocr_module: object, langs: List[str]) -> None:
        """(Re)initialise the reader if languages changed."""
        if self._reader is None or self._init_languages != langs:
            self._init_languages = langs
            logger.debug("Initialising EasyOCR reader for languages: %s", langs)
            self._reader = easyocr_module.Reader(langs, gpu=self._gpu)  # type: ignore[attr-defined]

    @staticmethod
    def _parse_detections(raw: list) -> List[OCRWord]:
        """Convert EasyOCR detections to :class:`OCRWord` list."""
        words: List[OCRWord] = []
        for bbox_points, text, conf in raw:
            text = str(text).strip()
            if not text:
                continue
            # bbox_points: [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            words.append(
                OCRWord(
                    text=text,
                    bbox=BoundingBox(
                        x0=float(min(xs)),
                        y0=float(min(ys)),
                        x1=float(max(xs)),
                        y1=float(max(ys)),
                    ),
                    confidence=float(conf),
                )
            )
        return words

    @staticmethod
    def _mean_confidence(words: List[OCRWord]) -> float:
        if not words:
            return 0.0
        return sum(w.confidence for w in words) / len(words)
