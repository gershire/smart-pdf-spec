"""PDFParser stage — raw PDF data extraction.

Extracts text with positions, embedded images, and document metadata from a
PDF file using PyMuPDF (``fitz``).  Produces a populated
:class:`~smart_pdf_scanner.models.document.Document` with one
:class:`~smart_pdf_scanner.models.page.Page` per PDF page (Requirement 2).

Requires:
    pip install pymupdf
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import List

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    ElementType,
    FontInfo,
    Image,
    ImageType,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning, WarningSeverity

__all__ = ["PDFParser"]

logger = logging.getLogger(__name__)


class PDFParser(ProcessingStage):
    """Pipeline stage that opens a PDF and extracts raw content.

    The stage expects ``config`` to carry the source path via the ``_pdf_path``
    attribute set by the :class:`~smart_pdf_scanner.core.pipeline.Pipeline`
    before invoking each stage.  Alternatively, pass *pdf_path* directly to
    the constructor for standalone use.

    Processing steps per page:
    1. Extract text blocks with bounding boxes and font info.
    2. Detect whether the page is image-based (no extractable text layer).
    3. Extract embedded images and save them to ``document.assets_folder``.

    Args:
        pdf_path: Path to the PDF file.  Overrides the path set on the
            pipeline if provided.
    """

    def __init__(self, pdf_path: Path | None = None) -> None:
        self._pdf_path = pdf_path

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "pdf_parser"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        path = self._resolve_path(document)
        warnings: List[ValidationWarning] = []
        if path is None:
            warnings.append(
                ValidationWarning(
                    code="missing_pdf_path",
                    message="No PDF path provided to PDFParser.",
                    severity=WarningSeverity.ERROR,
                )
            )
            return warnings
        if not path.exists():
            warnings.append(
                ValidationWarning(
                    code="pdf_not_found",
                    message=f"PDF file not found: {path}",
                    severity=WarningSeverity.ERROR,
                )
            )
        elif path.stat().st_size > config.max_file_size_mb * 1024 * 1024:
            warnings.append(
                ValidationWarning(
                    code="pdf_too_large",
                    message=(
                        f"PDF exceeds max_file_size_mb={config.max_file_size_mb}: {path}"
                    ),
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Extract text, images and metadata from the PDF.

        Args:
            document: Document whose ``assets_folder`` is used for image output.
            config: Active pipeline configuration.

        Returns:
            The document populated with pages and metadata.
        """
        import fitz  # PyMuPDF

        path = self._resolve_path(document)
        if path is None:
            raise ValueError("No PDF path provided to PDFParser.")

        logger.info("Parsing PDF: %s", path)
        doc = fitz.open(str(path))
        try:
            document.metadata = self._extract_metadata(doc, path)
            document.assets_folder.mkdir(parents=True, exist_ok=True)

            for page_idx in range(len(doc)):
                fitz_page = doc[page_idx]
                page = self._parse_page(fitz_page, page_idx, document.assets_folder)
                document.add_page(page)
        finally:
            doc.close()

        logger.info(
            "PDFParser extracted %d pages from %s", len(document.pages), path.name
        )
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, document: Document) -> Path | None:
        if self._pdf_path is not None:
            return self._pdf_path
        # Pipeline may stash the path on the document metadata title as a Path
        # object; check the private pipeline attribute conveyed via metadata.
        src = getattr(document, "_pdf_path", None)
        return Path(src) if src else None

    @staticmethod
    def _extract_metadata(doc: object, path: Path) -> DocumentMetadata:

        raw: dict = doc.metadata  # type: ignore[union-attr]
        stat = path.stat()
        return DocumentMetadata(
            title=raw.get("title") or None,
            author=raw.get("author") or None,
            subject=raw.get("subject") or None,
            keywords=raw.get("keywords") or None,
            creator=raw.get("creator") or None,
            producer=raw.get("producer") or None,
            page_count=len(doc),  # type: ignore[arg-type]
            file_size_bytes=stat.st_size,
        )

    def _parse_page(self, fitz_page: object, page_idx: int, assets_folder: Path) -> Page:

        rect = fitz_page.rect  # type: ignore[union-attr]
        dims = PageDimensions(width=rect.width, height=rect.height)
        page = Page(page_number=page_idx, dimensions=dims)

        text_blocks = self._extract_text_blocks(fitz_page)
        for block in text_blocks:
            page.add_element(block)

        images = self._extract_images(fitz_page, page_idx, assets_folder)
        for img in images:
            page.add_element(img)

        # Mark as image-based when no text was extracted
        if not text_blocks and images:
            page.is_image_based = True

        return page

    @staticmethod
    def _extract_text_blocks(fitz_page: object) -> List[TextBlock]:
        """Extract text with position and font info from a fitz Page."""
        blocks: List[TextBlock] = []
        # get_text("dict") returns nested block→line→span structure
        page_dict = fitz_page.get_text("dict")  # type: ignore[union-attr]
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            lines_text: List[str] = []
            first_span: dict | None = None
            x0, y0, x1, y1 = block["bbox"]
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    if span_text:
                        lines_text.append(span_text)
                        if first_span is None:
                            first_span = span
            full_text = " ".join(lines_text)
            if not full_text:
                continue
            font_info: FontInfo | None = None
            if first_span:
                _is_bold = (
                    "Bold" in first_span.get("font", "")
                    or bool(first_span.get("flags", 0) & 2**4)
                )
                _is_italic = (
                    "Italic" in first_span.get("font", "")
                    or bool(first_span.get("flags", 0) & 2**1)
                )
                font_info = FontInfo(
                    name=first_span.get("font", ""),
                    size=float(first_span.get("size", 0)),
                    weight="bold" if _is_bold else "normal",
                    style="italic" if _is_italic else "normal",
                )
            blocks.append(
                TextBlock(
                    element_id=str(uuid.uuid4()),
                    element_type=ElementType.TEXT_BLOCK,
                    bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    page_number=0,  # will be corrected by caller if needed
                    text=full_text,
                    font_info=font_info,
                )
            )
        return blocks

    def _extract_images(
        self, fitz_page: object, page_idx: int, assets_folder: Path
    ) -> List[Image]:
        """Extract embedded images from a fitz Page, saving to assets_folder."""

        images: List[Image] = []
        img_list = fitz_page.get_images(full=True)  # type: ignore[union-attr]
        doc = fitz_page.parent  # type: ignore[union-attr]
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception as exc:
                logger.debug("Could not extract image xref %d: %s", xref, exc)
                continue
            ext = base_image.get("ext", "png")
            img_bytes = base_image.get("image", b"")
            if not img_bytes:
                continue
            filename = f"page{page_idx:04d}_img{img_idx:03d}.{ext}"
            img_path = assets_folder / filename
            img_path.write_bytes(img_bytes)

            # Attempt to find the image's bbox on the page
            bbox = self._image_bbox(fitz_page, xref)
            images.append(
                Image(
                    element_id=str(uuid.uuid4()),
                    element_type=ElementType.IMAGE,
                    bbox=bbox,
                    page_number=page_idx,
                    image_type=ImageType.OTHER,
                    image_path=img_path,
                    description="",
                )
            )
        return images

    @staticmethod
    def _image_bbox(fitz_page: object, xref: int) -> BoundingBox:
        """Return the bbox of an image placed on the page, or a zero box."""
        try:
            for item in fitz_page.get_image_rects(xref):  # type: ignore[union-attr]
                r = item if hasattr(item, "x0") else item[0]
                return BoundingBox(x0=r.x0, y0=r.y0, x1=r.x1, y1=r.y1)
        except Exception:
            pass
        return BoundingBox(x0=0, y0=0, x1=0, y1=0)
