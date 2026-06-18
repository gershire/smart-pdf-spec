"""Unit tests for concrete element subclasses."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

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


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0, y0=0, x1=10, y1=10)


class TestFontInfo:
    def test_construction(self) -> None:
        font = FontInfo(name="Helvetica", size=12.0, weight="bold", style="italic")
        assert font.name == "Helvetica"
        assert font.size == 12.0

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            FontInfo(name="Helvetica", size=12.0)  # type: ignore[call-arg]


class TestTextBlock:
    def test_inherits_element(self) -> None:
        block = TextBlock(element_id="t1", bbox=_bbox(), page_number=0, text="hello")
        assert isinstance(block, Element)
        assert block.element_type is ElementType.TEXT_BLOCK
        assert block.reading_order == 0
        assert block.font_info is None
        assert block.hierarchy_level is None

    def test_with_font_info(self) -> None:
        block = TextBlock(
            element_id="t1",
            bbox=_bbox(),
            page_number=1,
            text="styled",
            font_info=FontInfo(name="Arial", size=10.0, weight="normal", style="normal"),
            reading_order=3,
            hierarchy_level=2,
        )
        assert block.font_info is not None
        assert block.font_info.name == "Arial"
        assert block.reading_order == 3

    def test_text_required(self) -> None:
        with pytest.raises(ValidationError):
            TextBlock(element_id="t1", bbox=_bbox(), page_number=0)  # type: ignore[call-arg]


class TestHeading:
    def test_inherits_textblock(self) -> None:
        heading = Heading(element_id="h1", bbox=_bbox(), page_number=0, text="Title", level=1)
        assert isinstance(heading, TextBlock)
        assert isinstance(heading, Element)
        assert heading.element_type is ElementType.HEADING

    @pytest.mark.parametrize("level", [0, 7, -1])
    def test_level_out_of_range(self, level: int) -> None:
        with pytest.raises(ValidationError):
            Heading(element_id="h1", bbox=_bbox(), page_number=0, text="Title", level=level)

    @pytest.mark.parametrize("level", [1, 3, 6])
    def test_level_in_range(self, level: int) -> None:
        heading = Heading(element_id="h1", bbox=_bbox(), page_number=0, text="T", level=level)
        assert heading.level == level


class TestTable:
    def test_construction(self) -> None:
        table = Table(
            element_id="tbl1",
            bbox=_bbox(),
            page_number=0,
            rows=[TableRow(cells=["a", "b"]), TableRow(cells=["c", "d"])],
            headers=["col1", "col2"],
            markdown="| col1 | col2 |\n| --- | --- |\n| a | b |\n| c | d |",
        )
        assert table.element_type is ElementType.TABLE
        assert len(table.rows) == 2
        assert table.rows[0].cells == ["a", "b"]
        assert table.csv_path is None

    def test_csv_path_coerced_to_path(self) -> None:
        table = Table(
            element_id="tbl1",
            bbox=_bbox(),
            page_number=0,
            rows=[],
            markdown="",
            csv_path="assets/table.csv",
        )
        assert isinstance(table.csv_path, Path)

    def test_markdown_required(self) -> None:
        with pytest.raises(ValidationError):
            Table(element_id="tbl1", bbox=_bbox(), page_number=0, rows=[])  # type: ignore[call-arg]


class TestImage:
    def test_construction(self) -> None:
        image = Image(
            element_id="img1",
            bbox=_bbox(),
            page_number=0,
            image_path="assets/img1.png",
            image_type=ImageType.PHOTOGRAPH,
            description="A photo",
        )
        assert image.element_type is ElementType.IMAGE
        assert isinstance(image.image_path, Path)
        assert image.ocr_text is None

    def test_invalid_image_type(self) -> None:
        with pytest.raises(ValidationError):
            Image(
                element_id="img1",
                bbox=_bbox(),
                page_number=0,
                image_path="assets/img1.png",
                image_type="invalid",  # type: ignore[arg-type]
                description="x",
            )


class TestSerialization:
    def test_heading_json_round_trip(self) -> None:
        heading = Heading(
            element_id="h1",
            bbox=_bbox(),
            page_number=2,
            text="Chapter 1",
            level=1,
        )
        dumped = heading.model_dump_json()
        payload = json.loads(dumped)
        assert payload["element_type"] == "heading"
        assert payload["level"] == 1
        restored = Heading.model_validate_json(dumped)
        assert restored == heading

    def test_image_json_round_trip(self) -> None:
        image = Image(
            element_id="img1",
            bbox=_bbox(),
            page_number=0,
            image_path="assets/img1.png",
            image_type=ImageType.CHART,
            description="bar chart",
            caption="Figure 1",
        )
        restored = Image.model_validate_json(image.model_dump_json())
        assert restored == image
        assert restored.image_type is ImageType.CHART
