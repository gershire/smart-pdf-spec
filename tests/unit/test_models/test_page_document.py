"""Unit tests for Page and Document models (task 1.4)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    Element,
    ElementType,
    Heading,
    Image,
    ImageType,
    Table,
    TableRow,
    TextBlock,
)
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0, y0=0, x1=10, y1=10)


def _text(element_id: str = "t1") -> TextBlock:
    return TextBlock(element_id=element_id, bbox=_bbox(), page_number=0, text="hello")


def _metadata() -> DocumentMetadata:
    return DocumentMetadata(page_count=1, file_size_bytes=1024)


def test_page_defaults() -> None:
    page = Page(page_number=0, dimensions=PageDimensions(width=612, height=792))
    assert page.elements == []
    assert page.is_image_based is False
    assert page.ocr_confidence is None


def test_page_add_and_filter_elements() -> None:
    page = Page(page_number=1, dimensions=PageDimensions(width=612, height=792))
    block = _text("a")
    page.add_element(block)
    assert page.elements == [block]
    assert page.get_elements_by_type(ElementType.TEXT_BLOCK) == [block]
    assert page.get_elements_by_type(ElementType.TABLE) == []


def test_page_ocr_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        Page(
            page_number=0,
            dimensions=PageDimensions(width=10, height=10),
            ocr_confidence=1.5,
        )


def test_page_dimensions_non_negative() -> None:
    with pytest.raises(ValidationError):
        PageDimensions(width=-1, height=10)


def test_document_add_and_get_page() -> None:
    doc = Document(metadata=_metadata(), assets_folder=Path("assets"))
    page = Page(page_number=3, dimensions=PageDimensions(width=1, height=1))
    doc.add_page(page)
    assert doc.get_page(3) is page
    assert doc.get_page(99) is None


def test_document_get_all_elements_in_page_order() -> None:
    doc = Document(metadata=_metadata(), assets_folder=Path("assets"))
    page0 = Page(page_number=0, dimensions=PageDimensions(width=1, height=1))
    page1 = Page(page_number=1, dimensions=PageDimensions(width=1, height=1))
    page0.add_element(_text("a"))
    page1.add_element(_text("b"))
    page1.add_element(_text("c"))
    doc.add_page(page0)
    doc.add_page(page1)
    ids = [el.element_id for el in doc.get_all_elements()]
    assert ids == ["a", "b", "c"]


def test_document_assets_folder_path_coercion() -> None:
    doc = Document(metadata=_metadata(), assets_folder="out/assets")
    assert doc.assets_folder == Path("out/assets")


def test_document_json_round_trip() -> None:
    doc = Document(metadata=_metadata(), assets_folder=Path("assets"))
    page = Page(page_number=0, dimensions=PageDimensions(width=612, height=792))
    page.add_element(_text("a"))
    doc.add_page(page)

    restored = Document.model_validate(json.loads(doc.model_dump_json()))
    assert restored.metadata == doc.metadata
    assert restored.assets_folder == doc.assets_folder
    assert len(restored.pages) == 1
    assert restored.pages[0].dimensions == page.dimensions
    element = restored.get_all_elements()[0]
    assert element.element_id == "a"
    assert element.element_type == ElementType.TEXT_BLOCK
    # Subclass identity and fields must survive the round trip, not downcast
    # to the bare Element base (which would silently drop ``text``).
    assert isinstance(element, TextBlock)
    assert element.text == "hello"


def test_page_mixed_element_round_trip_preserves_subtypes() -> None:
    """Every concrete element subtype survives a serialization round trip.

    The page element field is a discriminated union, so each element is
    reconstructed as its concrete class (with its subclass-specific fields)
    rather than collapsing to the ``Element`` base. Element types without a
    dedicated subclass (e.g. caption) fall back to ``Element``.
    """
    page = Page(page_number=0, dimensions=PageDimensions(width=612, height=792))
    page.add_element(TextBlock(element_id="t1", bbox=_bbox(), page_number=0, text="body"))
    page.add_element(
        Heading(element_id="h1", bbox=_bbox(), page_number=0, text="Title", level=2)
    )
    page.add_element(
        Table(
            element_id="tb1",
            bbox=_bbox(),
            page_number=0,
            rows=[TableRow(cells=["a", "b"])],
            markdown="|a|b|",
        )
    )
    page.add_element(
        Image(
            element_id="i1",
            bbox=_bbox(),
            page_number=0,
            image_path=Path("img.png"),
            image_type=ImageType.CHART,
            description="chart",
        )
    )
    page.add_element(
        Element(
            element_id="c1",
            element_type=ElementType.CAPTION,
            bbox=_bbox(),
            page_number=0,
        )
    )

    restored = Page.model_validate(json.loads(page.model_dump_json()))
    text, heading, table, image, caption = restored.elements

    assert isinstance(text, TextBlock) and text.text == "body"
    assert isinstance(heading, Heading) and heading.level == 2
    assert isinstance(table, Table) and table.rows[0].cells == ["a", "b"]
    assert isinstance(image, Image) and image.image_type == ImageType.CHART
    # Subclass-less types fall back to the Element base.
    assert type(caption) is Element
    assert caption.element_type == ElementType.CAPTION
