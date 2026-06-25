"""Page renderer with bounding-box overlays.

Renders PDF pages as PIL images using PyMuPDF and overlays color-coded
bounding boxes for detected elements.  PyMuPDF is imported lazily so the
module stays importable even when the library is not installed — only
:meth:`PageRenderer.render_page` requires it.

(Requirement 11: Visualization Support)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage, ImageDraw

from smart_pdf_scanner.models.elements import BoundingBox, Element
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.visualization.colors import (
    ColorRGBA,
    ColorScheme,
    get_color_scheme,
    get_element_color,
)

__all__ = ["PageRenderer"]

logger = logging.getLogger(__name__)

# Points per inch for PDF coordinates.
_POINTS_PER_INCH = 72.0

# Outline width (pixels) for bounding box borders.
_BORDER_WIDTH = 2


class PageRenderer:
    """Renders PDF pages as images and overlays element bounding boxes.

    Coordinates in :class:`~smart_pdf_scanner.models.elements.BoundingBox`
    objects are expressed in PDF points (1 inch = 72 points).  The renderer
    scales them to pixel space using ``scale = dpi / 72``.

    Args:
        dpi: Rendering resolution in dots per inch.  Higher values produce
            sharper images at the cost of memory.  Defaults to 150 dpi.
        color_scheme: Custom color scheme.  When ``None`` the
            :data:`~smart_pdf_scanner.visualization.colors.DEFAULT_COLOR_SCHEME`
            is used.
        fill_alpha: Alpha value ``[0, 255]`` used for the filled interior of
            bounding box rectangles.  The outline always uses full opacity.
            Defaults to 80 (≈31 % opacity).

    Example::

        renderer = PageRenderer(dpi=150)
        img = renderer.render_with_annotations(page, pdf_path=Path("doc.pdf"))
        img.save("page_0.png")
    """

    def __init__(
        self,
        dpi: int = 150,
        color_scheme: Optional[ColorScheme] = None,
        fill_alpha: int = 80,
    ) -> None:
        self._dpi = dpi
        self._scheme = color_scheme if color_scheme is not None else get_color_scheme()
        self._fill_alpha = max(0, min(255, fill_alpha))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_page(
        self,
        page: Page,
        pdf_path: Optional[Path] = None,
    ) -> PILImage.Image:
        """Render *page* as an RGB PIL image.

        When *pdf_path* is supplied the page is rasterised from the source PDF
        using PyMuPDF at :attr:`dpi` resolution.  When omitted (or when
        PyMuPDF is not installed) a plain white canvas sized to the page
        dimensions is returned instead.

        Args:
            page: The page to render.
            pdf_path: Path to the source PDF.  Required for real page content.

        Returns:
            An RGB :class:`~PIL.Image.Image` of the rendered page.
        """
        if pdf_path is not None:
            try:
                return self._render_with_fitz(page.page_number, pdf_path)
            except Exception as exc:
                logger.warning(
                    "PyMuPDF rendering failed (page %d): %s — falling back to blank canvas",
                    page.page_number,
                    exc,
                )

        return self._blank_canvas(page)

    def draw_bbox(
        self,
        image: PILImage.Image,
        bbox: BoundingBox,
        color: ColorRGBA,
        scale: float = 1.0,
    ) -> None:
        """Draw a single bounding box on *image* in-place.

        Draws a semi-transparent filled rectangle with a fully-opaque outline.

        Args:
            image: The RGBA image to draw on.  Must be in ``"RGBA"`` mode.
            bbox: Element bounding box in PDF point coordinates.
            color: ``(R, G, B, A)`` fill color; the ``A`` component is
                replaced by :attr:`fill_alpha`.
            scale: Pixels-per-point scale factor (``dpi / 72``).
        """
        draw = ImageDraw.Draw(image, "RGBA")
        x0 = int(bbox.x0 * scale)
        y0 = int(bbox.y0 * scale)
        x1 = int(bbox.x1 * scale)
        y1 = int(bbox.y1 * scale)
        r, g, b, _ = color
        draw.rectangle(
            [x0, y0, x1, y1],
            fill=(r, g, b, self._fill_alpha),
            outline=(r, g, b, 255),
            width=_BORDER_WIDTH,
        )

    def apply_colors(
        self,
        image: PILImage.Image,
        page: Page,
        scale: float = 1.0,
    ) -> PILImage.Image:
        """Overlay color-coded bounding boxes for all elements on *page*.

        Converts *image* to RGBA, draws each element's bounding box using the
        renderer's :attr:`color_scheme`, then returns the result as an RGB
        image.

        Args:
            image: Base page image (any PIL mode).
            page: Page whose elements will be annotated.
            scale: Pixels-per-point scale factor (``dpi / 72``).

        Returns:
            A new RGB image with bounding box overlays applied.
        """
        result = image.convert("RGBA")
        for element in page.elements:
            color = get_element_color(element.element_type, self._scheme)
            self.draw_bbox(result, element.bbox, color, scale)
        return result.convert("RGB")

    def render_with_annotations(
        self,
        page: Page,
        pdf_path: Optional[Path] = None,
    ) -> PILImage.Image:
        """Render *page* and overlay element bounding boxes in one call.

        Convenience wrapper that chains :meth:`render_page` →
        :meth:`apply_colors`.

        Args:
            page: The page to render and annotate.
            pdf_path: Optional path to the source PDF for real page content.

        Returns:
            An annotated RGB image.
        """
        base = self.render_page(page, pdf_path)
        scale = self._dpi / _POINTS_PER_INCH
        return self.apply_colors(base, page, scale)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def dpi(self) -> int:
        """Rendering resolution in dots per inch."""
        return self._dpi

    @property
    def color_scheme(self) -> ColorScheme:
        """The active color scheme used for element overlays."""
        return self._scheme

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_with_fitz(self, page_index: int, pdf_path: Path) -> PILImage.Image:
        """Use PyMuPDF to rasterise page *page_index* from *pdf_path*."""
        import fitz  # lazy import — PyMuPDF

        doc = fitz.open(str(pdf_path))
        try:
            fitz_page = doc[page_index]
            scale = self._dpi / _POINTS_PER_INCH
            mat = fitz.Matrix(scale, scale)
            pix = fitz_page.get_pixmap(matrix=mat, alpha=False)
            return PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        finally:
            doc.close()

    def _blank_canvas(self, page: Page) -> PILImage.Image:
        """Create a white canvas sized to *page* dimensions at :attr:`dpi`."""
        scale = self._dpi / _POINTS_PER_INCH
        width = max(1, int(page.dimensions.width * scale))
        height = max(1, int(page.dimensions.height * scale))
        return PILImage.new("RGB", (width, height), color=(255, 255, 255))
