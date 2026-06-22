"""Core element data models for the PDF processing pipeline.

This module defines the foundational data models used throughout the layout
analysis stage (Requirement 3): the :class:`ElementType` enumeration, the
:class:`BoundingBox` geometry primitive with its geometric operations, and the
:class:`Element` base class that all concrete element types extend.

It also defines the concrete element types produced by the parsing, table, and
image stages (Requirements 2, 6, 7): :class:`TextBlock`, :class:`Heading`,
:class:`Table`, and :class:`Image`, together with their supporting models
:class:`FontInfo`, :class:`TableRow`, and :class:`ImageType`.

The models use Pydantic for validation and JSON serialization, ensuring type
safety across the pipeline.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ElementType(str, Enum):
    """Classification of a detected layout element.

    The values mirror the element categories produced by the layout analysis
    stage (Requirement 3): text block, heading, table, image, caption,
    footnote, and sidebar.
    """

    TEXT_BLOCK = "text_block"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    SIDEBAR = "sidebar"


class BoundingBox(BaseModel):
    """Axis-aligned bounding box defined by two corner coordinates.

    Coordinates follow the ``(x0, y0)`` top-left and ``(x1, y1)`` bottom-right
    convention, where ``x1 >= x0`` and ``y1 >= y0``. The box is validated on
    construction to guarantee this invariant so that geometric operations
    behave predictably.

    Attributes:
        x0: Left coordinate of the box.
        y0: Top coordinate of the box.
        x1: Right coordinate of the box.
        y1: Bottom coordinate of the box.
    """

    model_config = ConfigDict(frozen=False)

    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def _validate_ordering(self) -> "BoundingBox":
        """Ensure the box corners are correctly ordered.

        Returns:
            The validated bounding box.

        Raises:
            ValueError: If ``x1 < x0`` or ``y1 < y0``.
        """
        if self.x1 < self.x0:
            raise ValueError(f"x1 ({self.x1}) must be >= x0 ({self.x0})")
        if self.y1 < self.y0:
            raise ValueError(f"y1 ({self.y1}) must be >= y0 ({self.y0})")
        return self

    @property
    def width(self) -> float:
        """Width of the bounding box."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Height of the bounding box."""
        return self.y1 - self.y0

    def area(self) -> float:
        """Calculate the bounding box area.

        Returns:
            The area as ``width * height``.
        """
        return self.width * self.height

    def intersects(self, other: "BoundingBox") -> bool:
        """Check whether this box overlaps another box.

        Two boxes intersect only when they share a region of positive area;
        boxes that merely touch along an edge or corner are not considered
        intersecting.

        Args:
            other: The bounding box to test against.

        Returns:
            ``True`` if the boxes overlap, ``False`` otherwise.
        """
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )

    def contains(self, other: "BoundingBox") -> bool:
        """Check whether this box fully contains another box.

        Containment is inclusive: a box contains itself, and edges may be
        shared.

        Args:
            other: The bounding box to test for containment.

        Returns:
            ``True`` if ``other`` lies entirely within this box.
        """
        return (
            self.x0 <= other.x0
            and self.y0 <= other.y0
            and self.x1 >= other.x1
            and self.y1 >= other.y1
        )

    def intersection(self, other: "BoundingBox") -> "BoundingBox | None":
        """Compute the overlapping region between this box and another.

        Args:
            other: The bounding box to intersect with.

        Returns:
            A new :class:`BoundingBox` describing the overlap, or ``None`` if
            the boxes do not intersect.
        """
        if not self.intersects(other):
            return None
        return BoundingBox(
            x0=max(self.x0, other.x0),
            y0=max(self.y0, other.y0),
            x1=min(self.x1, other.x1),
            y1=min(self.y1, other.y1),
        )

    def iou(self, other: "BoundingBox") -> float:
        """Compute the intersection-over-union with another box.

        Args:
            other: The bounding box to compare against.

        Returns:
            The IoU ratio in the range ``[0.0, 1.0]``. Returns ``0.0`` when the
            boxes do not overlap or the union has zero area.
        """
        overlap = self.intersection(other)
        if overlap is None:
            return 0.0
        intersection_area = overlap.area()
        union_area = self.area() + other.area() - intersection_area
        if union_area <= 0:
            return 0.0
        return intersection_area / union_area


class Element(BaseModel):
    """Base class for all detected document elements.

    Concrete element types (text blocks, headings, tables, images, etc.)
    extend this class with type-specific fields.

    Attributes:
        element_id: Unique identifier for the element.
        element_type: The classified :class:`ElementType` of the element.
        bbox: The :class:`BoundingBox` describing the element's location.
        page_number: Zero-based or one-based page index the element belongs to.
        confidence: Detection confidence in the range ``[0.0, 1.0]``.
    """

    element_id: str
    element_type: ElementType
    bbox: BoundingBox
    page_number: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FontInfo(BaseModel):
    """Font attributes for a piece of text.

    Attributes:
        name: Font family name (e.g. ``"Helvetica"``).
        size: Font size in points.
        weight: Font weight, ``"normal"`` or ``"bold"``.
        style: Font style, ``"normal"`` or ``"italic"``.
    """

    name: str
    size: float
    weight: str
    style: str


class TextBlock(Element):
    """A block of text extracted from a page (Requirement 2).

    Attributes:
        text: The extracted text content.
        font_info: Optional font metadata for the block.
        reading_order: Index of the block within the page reading order.
        hierarchy_level: Optional logical nesting level of the block.
    """

    element_type: ElementType = ElementType.TEXT_BLOCK
    text: str
    font_info: FontInfo | None = None
    reading_order: int = 0
    hierarchy_level: int | None = None


class Heading(TextBlock):
    """A heading element (Requirement 2).

    Attributes:
        level: Heading level from 1 (H1) to 6 (H6).
    """

    element_type: ElementType = ElementType.HEADING
    level: int = Field(ge=1, le=6)


class TableRow(BaseModel):
    """A single row of table cell values.

    Attributes:
        cells: The ordered cell values for the row.
    """

    cells: list[str]


class Table(Element):
    """A table element with its extracted content (Requirement 6).

    Attributes:
        rows: The table rows.
        headers: Optional header labels for the table columns.
        markdown: The table rendered as Markdown.
        csv_path: Optional path to an exported CSV of the table.
    """

    element_type: ElementType = ElementType.TABLE
    rows: list[TableRow]
    headers: list[str] | None = None
    markdown: str
    csv_path: Path | None = None


class ImageType(str, Enum):
    """Visual classification of an extracted image (Requirement 7)."""

    PHOTOGRAPH = "photograph"
    DIAGRAM = "diagram"
    CHART = "chart"
    GRAPH = "graph"
    ILLUSTRATION = "illustration"
    OTHER = "other"


class Image(Element):
    """An image element extracted from a page (Requirement 7).

    Attributes:
        image_path: Path to the saved image asset.
        image_type: The classified :class:`ImageType` of the image.
        description: Human- or model-generated description of the image.
        ocr_text: Optional text recognized within the image.
        caption: Optional caption associated with the image.
    """

    element_type: ElementType = ElementType.IMAGE
    image_path: Path
    image_type: ImageType
    description: str
    ocr_text: str | None = None
    caption: str | None = None
