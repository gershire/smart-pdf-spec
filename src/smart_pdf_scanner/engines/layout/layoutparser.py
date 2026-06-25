"""LayoutParser engine implementation.

Uses the ``layoutparser`` library with a Detectron2-backed model to detect
and classify document layout elements (Requirement 3: Layout Analysis).

Requires:
    pip install layoutparser
    pip install detectron2  # see https://detectron2.readthedocs.io/en/latest/tutorials/install.html

Both libraries have complex native-extension dependencies.  The engine
performs a lazy import so that the rest of the pipeline remains importable
even when these libraries are not installed.
"""

from __future__ import annotations

import logging
import uuid
from typing import List

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.models.config import LayoutConfig
from smart_pdf_scanner.models.elements import BoundingBox, Element, ElementType, TextBlock
from smart_pdf_scanner.models.page import Page

__all__ = ["LayoutParserEngine"]

logger = logging.getLogger(__name__)

# Mapping from PubLayNet label names to ElementType enum values.
_LABEL_MAP: dict[str, ElementType] = {
    "Text": ElementType.TEXT_BLOCK,
    "Title": ElementType.HEADING,
    "List": ElementType.TEXT_BLOCK,
    "Table": ElementType.TABLE,
    "Figure": ElementType.IMAGE,
}
_DEFAULT_LABEL = ElementType.TEXT_BLOCK


class LayoutParserEngine(LayoutEngine):
    """Layout engine backed by LayoutParser + Detectron2.

    Loads a PubLayNet model (or a custom model configured via
    ``config.model``) and runs inference on a page rendered as a PIL image.
    Detected regions are mapped to :class:`~smart_pdf_scanner.models.elements.Element`
    objects whose text content is filled from overlapping elements already
    on the page (parsed by the PDF parser stage).

    The model is loaded lazily on the first :meth:`detect_layout` call to
    avoid import-time costs.

    Args:
        device: Inference device string passed to layoutparser (e.g.
            ``"cpu"`` or ``"cuda:0"``).  Defaults to ``"cpu"``.

    Raises:
        ImportError: If ``layoutparser`` or ``detectron2`` are not installed,
            raised on the first :meth:`detect_layout` call with a helpful
            installation message.
    """

    def __init__(self, *, device: str = "cpu") -> None:
        self._device = device
        self._model: object | None = None
        self._loaded_model_path: str | None = None

    # ------------------------------------------------------------------
    # LayoutEngine interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "layoutparser"

    def detect_layout(self, page: Page, config: LayoutConfig) -> List[Element]:
        """Detect layout on *page* using the Detectron2-backed model.

        Args:
            page: Page to analyse. Must have ``_image`` attribute set by the
                PDF parser (a PIL Image of the rendered page).
            config: Active layout configuration; ``config.model`` overrides
                the default PubLayNet model path.

        Returns:
            List of elements classified by the model, with ``confidence``
            set to the Detectron2 detection score.

        Raises:
            ImportError: If layoutparser / detectron2 are not installed.
            AttributeError: If the page has no rendered image attached.
        """
        try:
            import layoutparser as lp  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "layoutparser is required for LayoutParserEngine. "
                "Install it with: pip install layoutparser detectron2"
            ) from exc

        self._ensure_model(lp, config.model)
        page_image = getattr(page, "_image", None)
        if page_image is None:
            logger.warning(
                "Page %d has no rendered image; returning existing elements.",
                page.page_number,
            )
            return list(page.elements)

        import numpy as np

        arr = np.array(page_image)
        layout = self._model.detect(arr)  # type: ignore[union-attr]

        elements: List[Element] = []
        for block in layout:
            element_type = _LABEL_MAP.get(block.type, _DEFAULT_LABEL)
            x1, y1, x2, y2 = (
                block.block.x_1,
                block.block.y_1,
                block.block.x_2,
                block.block.y_2,
            )
            text = self._text_for_region(page, x1, y1, x2, y2)
            elements.append(
                TextBlock(
                    element_id=str(uuid.uuid4()),
                    element_type=element_type,
                    bbox=BoundingBox(x0=x1, y0=y1, x1=x2, y1=y2),
                    page_number=page.page_number,
                    confidence=float(block.score),
                    text=text,
                )
            )
        return elements

    def get_confidence(self, element: Element) -> float:
        """Return ``element.confidence`` set during detection."""
        return element.confidence

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_model(self, lp: object, model_path: str) -> None:
        """Load the Detectron2 model if not already loaded or path changed."""
        if self._model is not None and self._loaded_model_path == model_path:
            return
        logger.info("Loading LayoutParser model: %s on %s", model_path, self._device)
        self._model = lp.Detectron2LayoutModel(  # type: ignore[attr-defined]
            model_path,
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
            label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
            device=self._device,
        )
        self._loaded_model_path = model_path

    @staticmethod
    def _text_for_region(
        page: Page, x0: float, y0: float, x1: float, y1: float
    ) -> str:
        """Collect text from page elements whose bbox overlaps this region."""
        region = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
        texts: List[str] = []
        for el in page.elements:
            if region.intersects(el.bbox):
                text = getattr(el, "text", None)
                if text:
                    texts.append(text)
        return " ".join(texts)
