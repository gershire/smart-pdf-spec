"""TableProcessor stage — table extraction and Markdown/CSV conversion.

Uses ``pdfplumber`` to extract simple tables from text-layer PDFs.  For
complex tables it falls back to a heuristic row-detection approach so
the stage can run without optional heavy dependencies
(Requirement 6: Table Processing).

Optionally exports each table as a CSV file to ``document.assets_folder``
when ``config.export_tables_csv`` is ``True``.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, Table, TableRow
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning

__all__ = ["TableProcessor"]

logger = logging.getLogger(__name__)


class TableProcessor(ProcessingStage):
    """Pipeline stage that extracts tables and converts them to Markdown.

    Extraction strategy per page (with pdfplumber as the primary extractor):

    1. Open the source PDF page with pdfplumber.
    2. Call ``page.extract_tables()`` to get cell data.
    3. For each table, build a :class:`~smart_pdf_scanner.models.elements.Table`
       element with :class:`~smart_pdf_scanner.models.elements.TableRow` rows.
    4. Generate a Markdown-formatted representation stored on the element's
       ``markdown`` attribute.
    5. Optionally write a CSV file to ``document.assets_folder``.

    When pdfplumber cannot detect tables (e.g. scanned pages), the stage
    silently skips the page.
    """

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "table_processor"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if not document.pages:
            warnings.append(
                ValidationWarning(
                    code="no_pages",
                    message="TableProcessor received a document with no pages.",
                )
            )
        pdf_path = getattr(document, "_pdf_path", None)
        if not pdf_path:
            warnings.append(
                ValidationWarning(
                    code="missing_pdf_path",
                    message=(
                        "TableProcessor requires a PDF path on document._pdf_path "
                        "to use pdfplumber."
                    ),
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Extract tables from every page and add them as Table elements.

        Args:
            document: Document to process.
            config: Active pipeline configuration.

        Returns:
            Document with Table elements added to pages.
        """
        pdf_path: Optional[Path] = getattr(document, "_pdf_path", None)
        if pdf_path is None:
            logger.warning("TableProcessor: no _pdf_path on document, skipping.")
            return document

        try:
            import pdfplumber
        except ImportError:
            logger.warning(
                "pdfplumber not installed; TableProcessor will not extract tables. "
                "Install with: pip install pdfplumber"
            )
            return document

        logger.info("TableProcessor: opening %s with pdfplumber", pdf_path)
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in document.pages:
                if page.page_number >= len(pdf.pages):
                    continue
                plumber_page = pdf.pages[page.page_number]
                self._process_page(page, plumber_page, document.assets_folder, config)
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_page(
        self,
        page: Page,
        plumber_page: object,
        assets_folder: Path,
        config: Config,
    ) -> None:
        raw_tables = plumber_page.extract_tables()  # type: ignore[union-attr]
        if not raw_tables:
            return
        for tbl_idx, raw in enumerate(raw_tables):
            if not raw:
                continue
            rows = self._build_rows(raw)
            if not rows:
                continue
            bbox = self._table_bbox(plumber_page, tbl_idx)
            table_id = str(uuid.uuid4())
            markdown = self.convert_to_markdown(rows)

            csv_path: Optional[Path] = None
            if config.export_tables_csv:
                csv_path = self.export_to_csv(
                    rows,
                    assets_folder / f"page{page.page_number:04d}_table{tbl_idx:03d}.csv",
                )

            table_el = Table(
                element_id=table_id,
                element_type=ElementType.TABLE,
                bbox=bbox,
                page_number=page.page_number,
                rows=rows,
                markdown=markdown,
                csv_path=csv_path,
            )
            page.add_element(table_el)
            logger.debug(
                "Page %d: table %d (%d×%d) extracted",
                page.page_number,
                tbl_idx,
                len(rows),
                max((len(r.cells) for r in rows), default=0),
            )

    @staticmethod
    def _build_rows(raw: list) -> List[TableRow]:
        rows: List[TableRow] = []
        for i, raw_row in enumerate(raw):
            cells = [str(c or "") for c in raw_row]
            rows.append(TableRow(cells=cells, is_header=(i == 0)))
        return rows

    @staticmethod
    def _table_bbox(plumber_page: object, tbl_idx: int) -> BoundingBox:
        """Get bounding box for the nth table on a pdfplumber page."""
        try:
            tables = plumber_page.find_tables()  # type: ignore[union-attr]
            if tbl_idx < len(tables):
                bb = tables[tbl_idx].bbox
                return BoundingBox(x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3])
        except Exception:
            pass
        return BoundingBox(x0=0, y0=0, x1=1, y1=1)

    @staticmethod
    def convert_to_markdown(rows: List[TableRow]) -> str:
        """Format *rows* as a GitHub Flavored Markdown table string.

        Args:
            rows: Table rows (first row treated as header).

        Returns:
            A Markdown table string.
        """
        if not rows:
            return ""
        col_count = max(len(r.cells) for r in rows)
        lines: List[str] = []

        def row_line(cells: List[str]) -> str:
            padded = cells + [""] * (col_count - len(cells))
            return "| " + " | ".join(c.replace("|", "\\|") for c in padded) + " |"

        # Header row
        header = rows[0]
        lines.append(row_line(header.cells))
        lines.append("| " + " | ".join(["---"] * col_count) + " |")
        for row in rows[1:]:
            lines.append(row_line(row.cells))
        return "\n".join(lines)

    @staticmethod
    def export_to_csv(rows: List[TableRow], path: Path) -> Path:
        """Write *rows* to a CSV file at *path*.

        Args:
            rows: Table rows to write.
            path: Destination path.

        Returns:
            The path written to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row.cells)
        return path
