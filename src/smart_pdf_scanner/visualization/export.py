"""Visualization export utilities.

Exports annotated page images to files, supporting single-page and
multi-page batch export with PNG/JPEG output and embedded metadata
(Requirement 11: Visualization Support).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
from PIL import PngImagePlugin

from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.visualization.colors import ColorScheme
from smart_pdf_scanner.visualization.renderer import PageRenderer

__all__ = [
    "export_visualization",
    "export_all_pages",
]

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = frozenset({"png", "jpeg", "jpg"})
_DEFAULT_FORMAT = "png"


def export_visualization(
    page: Page,
    output_path: Path,
    *,
    pdf_path: Optional[Path] = None,
    renderer: Optional[PageRenderer] = None,
    color_scheme: Optional[ColorScheme] = None,
    dpi: int = 150,
    fmt: str = _DEFAULT_FORMAT,
    include_metadata: bool = True,
) -> Path:
    """Render a single page with bounding-box overlays and save it to a file.

    Args:
        page: The page to visualise.
        output_path: Destination file path.  The suffix is overridden to match
            *fmt* when they differ.
        pdf_path: Optional path to the source PDF for real page rendering.
            When omitted a blank white canvas is used.
        renderer: Optional pre-configured :class:`~.renderer.PageRenderer`.
            When ``None`` a new renderer is created from *dpi* and
            *color_scheme*.
        color_scheme: Custom color scheme forwarded to the renderer when
            *renderer* is ``None``.
        dpi: Rendering resolution; used only when *renderer* is ``None``.
        fmt: Output image format — ``"png"`` (default) or ``"jpeg"``/``"jpg"``.
        include_metadata: When ``True`` (default) page metadata is embedded in
            the saved image (PNG text chunks or JPEG comment).

    Returns:
        The resolved :class:`~pathlib.Path` of the saved file.

    Raises:
        ValueError: If *fmt* is not a supported image format.
    """
    fmt = fmt.lower().lstrip(".")
    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{fmt}'. Supported: {sorted(_SUPPORTED_FORMATS)}"
        )
    canonical_fmt = "jpeg" if fmt in {"jpeg", "jpg"} else "png"

    # Ensure output path has the correct suffix
    output_path = output_path.with_suffix(f".{canonical_fmt if canonical_fmt != 'jpeg' else 'jpg'}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if renderer is None:
        renderer = PageRenderer(dpi=dpi, color_scheme=color_scheme)

    image = renderer.render_with_annotations(page, pdf_path=pdf_path)

    _save_image(
        image=image,
        path=output_path,
        fmt=canonical_fmt,
        metadata=_build_page_metadata(page) if include_metadata else None,
    )
    logger.info("Saved visualization: %s (page %d)", output_path, page.page_number)
    return output_path


def export_all_pages(
    document: Document,
    output_dir: Path,
    *,
    pdf_path: Optional[Path] = None,
    renderer: Optional[PageRenderer] = None,
    color_scheme: Optional[ColorScheme] = None,
    dpi: int = 150,
    fmt: str = _DEFAULT_FORMAT,
    include_metadata: bool = True,
) -> list[Path]:
    """Render all pages of a document and save them to *output_dir*.

    Output files are named ``page_{n:04d}.{ext}`` where *n* is the
    :attr:`~smart_pdf_scanner.models.page.Page.page_number`.

    Args:
        document: The processed document containing pages to export.
        output_dir: Directory where rendered images are saved.  Created if it
            does not exist.
        pdf_path: Optional path to the source PDF for real page content.
        renderer: Optional pre-configured :class:`~.renderer.PageRenderer`
            shared across all pages.  When ``None`` one is created from *dpi*
            and *color_scheme*.
        color_scheme: Custom color scheme; forwarded to the renderer when
            *renderer* is ``None``.
        dpi: Rendering resolution; used only when *renderer* is ``None``.
        fmt: Output image format — ``"png"`` (default) or ``"jpeg"``/``"jpg"``.
        include_metadata: Embed page metadata in each image.

    Returns:
        Ordered list of :class:`~pathlib.Path` objects for each saved file.

    Raises:
        ValueError: If *fmt* is not a supported image format.
    """
    fmt_clean = fmt.lower().lstrip(".")
    if fmt_clean not in _SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{fmt_clean}'. Supported: {sorted(_SUPPORTED_FORMATS)}"
        )
    ext = "jpg" if fmt_clean in {"jpeg", "jpg"} else "png"
    output_dir.mkdir(parents=True, exist_ok=True)

    if renderer is None:
        renderer = PageRenderer(dpi=dpi, color_scheme=color_scheme)

    saved: list[Path] = []
    for page in document.pages:
        output_path = output_dir / f"page_{page.page_number:04d}.{ext}"
        path = export_visualization(
            page=page,
            output_path=output_path,
            pdf_path=pdf_path,
            renderer=renderer,
            fmt=ext,
            include_metadata=include_metadata,
        )
        saved.append(path)

    logger.info(
        "Exported %d page visualization(s) to %s", len(saved), output_dir
    )
    return saved


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_page_metadata(page: Page) -> dict[str, str]:
    """Build a metadata dict for embedding in an image file."""
    element_counts: dict[str, int] = {}
    for element in page.elements:
        key = element.element_type.value
        element_counts[key] = element_counts.get(key, 0) + 1

    return {
        "page_number": str(page.page_number),
        "page_width_pts": str(page.dimensions.width),
        "page_height_pts": str(page.dimensions.height),
        "element_count": str(len(page.elements)),
        "element_types": json.dumps(element_counts),
        "is_image_based": str(page.is_image_based),
        "generator": "smart-pdf-scanner visualization",
    }


def _save_image(
    image: PILImage.Image,
    path: Path,
    fmt: str,
    metadata: dict[str, str] | None,
) -> None:
    """Save *image* to *path* with optional embedded *metadata*."""
    if fmt == "png":
        png_info = PngImagePlugin.PngInfo()
        if metadata:
            for key, value in metadata.items():
                png_info.add_text(key, value)
        image.save(str(path), format="PNG", pnginfo=png_info)
    else:
        # JPEG: embed metadata as a comment string
        comment = json.dumps(metadata).encode() if metadata else b""
        image = image.convert("RGB")
        image.save(str(path), format="JPEG", quality=90, comment=comment)
