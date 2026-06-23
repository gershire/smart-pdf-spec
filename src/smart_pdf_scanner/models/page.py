"""Page models for the PDF processing pipeline.

Defines the :class:`Page` container that holds the elements detected on a single
page, along with its :class:`PageDimensions` (Requirement 1). Pages use Pydantic
for validation and provide helper methods for managing and querying elements.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from smart_pdf_scanner.models.elements import AnyElement, Element, ElementType


class PageDimensions(BaseModel):
    """Physical dimensions of a page, expressed in points.

    Attributes:
        width: Page width in points.
        height: Page height in points.
    """

    width: float = Field(ge=0.0)
    height: float = Field(ge=0.0)


class Page(BaseModel):
    """A single document page and the elements detected on it.

    Attributes:
        page_number: The page index within the document.
        elements: The elements detected on the page.
        dimensions: The page's physical dimensions.
        is_image_based: Whether the page is image-based (scanned) rather than
            containing extractable text.
        ocr_confidence: Optional aggregate OCR confidence for the page.
    """

    page_number: int = Field(ge=0)
    elements: list[AnyElement] = Field(default_factory=list)
    dimensions: PageDimensions
    is_image_based: bool = False
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    def add_element(self, element: Element) -> None:
        """Add an element to the page.

        Args:
            element: The element to append to this page.
        """
        self.elements.append(element)

    def get_elements_by_type(self, element_type: ElementType) -> list[Element]:
        """Return all elements on the page matching a given type.

        Args:
            element_type: The element type to filter by.

        Returns:
            The elements whose ``element_type`` equals ``element_type``.
        """
        return [element for element in self.elements if element.element_type == element_type]
