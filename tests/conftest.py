"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
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


# ---------------------------------------------------------------------------
# Primitive fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config() -> Config:
    return Config()


@pytest.fixture
def sample_bbox() -> BoundingBox:
    return BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)


@pytest.fixture
def sample_metadata() -> DocumentMetadata:
    return DocumentMetadata(title="Test PDF", page_count=1, file_size_bytes=1024)


# ---------------------------------------------------------------------------
# Element fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def text_block() -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=50.0, y0=50.0, x1=400.0, y1=100.0),
        page_number=0,
        text="Hello, world!",
        font_info=FontInfo(name="Helvetica", size=12.0, weight="normal", style="normal"),
    )


@pytest.fixture
def heading_element() -> Heading:
    return Heading(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.HEADING,
        bbox=BoundingBox(x0=50.0, y0=20.0, x1=400.0, y1=60.0),
        page_number=0,
        text="Introduction",
        font_info=FontInfo(name="Helvetica-Bold", size=24.0, weight="bold", style="normal"),
        level=1,
    )


@pytest.fixture
def table_element() -> Table:
    rows = [
        TableRow(cells=["Name", "Age", "City"]),
        TableRow(cells=["Alice", "30", "London"]),
        TableRow(cells=["Bob", "25", "Paris"]),
    ]
    return Table(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TABLE,
        bbox=BoundingBox(x0=50.0, y0=200.0, x1=400.0, y1=300.0),
        page_number=0,
        rows=rows,
        markdown="| Name | Age | City |\n| --- | --- | --- |\n| Alice | 30 | London |\n| Bob | 25 | Paris |",
    )


@pytest.fixture
def image_element(tmp_path: Path) -> Image:
    img_path = tmp_path / "test_img.png"
    from PIL import Image as PILImage
    PILImage.new("RGB", (100, 100), color="white").save(str(img_path))
    return Image(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.IMAGE,
        bbox=BoundingBox(x0=50.0, y0=300.0, x1=300.0, y1=500.0),
        page_number=0,
        image_path=img_path,
        image_type=ImageType.PHOTOGRAPH,
        description="A test image",
    )


# ---------------------------------------------------------------------------
# Page / Document fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_page(text_block: TextBlock) -> Page:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    page.add_element(text_block)
    return page


@pytest.fixture
def empty_page() -> Page:
    return Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))


@pytest.fixture
def sample_document(tmp_path: Path, sample_metadata: DocumentMetadata, sample_page: Page) -> Document:
    doc = Document(
        metadata=sample_metadata,
        assets_folder=tmp_path / "assets",
    )
    doc.add_page(sample_page)
    return doc


@pytest.fixture
def empty_document(tmp_path: Path, sample_metadata: DocumentMetadata) -> Document:
    return Document(
        metadata=sample_metadata,
        assets_folder=tmp_path / "assets",
    )


# ---------------------------------------------------------------------------
# PDF file fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF with text using PyMuPDF."""
    import fitz

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Test Document Title", fontsize=24)
    page.insert_text((72, 150), "This is the first paragraph of text.", fontsize=12)
    page.insert_text((72, 175), "This is the second paragraph of text.", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def simple_image_file(tmp_path: Path) -> Path:
    """Create a simple PNG image file."""
    from PIL import Image as PILImage

    img_path = tmp_path / "test_image.png"
    img = PILImage.new("RGB", (200, 100), color=(128, 128, 128))
    img.save(str(img_path))
    return img_path
