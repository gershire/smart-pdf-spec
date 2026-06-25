"""ImageProcessor stage — image classification and description.

Classifies each :class:`~smart_pdf_scanner.models.elements.Image` element by
visual type, runs OCR to extract embedded text, generates a description
(basic heuristic or LLM-enhanced when an
:class:`~smart_pdf_scanner.engines.llm.base.LLMProvider` is available), and
associates nearby captions (Requirement 7: Image Processing).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image as PILImage

from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.engines.ocr.base import OCREngine
from smart_pdf_scanner.models.config import Config, LLMConfig, OCRConfig
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import ElementType, Image, ImageType
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning

__all__ = ["ImageProcessor"]

logger = logging.getLogger(__name__)

# Aspect-ratio thresholds used for basic visual classification
_WIDE_RATIO = 3.0   # width/height >= 3 → likely a chart/diagram strip
_TALL_RATIO = 0.4   # width/height <= 0.4 → likely a portrait photo

# Minimum pixel dimensions to run OCR (ignore tiny decorative images)
_MIN_OCR_PIXELS = 100


class ImageProcessor(ProcessingStage):
    """Pipeline stage that processes Image elements on each page.

    Processing steps per image element:
    1. Load the saved image file from ``element.file_path``.
    2. Classify visual type (:class:`~smart_pdf_scanner.models.elements.ImageType`).
    3. Run OCR to extract embedded text (if image is large enough).
    4. Generate a description: LLM-enhanced if a provider is supplied,
       otherwise a basic heuristic description.
    5. Find the nearest CAPTION element on the same page and link it.

    Args:
        ocr_engine: OCR engine used to extract text from images.
        llm_provider: Optional LLM provider for description generation.
            When ``None``, basic heuristic descriptions are used.
    """

    def __init__(
        self,
        ocr_engine: Optional[OCREngine] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self._ocr = ocr_engine
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "image_processor"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        return []  # no hard pre-conditions

    def process(self, document: Document, config: Config) -> Document:
        """Classify, OCR, and describe all Image elements.

        Args:
            document: Document with Image elements on pages.
            config: Active pipeline configuration.

        Returns:
            Document with Image elements enriched.
        """
        ocr_cfg = OCRConfig(
            engine=config.ocr_engine,
            languages=config.ocr_languages,
            confidence_threshold=config.ocr_confidence_threshold,
            preprocess=False,
        )
        llm_cfg = LLMConfig(
            provider=config.llm_provider or "openai",
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            temperature=config.llm_temperature,
        ) if config.llm_provider and self._llm else None

        for page in document.pages:
            self._process_page(page, ocr_cfg, llm_cfg)
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_page(
        self,
        page: Page,
        ocr_cfg: OCRConfig,
        llm_cfg: Optional[LLMConfig],
    ) -> None:
        captions = [
            el for el in page.elements if el.element_type == ElementType.CAPTION
        ]
        for el in page.elements:
            if not isinstance(el, Image):
                continue
            pil_img = self._load_image(el)
            if pil_img is None:
                continue

            el.image_type = self.classify_image(pil_img)
            el.ocr_text = self.extract_text_from_image(pil_img, ocr_cfg)  # type: ignore[attr-defined]
            el.description = self.generate_description(pil_img, el, llm_cfg)  # type: ignore[attr-defined]

            caption_el = self._find_nearest_caption(el, captions)
            if caption_el is not None:
                el.caption = getattr(caption_el, "text", None)  # type: ignore[attr-defined]

            logger.debug(
                "Image %s: type=%s, ocr_chars=%d",
                el.element_id[:8],
                el.image_type.value,
                len(el.ocr_text or ""),
            )

    @staticmethod
    def _load_image(element: Image) -> Optional[PILImage.Image]:
        file_path: Path | None = getattr(element, "file_path", None)
        if not file_path or not Path(file_path).exists():
            return None
        try:
            return PILImage.open(file_path).convert("RGB")
        except Exception as exc:
            logger.debug("Cannot load image %s: %s", file_path, exc)
            return None

    def classify_image(self, image: PILImage.Image) -> ImageType:
        """Classify image visual type from aspect ratio and pixel statistics.

        Args:
            image: PIL image to classify.

        Returns:
            :class:`~smart_pdf_scanner.models.elements.ImageType` value.
        """
        w, h = image.size
        if h == 0:
            return ImageType.UNKNOWN
        ratio = w / h
        if ratio >= _WIDE_RATIO:
            return ImageType.CHART
        if ratio <= _TALL_RATIO:
            return ImageType.PHOTO
        # Use colour entropy as a rough diagram/photo discriminator
        try:
            import numpy as np
            arr = np.array(image.convert("L"))
            std = float(arr.std())
            return ImageType.PHOTO if std > 60 else ImageType.DIAGRAM
        except Exception:
            return ImageType.UNKNOWN

    def extract_text_from_image(
        self, image: PILImage.Image, config: OCRConfig
    ) -> str:
        """Run OCR on *image* and return extracted text, or empty string.

        Args:
            image: PIL image to process.
            config: OCR configuration to use.

        Returns:
            Extracted text string.
        """
        if self._ocr is None:
            return ""
        w, h = image.size
        if w < _MIN_OCR_PIXELS or h < _MIN_OCR_PIXELS:
            return ""
        try:
            result = self._ocr.extract_text(image, config)
            return result.text
        except Exception as exc:
            logger.debug("OCR on image failed: %s", exc)
            return ""

    def generate_description(
        self,
        image: PILImage.Image,
        element: Image,
        llm_cfg: Optional[LLMConfig],
    ) -> str:
        """Generate a textual description of *image*.

        Uses the LLM provider when available; otherwise falls back to a
        heuristic description based on image type and dimensions.

        Args:
            image: PIL image.
            element: The Image element (for type and OCR text).
            llm_cfg: LLM configuration; ``None`` triggers heuristic mode.

        Returns:
            Description string.
        """
        ocr_text: str = getattr(element, "ocr_text", "") or ""
        image_type: ImageType = getattr(element, "image_type", ImageType.UNKNOWN)

        if self._llm is not None and llm_cfg is not None:
            context = f"The image appears to be a {image_type.value}."
            if ocr_text:
                context += f" It contains the text: {ocr_text[:200]}"
            prompt = (
                f"Describe this document image concisely in 1–2 sentences. {context}"
            )
            try:
                return self._llm.generate_with_vision(prompt, image, llm_cfg)
            except Exception as exc:
                logger.debug("LLM image description failed: %s", exc)

        # Heuristic fallback
        w, h = image.size
        base = f"A {image_type.value} image ({w}×{h} px)"
        if ocr_text:
            preview = ocr_text[:80].replace("\n", " ")
            return f"{base} containing text: \"{preview}\""
        return base + "."

    @staticmethod
    def _find_nearest_caption(
        image: Image, captions: list
    ) -> Optional[object]:
        """Return the caption element geometrically closest to *image*, or None."""
        if not captions:
            return None
        def dist(cap: object) -> float:
            cb = getattr(cap, "bbox", None)
            ib = image.bbox
            if cb is None:
                return float("inf")
            # vertical gap below the image
            return abs(cb.y0 - ib.y1)
        closest = min(captions, key=dist)
        # Only associate if within ~50 pt
        if dist(closest) < 50:
            return closest
        return None
