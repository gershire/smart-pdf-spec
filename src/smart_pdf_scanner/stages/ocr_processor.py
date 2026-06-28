"""OCRProcessor stage — OCR on image-based pages and image elements.

Runs a pluggable :class:`~smart_pdf_scanner.engines.ocr.base.OCREngine` on
pages that have no extractable text layer, with automatic fallback to a
secondary engine when the primary confidence falls below the configured
threshold.  Also runs OCR on
:class:`~smart_pdf_scanner.models.elements.Image` elements to extract
embedded text (Requirement 4: OCR Processing).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image as PILImage

from smart_pdf_scanner.engines.ocr.base import OCREngine, OCRResult
from smart_pdf_scanner.models.config import Config, OCRConfig
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import ElementType, Image, TextBlock
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning
from smart_pdf_scanner.utils.image_utils import preprocess_for_ocr

__all__ = ["OCRProcessor"]

logger = logging.getLogger(__name__)

# Render resolution used when converting PDF pages to images for OCR (dpi).
_PAGE_DPI = 150


class OCRProcessor(ProcessingStage):
    """Pipeline stage that applies OCR to image-based pages and image elements.

    The stage skips pages that already have a text layer (i.e.
    ``page.is_image_based`` is ``False`` and the page already has TextBlock
    elements).  For image-based pages it renders the page to a PIL image at
    :data:`_PAGE_DPI` and runs the OCR engine.

    When primary OCR confidence falls below ``config.ocr_confidence_threshold``
    the fallback engine is invoked instead.

    Args:
        primary_engine: Primary OCR engine.
        fallback_engine: Secondary engine used on low confidence results.
    """

    def __init__(
        self,
        primary_engine: OCREngine,
        fallback_engine: Optional[OCREngine] = None,
    ) -> None:
        self._primary = primary_engine
        self._fallback = fallback_engine

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "ocr_processor"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if not document.pages:
            warnings.append(
                ValidationWarning(
                    code="no_pages",
                    message="OCRProcessor received a document with no pages.",
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Run OCR on image-based pages and embedded image elements.

        Args:
            document: Document to process.
            config: Active pipeline configuration.

        Returns:
            Document with OCR text added to image-based pages and images.
        """
        ocr_cfg = OCRConfig(
            engine=config.ocr_engine,
            languages=config.ocr_languages,
            confidence_threshold=config.ocr_confidence_threshold,
            preprocess=True,
        )
        for page in document.pages:
            if page.is_image_based or not self._has_text(page):
                self._ocr_page(page, document, ocr_cfg)
            else:
                self._ocr_images_on_page(page, ocr_cfg)
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ocr_page(self, page: Page, document: Document, config: OCRConfig) -> None:
        """Render a full page to image and run OCR, adding results to the page."""
        img = self._render_page(document, page.page_number)
        if img is None:
            logger.debug("Could not render page %d for OCR", page.page_number)
            return

        result = self._run_with_fallback(img, config)
        page.ocr_confidence = result.confidence
        if result.text:
            import uuid
            from smart_pdf_scanner.models.elements import BoundingBox
            page.add_element(
                TextBlock(
                    element_id=str(uuid.uuid4()),
                    element_type=ElementType.TEXT_BLOCK,
                    bbox=BoundingBox(
                        x0=0,
                        y0=0,
                        x1=page.dimensions.width,
                        y1=page.dimensions.height,
                    ),
                    page_number=page.page_number,
                    text=result.text,
                    ocr_confidence=result.confidence,
                )
            )
            logger.debug(
                "Page %d OCR: %.2f confidence, %d chars",
                page.page_number,
                result.confidence,
                len(result.text),
            )

    def _ocr_images_on_page(self, page: Page, config: OCRConfig) -> None:
        """Run OCR on Image elements that have a file_path and store the text."""
        for el in page.elements:
            if not isinstance(el, Image):
                continue
            file_path: Path | None = getattr(el, "image_path", None)
            if not file_path or not file_path.exists():
                continue
            try:
                pil_img = PILImage.open(file_path).convert("RGB")
            except Exception as exc:
                logger.debug("Cannot open image %s: %s", file_path, exc)
                continue
            result = self._run_with_fallback(pil_img, config)
            el.ocr_text = result.text  # type: ignore[attr-defined]

    def _run_with_fallback(self, image: PILImage.Image, config: OCRConfig) -> OCRResult:
        """Run primary OCR; fall back to secondary on low confidence."""
        if config.preprocess:
            try:
                image = preprocess_for_ocr(image)
            except Exception as exc:
                logger.debug("Image preprocessing failed: %s", exc)

        result = self._primary.extract_text(image, config)
        if (
            self._fallback is not None
            and result.confidence < config.confidence_threshold
        ):
            logger.debug(
                "Primary OCR confidence %.2f < %.2f, trying fallback",
                result.confidence,
                config.confidence_threshold,
            )
            fallback_result = self._fallback.extract_text(image, config)
            if fallback_result.confidence > result.confidence:
                return fallback_result
        return result

    @staticmethod
    def _has_text(page: Page) -> bool:
        return any(
            el.element_type == ElementType.TEXT_BLOCK for el in page.elements
        )

    @staticmethod
    def _render_page(document: Document, page_number: int) -> PILImage.Image | None:
        """Render a PDF page to PIL image using PyMuPDF."""
        try:
            import fitz

            pdf_path = getattr(document, "_pdf_path", None)
            if not pdf_path:
                return None
            doc = fitz.open(str(pdf_path))
            try:
                fitz_page = doc[page_number]
                mat = fitz.Matrix(_PAGE_DPI / 72, _PAGE_DPI / 72)
                pix = fitz_page.get_pixmap(matrix=mat, alpha=False)
                from io import BytesIO
                buf = BytesIO(pix.tobytes("png"))
                return PILImage.open(buf).convert("RGB")
            finally:
                doc.close()
        except Exception as exc:
            logger.debug("Page render failed (page %d): %s", page_number, exc)
            return None
