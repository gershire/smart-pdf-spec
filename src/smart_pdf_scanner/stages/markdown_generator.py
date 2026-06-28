"""MarkdownGenerator stage — final Markdown assembly and file output.

Assembles all document elements in reading order, formats each element type
as valid GitHub Flavored Markdown, optionally inserts page-number markers,
and writes the result to the output file path stored on the document
(Requirement 9: Markdown Generation).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    AnyElement,
    ElementType,
    Heading,
    Image,
    Table,
    TextBlock,
)
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning

__all__ = ["MarkdownGenerator"]

logger = logging.getLogger(__name__)


class MarkdownGenerator(ProcessingStage):
    """Pipeline stage that produces the final Markdown document.

    Reads elements in the reading order established by
    :class:`~smart_pdf_scanner.stages.structure_recognizer.StructureRecognizer`
    (falling back to page order when no structure is available), then formats
    each element according to its type.

    The output path is read from ``document._output_path`` (set by the
    :class:`~smart_pdf_scanner.core.pipeline.Pipeline`).  If no path is set,
    the Markdown is stored on ``document._markdown`` for programmatic use.

    Args:
        output_path: Explicit output file path.  Overrides ``document._output_path``.
    """

    def __init__(self, output_path: Optional[Path] = None) -> None:
        self._output_path = output_path

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "markdown_generator"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if not document.pages:
            warnings.append(
                ValidationWarning(
                    code="no_pages",
                    message="MarkdownGenerator: document has no pages.",
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Assemble and write Markdown output.

        Args:
            document: Fully processed document.
            config: Active pipeline configuration.

        Returns:
            Document with ``_markdown`` attribute set.
        """
        markdown = self.assemble_markdown(document, config)
        document._markdown = markdown  # type: ignore[attr-defined]

        output_path = self._resolve_output_path(document)
        if output_path:
            self.write_output(markdown, output_path)
            logger.info("Markdown written to %s (%d chars)", output_path, len(markdown))
        else:
            logger.debug("No output path set; Markdown stored on document._markdown")

        return document

    # ------------------------------------------------------------------
    # Public formatting methods
    # ------------------------------------------------------------------

    def assemble_markdown(self, document: Document, config: Config) -> str:
        """Build the full Markdown string for *document*.

        Elements are ordered using ``document.structure.reading_order`` when
        available, otherwise by page order (top-to-bottom, left-to-right).

        Args:
            document: Fully processed document.
            config: Active pipeline configuration.

        Returns:
            Complete Markdown string.
        """
        # Build element lookup
        element_map: dict[str, AnyElement] = {}
        for page in document.pages:
            for el in page.elements:
                element_map[el.element_id] = el

        # Determine order
        if document.structure and document.structure.reading_order:
            ordered = [
                element_map[eid]
                for eid in document.structure.reading_order
                if eid in element_map
            ]
        else:
            ordered = self._page_order(document)

        sections: List[str] = []
        current_page: int = -1

        for el in ordered:
            # Optionally insert page markers
            if config.include_page_numbers and el.page_number != current_page:
                current_page = el.page_number
                sections.append(f"\n---\n<!-- Page {current_page + 1} -->\n")

            formatted = self._format_element(el)
            if formatted:
                sections.append(formatted)

        return "\n\n".join(s.strip() for s in sections if s.strip())

    def format_heading(self, element: Heading) -> str:
        """Format a Heading element as a Markdown heading.

        Args:
            element: Heading element with ``level`` (1–6) and ``text``.

        Returns:
            Markdown heading string (e.g. ``## Section Title``).
        """
        level = max(1, min(6, element.level))
        return f"{'#' * level} {element.text or ''}"

    def format_table(self, element: Table) -> str:
        """Format a Table element as GitHub Flavored Markdown.

        Uses the pre-computed ``element.markdown`` attribute when available
        (set by :class:`~smart_pdf_scanner.stages.table_processor.TableProcessor`),
        otherwise re-renders from the row data.

        Args:
            element: Table element.

        Returns:
            Markdown table string.
        """
        precomputed: str | None = getattr(element, "markdown", None)
        if precomputed:
            return precomputed
        if not element.rows:
            return ""
        # Minimal fallback renderer
        lines: List[str] = []
        col_count = max(len(r.cells) for r in element.rows)
        for i, row in enumerate(element.rows):
            padded = row.cells + [""] * (col_count - len(row.cells))
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in padded) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * col_count) + " |")
        return "\n".join(lines)

    def format_image(self, element: Image) -> str:
        """Format an Image element as a Markdown image or description block.

        Uses the LLM/heuristic description when available, otherwise produces
        a simple alt-text reference.

        Args:
            element: Image element.

        Returns:
            Markdown image string.
        """
        description: str = getattr(element, "description", "") or ""
        caption: str = getattr(element, "caption", "") or ""
        file_path = getattr(element, "image_path", None)

        alt = description or caption or "image"
        if file_path:
            md = f"![{alt}]({file_path})"
        else:
            md = f"*[Image: {alt}]*"
        if caption and caption != alt:
            md += f"\n*{caption}*"
        return md

    def write_output(self, markdown: str, path: Path) -> None:
        """Write *markdown* string to *path*, creating parent directories.

        Args:
            markdown: Markdown content to write.
            path: Destination file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_element(self, element: AnyElement) -> str:
        """Dispatch to the appropriate formatter for *element*."""
        etype = element.element_type
        if etype == ElementType.HEADING and isinstance(element, Heading):
            return self.format_heading(element)
        if etype == ElementType.TABLE and isinstance(element, Table):
            return self.format_table(element)
        if etype == ElementType.IMAGE and isinstance(element, Image):
            return self.format_image(element)
        if etype == ElementType.CAPTION:
            text = getattr(element, "text", "") or ""
            return f"*{text}*" if text else ""
        if etype == ElementType.FOOTNOTE:
            text = getattr(element, "text", "") or ""
            return f"> {text}" if text else ""
        # TEXT_BLOCK, SIDEBAR, and anything else
        text = getattr(element, "text", "") or ""
        return text

    def _resolve_output_path(self, document: Document) -> Optional[Path]:
        if self._output_path:
            return self._output_path
        p = getattr(document, "_output_path", None)
        return Path(p) if p else None

    @staticmethod
    def _page_order(document: Document) -> List[AnyElement]:
        """Return all elements in top-to-bottom, left-to-right page order."""
        result: List[AnyElement] = []
        for page in document.pages:
            sorted_els = sorted(
                page.elements, key=lambda el: (el.bbox.y0, el.bbox.x0)
            )
            result.extend(sorted_els)
        return result
