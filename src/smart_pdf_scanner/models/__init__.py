"""Data models for the Smart PDF Scanner."""

from smart_pdf_scanner.models.config import (
    Config,
    LayoutConfig,
    LLMConfig,
    OCRConfig,
    ProcessingMode,
)
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    Element,
    ElementType,
    FontInfo,
    Heading,
    Image,
    ImageType,
    Table,
    TableRow,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.models.result import ProcessingResult, ProcessingStatistics
from smart_pdf_scanner.models.structure import (
    DocumentStructure,
    Link,
    LinkType,
    TableOfContents,
    TOCEntry,
)

__all__ = [
    "BoundingBox",
    "Config",
    "Document",
    "DocumentMetadata",
    "DocumentStructure",
    "Element",
    "ElementType",
    "FontInfo",
    "Heading",
    "Image",
    "ImageType",
    "LayoutConfig",
    "LLMConfig",
    "Link",
    "LinkType",
    "OCRConfig",
    "Page",
    "PageDimensions",
    "ProcessingMode",
    "ProcessingResult",
    "ProcessingStatistics",
    "Table",
    "TableOfContents",
    "TableRow",
    "TextBlock",
    "TOCEntry",
]
