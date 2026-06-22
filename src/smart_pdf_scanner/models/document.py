"""Top-level document model for the PDF processing pipeline.

The :class:`Document` is the root container produced by the pipeline
(Requirement 1). It aggregates the document metadata, its pages, the optional
logical structure, and any processing warnings, and provides helper methods for
managing pages and querying elements across the whole document.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from smart_pdf_scanner.models.elements import Element
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page
from smart_pdf_scanner.models.structure import DocumentStructure


class Document(BaseModel):
    """The root container for a processed document.

    Attributes:
        metadata: Metadata describing the source document.
        pages: The document's pages, in order.
        structure: Optional logical structure (headings, TOC, links).
        assets_folder: Directory where extracted assets (images, CSVs) are saved.
        processing_warnings: Warnings accumulated during processing.
    """

    metadata: DocumentMetadata
    pages: list[Page] = Field(default_factory=list)
    structure: DocumentStructure | None = None
    assets_folder: Path
    processing_warnings: list[str] = Field(default_factory=list)

    def add_page(self, page: Page) -> None:
        """Add a page to the document.

        Args:
            page: The page to append.
        """
        self.pages.append(page)

    def get_page(self, page_num: int) -> Page | None:
        """Return the page with the given page number.

        Args:
            page_num: The ``page_number`` to look up.

        Returns:
            The matching :class:`Page`, or ``None`` if no page has that number.
        """
        for page in self.pages:
            if page.page_number == page_num:
                return page
        return None

    def get_all_elements(self) -> list[Element]:
        """Return every element across all pages in page order.

        Returns:
            A flat list of all elements contained in the document's pages.
        """
        elements: list[Element] = []
        for page in self.pages:
            elements.extend(page.elements)
        return elements
