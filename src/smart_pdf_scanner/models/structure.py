"""Document structure models.

These models capture the logical structure of a document (Requirement 5): the
heading hierarchy, an optional table of contents, the reading order of
elements, and any links discovered in the document.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from smart_pdf_scanner.models.elements import Heading


class LinkType(str, Enum):
    """Classification of a document link."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class Link(BaseModel):
    """A link discovered within the document.

    Attributes:
        source_element_id: Identifier of the element the link originates from.
        target: The link target, either a URL or an internal reference.
        link_type: Whether the link is internal or external.
    """

    source_element_id: str
    target: str
    link_type: LinkType


class TOCEntry(BaseModel):
    """A single entry in a table of contents.

    Attributes:
        title: The displayed title of the entry.
        page_number: The page the entry points to.
        level: Nesting depth of the entry (1 is top level).
        linked_heading_id: Optional identifier of the heading this entry maps to.
    """

    title: str
    page_number: int = Field(ge=0)
    level: int = Field(ge=1)
    linked_heading_id: str | None = None


class TableOfContents(BaseModel):
    """A table of contents composed of ordered entries.

    Attributes:
        entries: The ordered table-of-contents entries.
    """

    entries: list[TOCEntry] = Field(default_factory=list)


class DocumentStructure(BaseModel):
    """The logical structure extracted from a document.

    Attributes:
        headings: All detected headings, in document order.
        toc: Optional table of contents.
        reading_order: Element identifiers in logical reading order.
        links: Links discovered in the document.
    """

    headings: list[Heading] = Field(default_factory=list)
    toc: TableOfContents | None = None
    reading_order: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
