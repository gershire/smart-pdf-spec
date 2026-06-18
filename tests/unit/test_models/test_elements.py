"""Unit tests for core element data models."""

import json

import pytest
from pydantic import ValidationError

from smart_pdf_scanner.models.elements import BoundingBox, Element, ElementType


class TestElementType:
    def test_values(self) -> None:
        assert ElementType.TEXT_BLOCK.value == "text_block"
        assert ElementType("heading") is ElementType.HEADING
        assert set(ElementType) == {
            ElementType.TEXT_BLOCK,
            ElementType.HEADING,
            ElementType.TABLE,
            ElementType.IMAGE,
            ElementType.CAPTION,
            ElementType.FOOTNOTE,
            ElementType.SIDEBAR,
        }


class TestBoundingBox:
    def test_dimensions_and_area(self) -> None:
        bbox = BoundingBox(x0=0, y0=0, x1=10, y1=5)
        assert bbox.width == 10
        assert bbox.height == 5
        assert bbox.area() == 50

    def test_zero_area(self) -> None:
        assert BoundingBox(x0=2, y0=2, x1=2, y1=8).area() == 0

    def test_invalid_ordering(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=10, y0=0, x1=0, y1=5)
        with pytest.raises(ValidationError):
            BoundingBox(x0=0, y0=10, x1=5, y1=0)

    def test_intersects_overlap(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=5, y0=5, x1=15, y1=15)
        assert a.intersects(b)
        assert b.intersects(a)

    def test_intersects_disjoint(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=20, y0=20, x1=30, y1=30)
        assert not a.intersects(b)

    def test_intersects_touching_edge_is_false(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=10, y0=0, x1=20, y1=10)
        assert not a.intersects(b)

    def test_contains(self) -> None:
        outer = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        inner = BoundingBox(x0=2, y0=2, x1=8, y1=8)
        assert outer.contains(inner)
        assert not inner.contains(outer)
        assert outer.contains(outer)

    def test_contains_partial_overlap_is_false(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=5, y0=5, x1=15, y1=15)
        assert not a.contains(b)

    def test_intersection_region(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=5, y0=5, x1=15, y1=15)
        overlap = a.intersection(b)
        assert overlap == BoundingBox(x0=5, y0=5, x1=10, y1=10)
        assert overlap is not None
        assert overlap.area() == 25

    def test_intersection_none_when_disjoint(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=20, y0=20, x1=30, y1=30)
        assert a.intersection(b) is None

    def test_iou(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=2, y1=2)
        b = BoundingBox(x0=1, y0=1, x1=3, y1=3)
        # intersection area = 1, union area = 4 + 4 - 1 = 7
        assert a.iou(b) == pytest.approx(1 / 7)
        assert a.iou(a) == pytest.approx(1.0)
        disjoint = BoundingBox(x0=50, y0=50, x1=60, y1=60)
        assert a.iou(disjoint) == 0.0

    def test_json_round_trip(self) -> None:
        bbox = BoundingBox(x0=1.5, y0=2.5, x1=3.5, y1=4.5)
        dumped = bbox.model_dump_json()
        restored = BoundingBox.model_validate_json(dumped)
        assert restored == bbox


class TestElement:
    def _bbox(self) -> BoundingBox:
        return BoundingBox(x0=0, y0=0, x1=10, y1=10)

    def test_construction_defaults(self) -> None:
        element = Element(
            element_id="el-1",
            element_type=ElementType.TEXT_BLOCK,
            bbox=self._bbox(),
            page_number=0,
        )
        assert element.confidence == 1.0
        assert element.element_type is ElementType.TEXT_BLOCK

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Element(
                element_id="el-1",
                element_type=ElementType.TEXT_BLOCK,
                bbox=self._bbox(),
                page_number=0,
                confidence=1.5,
            )
        with pytest.raises(ValidationError):
            Element(
                element_id="el-1",
                element_type=ElementType.TEXT_BLOCK,
                bbox=self._bbox(),
                page_number=0,
                confidence=-0.1,
            )

    def test_negative_page_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Element(
                element_id="el-1",
                element_type=ElementType.TEXT_BLOCK,
                bbox=self._bbox(),
                page_number=-1,
            )

    def test_json_round_trip(self) -> None:
        element = Element(
            element_id="el-42",
            element_type=ElementType.HEADING,
            bbox=self._bbox(),
            page_number=3,
            confidence=0.87,
        )
        dumped = element.model_dump_json()
        payload = json.loads(dumped)
        assert payload["element_type"] == "heading"
        restored = Element.model_validate_json(dumped)
        assert restored == element
