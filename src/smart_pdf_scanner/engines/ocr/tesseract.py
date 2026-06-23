"""Tesseract OCR engine implementation.

Wraps pytesseract to provide word-level text extraction with confidence
scores for each recognised token.  Serves as the primary OCR engine
(Requirement 4) with EasyOCR as the configured fallback.

Requires:
- pytesseract Python binding (``pip install pytesseract``)
- Tesseract binary on PATH (``brew install tesseract`` / ``apt install tesseract-ocr``)
"""

from __future__ import annotations

import logging
from typing import List

import pytesseract
from PIL import Image as PILImage

from smart_pdf_scanner.engines.ocr.base import OCREngine, OCRResult, OCRWord
from smart_pdf_scanner.models.config import OCRConfig
from smart_pdf_scanner.models.elements import BoundingBox

__all__ = ["TesseractEngine"]

logger = logging.getLogger(__name__)

# pytesseract confidence sentinel: -1 means layout noise (not a real word).
_INVALID_CONF = -1
# Tesseract reports confidence as 0-100; we normalise to [0, 1].
_CONF_SCALE = 100.0


class TesseractEngine(OCREngine):
    """OCR engine backed by Tesseract 5 via pytesseract.

    Calls :func:`pytesseract.image_to_data` to obtain word-level bounding
    boxes and per-word confidence scores, then aggregates them into an
    :class:`~smart_pdf_scanner.engines.ocr.base.OCRResult`.

    The overall confidence is the mean of all valid word confidences; if no
    valid words are found the result carries ``confidence=0.0``.

    Args:
        tesseract_cmd: Optional path to the Tesseract binary.  Defaults to
            whatever pytesseract resolves on PATH.
        page_segmentation_mode: Tesseract ``--psm`` value (default 3,
            fully automatic page segmentation).  Adjust for specific layouts
            (e.g. ``psm=6`` for a single uniform block of text).
    """

    def __init__(
        self,
        *,
        tesseract_cmd: str | None = None,
        page_segmentation_mode: int = 3,
    ) -> None:
        if tesseract_cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self._psm = page_segmentation_mode

    # ------------------------------------------------------------------
    # OCREngine interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "tesseract"

    def extract_text(self, image: PILImage.Image, config: OCRConfig) -> OCRResult:
        """Run Tesseract on *image* and return structured word-level results.

        Args:
            image: RGB PIL image to recognise.
            config: Active OCR configuration supplying language codes and
                the confidence threshold (used by the caller, not here).

        Returns:
            :class:`~smart_pdf_scanner.engines.ocr.base.OCRResult` with full
            text, per-word tokens, and mean confidence.

        Raises:
            pytesseract.TesseractNotFoundError: If the Tesseract binary is
                not installed or not on PATH.
            pytesseract.TesseractError: On any Tesseract runtime failure.
        """
        lang = "+".join(config.languages) if config.languages else "eng"
        custom_config = f"--psm {self._psm}"

        try:
            data = pytesseract.image_to_data(
                image,
                lang=lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError as exc:
            logger.warning("Tesseract failed: %s", exc)
            return OCRResult(text="", confidence=0.0, engine_name=self.name)

        words = self._parse_words(data)
        full_text = self._build_text(data)
        confidence = self._mean_confidence(words)

        return OCRResult(
            text=full_text,
            confidence=confidence,
            words=words,
            language=config.languages[0] if config.languages else "eng",
            engine_name=self.name,
        )

    def get_confidence(self, result: OCRResult) -> float:
        """Return the pre-computed mean word confidence from *result*.

        Args:
            result: A result previously returned by :meth:`extract_text`.

        Returns:
            Mean word confidence in ``[0.0, 1.0]``.
        """
        return result.confidence

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_words(data: dict) -> List[OCRWord]:
        """Convert pytesseract DICT output to a list of :class:`OCRWord`."""
        words: List[OCRWord] = []
        texts = data.get("text", [])
        confs = data.get("conf", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])

        for text, conf, left, top, width, height in zip(
            texts, confs, lefts, tops, widths, heights
        ):
            conf_int = int(conf)
            if conf_int == _INVALID_CONF or not str(text).strip():
                continue
            words.append(
                OCRWord(
                    text=str(text).strip(),
                    bbox=BoundingBox(
                        x0=float(left),
                        y0=float(top),
                        x1=float(left + width),
                        y1=float(top + height),
                    ),
                    confidence=conf_int / _CONF_SCALE,
                )
            )
        return words

    @staticmethod
    def _build_text(data: dict) -> str:
        """Reconstruct full text from pytesseract DICT output.

        Preserves line breaks by inserting newlines whenever the block or
        paragraph number advances.
        """
        texts = data.get("text", [])
        confs = data.get("conf", [])
        line_nums = data.get("line_num", [])

        lines: dict[int, list[str]] = {}
        for text, conf, line in zip(texts, confs, line_nums):
            if int(conf) == _INVALID_CONF or not str(text).strip():
                continue
            lines.setdefault(line, []).append(str(text).strip())

        return "\n".join(" ".join(words) for words in lines.values() if words)

    @staticmethod
    def _mean_confidence(words: List[OCRWord]) -> float:
        """Return mean word confidence, or 0.0 for an empty word list."""
        if not words:
            return 0.0
        return sum(w.confidence for w in words) / len(words)
