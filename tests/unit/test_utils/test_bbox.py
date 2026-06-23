"""Unit tests for :mod:`smart_pdf_scanner.utils.bbox`.

Covers geometric operations (area, intersection, union, contains, overlap_area,
IoU) and spatial-analysis helpers (overlap ratios, alignment, column detection,
reading order) including numerical edge cases.
"""

from dataclasses import dataclass

import pytest

from smart_pdf_scanner.utils import bbox


@dataclass
class Box:
    """Minimal BBoxLike stand-in used so tests don't depend on the model layer."""

    x0: float
    y0: float
    x1: float
    y1: float


# --------------------------------------------------------------------------- #
# Input handling / normalisation
# --------------------------------------------------------------------------- #


class TestCoordExtraction:
    def test_accepts_bbox_like_object(self):
        assert bbox.normalize(Box(1, 2, 3, 4)) == (1.0, 2.0, 3.0, 4.0)

    def test_accepts_tuple(self):
        assert bbox.normalize((1, 2, 3, 4)) == (1.0, 2.0, 3.0, 4.0)

    def test_accepts_list(self):
        assert bbox.normalize([1, 2, 3, 4]) == (1.0, 2.0, 3.0, 4.0)

    def test_normalizes_swapped_corners(self):
        # x1 < x0 and y1 < y0 should be reordered.
        assert bbox.normalize((3, 4, 1, 2)) == (1.0, 2.0, 3.0, 4.0)

    def test_invalid_input_raises(self):
        with pytest.raises(TypeError):
            bbox.normalize((1, 2, 3))  # wrong arity
        with pytest.raises(TypeError):
            bbox.normalize(42)  # not iterable


# --------------------------------------------------------------------------- #
# Basic measurements
# --------------------------------------------------------------------------- #


class TestMeasurements:
    def test_width_height_area(self):
        b = (0, 0, 4, 2)
        assert bbox.width(b) == 4.0
        assert bbox.height(b) == 2.0
        assert bbox.area(b) == 8.0

    def test_area_of_swapped_box_is_positive(self):
        assert bbox.area((4, 2, 0, 0)) == 8.0

    def test_zero_area(self):
        assert bbox.area((1, 1, 1, 5)) == 0.0

    def test_center(self):
        assert bbox.center((0, 0, 4, 2)) == (2.0, 1.0)


# --------------------------------------------------------------------------- #
# intersection / overlap_area / intersects
# --------------------------------------------------------------------------- #


class TestIntersection:
    def test_overlapping(self):
        assert bbox.intersection((0, 0, 4, 4), (2, 2, 6, 6)) == (2.0, 2.0, 4.0, 4.0)

    def test_disjoint_returns_none(self):
        assert bbox.intersection((0, 0, 1, 1), (5, 5, 6, 6)) is None

    def test_edge_touch_is_none(self):
        # Boxes sharing only the x=2 edge have zero-area overlap.
        assert bbox.intersection((0, 0, 2, 2), (2, 0, 4, 2)) is None

    def test_corner_touch_is_none(self):
        assert bbox.intersection((0, 0, 2, 2), (2, 2, 4, 4)) is None

    def test_contained_box(self):
        assert bbox.intersection((0, 0, 10, 10), (2, 2, 4, 4)) == (2.0, 2.0, 4.0, 4.0)

    def test_overlap_area(self):
        assert bbox.overlap_area((0, 0, 4, 4), (2, 2, 6, 6)) == 4.0

    def test_overlap_area_disjoint_is_zero(self):
        assert bbox.overlap_area((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0

    def test_intersects(self):
        assert bbox.intersects((0, 0, 4, 4), (2, 2, 6, 6)) is True
        assert bbox.intersects((0, 0, 1, 1), (5, 5, 6, 6)) is False
        assert bbox.intersects((0, 0, 2, 2), (2, 0, 4, 2)) is False


# --------------------------------------------------------------------------- #
# union / merge
# --------------------------------------------------------------------------- #


class TestUnion:
    def test_union_overlapping(self):
        assert bbox.union((0, 0, 4, 4), (2, 2, 6, 6)) == (0.0, 0.0, 6.0, 6.0)

    def test_union_disjoint(self):
        assert bbox.union((0, 0, 1, 1), (5, 5, 6, 6)) == (0.0, 0.0, 6.0, 6.0)

    def test_merge_multiple(self):
        boxes = [(0, 0, 1, 1), (2, 2, 3, 3), (-1, 5, 0, 6)]
        assert bbox.merge(boxes) == (-1.0, 0.0, 3.0, 6.0)

    def test_merge_single(self):
        assert bbox.merge([(1, 2, 3, 4)]) == (1.0, 2.0, 3.0, 4.0)

    def test_merge_empty_raises(self):
        with pytest.raises(ValueError):
            bbox.merge([])


# --------------------------------------------------------------------------- #
# contains
# --------------------------------------------------------------------------- #


class TestContains:
    def test_fully_contained(self):
        assert bbox.contains((0, 0, 10, 10), (2, 2, 4, 4)) is True

    def test_identical_boxes_contain(self):
        assert bbox.contains((0, 0, 10, 10), (0, 0, 10, 10)) is True

    def test_partial_overlap_not_contained(self):
        assert bbox.contains((0, 0, 4, 4), (2, 2, 6, 6)) is False

    def test_outside_not_contained(self):
        assert bbox.contains((0, 0, 4, 4), (5, 5, 6, 6)) is False

    def test_tolerance_absorbs_tiny_overflow(self):
        # inner exceeds outer by 1e-9, within default tolerance.
        assert bbox.contains((0, 0, 10, 10), (0, 0, 10.000000001, 10)) is True

    def test_overflow_beyond_tolerance(self):
        assert bbox.contains((0, 0, 10, 10), (0, 0, 10.5, 10)) is False


# --------------------------------------------------------------------------- #
# IoU / IoA
# --------------------------------------------------------------------------- #


class TestIoU:
    def test_identical_is_one(self):
        assert bbox.iou((0, 0, 4, 4), (0, 0, 4, 4)) == pytest.approx(1.0)

    def test_disjoint_is_zero(self):
        assert bbox.iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0

    def test_half_overlap(self):
        # a=[0,0,2,2] area 4, b=[1,0,3,2] area 4, overlap=2, union=6
        assert bbox.iou((0, 0, 2, 2), (1, 0, 3, 2)) == pytest.approx(2.0 / 6.0)

    def test_zero_area_boxes(self):
        assert bbox.iou((0, 0, 0, 0), (0, 0, 0, 0)) == 0.0

    def test_ioa_full_containment(self):
        # all of the small box is covered by the big one.
        assert bbox.ioa((2, 2, 4, 4), (0, 0, 10, 10)) == pytest.approx(1.0)

    def test_ioa_half(self):
        assert bbox.ioa((0, 0, 2, 2), (1, 0, 3, 2)) == pytest.approx(0.5)

    def test_ioa_zero_area(self):
        assert bbox.ioa((1, 1, 1, 1), (0, 0, 10, 10)) == 0.0


# --------------------------------------------------------------------------- #
# Overlap ratios and alignment
# --------------------------------------------------------------------------- #


class TestOverlapHelpers:
    def test_horizontal_overlap(self):
        assert bbox.horizontal_overlap((0, 0, 4, 1), (2, 5, 6, 6)) == 2.0

    def test_horizontal_overlap_none(self):
        assert bbox.horizontal_overlap((0, 0, 1, 1), (5, 0, 6, 1)) == 0.0

    def test_vertical_overlap(self):
        assert bbox.vertical_overlap((0, 0, 1, 4), (5, 2, 6, 6)) == 2.0

    def test_horizontal_overlap_ratio(self):
        # narrower box width 2 fully spanned -> 1.0
        assert bbox.horizontal_overlap_ratio((0, 0, 10, 1), (3, 0, 5, 1)) == pytest.approx(1.0)

    def test_vertical_overlap_ratio_partial(self):
        # a covers y[0,4], b covers y[2,6]; shorter height 4, overlap 2 -> 0.5
        assert bbox.vertical_overlap_ratio((0, 0, 1, 4), (0, 2, 1, 6)) == pytest.approx(0.5)

    def test_overlap_ratio_zero_dimension(self):
        assert bbox.horizontal_overlap_ratio((0, 0, 0, 1), (0, 0, 0, 1)) == 0.0

    def test_is_left_of(self):
        assert bbox.is_left_of((0, 0, 2, 2), (3, 0, 5, 2)) is True
        assert bbox.is_left_of((3, 0, 5, 2), (0, 0, 2, 2)) is False

    def test_is_above_top_down(self):
        # smaller y is higher; a above b
        assert bbox.is_above((0, 0, 2, 2), (0, 3, 2, 5)) is True
        assert bbox.is_above((0, 3, 2, 5), (0, 0, 2, 2)) is False

    def test_same_row(self):
        assert bbox.same_row((0, 0, 2, 2), (3, 0, 5, 2)) is True
        assert bbox.same_row((0, 0, 2, 2), (3, 10, 5, 12)) is False

    def test_same_column(self):
        assert bbox.same_column((0, 0, 2, 2), (0, 5, 2, 7)) is True
        assert bbox.same_column((0, 0, 2, 2), (10, 5, 12, 7)) is False


# --------------------------------------------------------------------------- #
# Column detection
# --------------------------------------------------------------------------- #


class TestColumnDetection:
    def test_empty(self):
        assert bbox.detect_columns([]) == []

    def test_single_column(self):
        boxes = [(0, 0, 100, 10), (0, 20, 100, 30), (0, 40, 100, 50)]
        cols = bbox.detect_columns(boxes)
        assert len(cols) == 1
        assert cols[0] == (0.0, 0.0, 100.0, 0.0)

    def test_two_columns(self):
        boxes = [
            (0, 0, 40, 10),
            (0, 20, 40, 30),
            (60, 0, 100, 10),
            (60, 20, 100, 30),
        ]
        cols = bbox.detect_columns(boxes)
        assert len(cols) == 2
        assert cols[0][0] == 0.0 and cols[0][2] == 40.0
        assert cols[1][0] == 60.0 and cols[1][2] == 100.0

    def test_small_gap_merged(self):
        # Two spans separated by a tiny gap relative to width -> merged.
        boxes = [(0, 0, 49, 10), (50, 0, 100, 10)]
        cols = bbox.detect_columns(boxes, min_gap_ratio=0.05)
        assert len(cols) == 1

    def test_assign_to_column(self):
        cols = [(0.0, 0.0, 40.0, 0.0), (60.0, 0.0, 100.0, 0.0)]
        assert bbox.assign_to_column((0, 0, 40, 10), cols) == 0
        assert bbox.assign_to_column((60, 0, 100, 10), cols) == 1

    def test_assign_to_column_no_overlap_uses_nearest(self):
        cols = [(0.0, 0.0, 40.0, 0.0), (60.0, 0.0, 100.0, 0.0)]
        # box centred near the right column though not overlapping span exactly
        assert bbox.assign_to_column((45, 0, 55, 10), cols) in (0, 1)

    def test_assign_to_column_empty_columns(self):
        assert bbox.assign_to_column((0, 0, 1, 1), []) == 0


# --------------------------------------------------------------------------- #
# Reading order
# --------------------------------------------------------------------------- #


class TestReadingOrder:
    def test_empty(self):
        assert bbox.sort_by_reading_order([]) == []

    def test_single_column_top_to_bottom(self):
        boxes = [
            Box(0, 40, 100, 50),
            Box(0, 0, 100, 10),
            Box(0, 20, 100, 30),
        ]
        ordered = bbox.sort_by_reading_order(boxes)
        tops = [b.y0 for b in ordered]
        assert tops == [0, 20, 40]

    def test_same_line_left_to_right(self):
        # Two boxes on the same line should be ordered by x.
        boxes = [Box(50, 0, 60, 10), Box(0, 0, 10, 10)]
        ordered = bbox.sort_by_reading_order(boxes, detect_cols=False)
        assert ordered[0].x0 == 0
        assert ordered[1].x0 == 50

    def test_two_column_reading_order(self):
        # Left column read fully before right column.
        left_top = Box(0, 0, 40, 10)
        left_bottom = Box(0, 50, 40, 60)
        right_top = Box(60, 0, 100, 10)
        right_bottom = Box(60, 50, 100, 60)
        boxes = [right_top, left_bottom, right_bottom, left_top]
        ordered = bbox.sort_by_reading_order(boxes)
        assert ordered == [left_top, left_bottom, right_top, right_bottom]

    def test_with_key_callable(self):
        items = [
            {"id": "c", "box": Box(0, 40, 10, 50)},
            {"id": "a", "box": Box(0, 0, 10, 10)},
            {"id": "b", "box": Box(0, 20, 10, 30)},
        ]
        ordered = bbox.sort_by_reading_order(items, key=lambda it: it["box"], detect_cols=False)
        assert [it["id"] for it in ordered] == ["a", "b", "c"]

    def test_stable_for_equal_positions(self):
        # Identical boxes keep input order (stable sort).
        b1 = Box(0, 0, 10, 10)
        b2 = Box(0, 0, 10, 10)
        ordered = bbox.sort_by_reading_order([b1, b2], detect_cols=False)
        assert ordered[0] is b1 and ordered[1] is b2

    def test_reading_order_key_banding(self):
        # Boxes within row_quantum of each other share a band and sort by x.
        k1 = bbox.reading_order_key((10, 100, 20, 110), row_quantum=20)
        k2 = bbox.reading_order_key((0, 105, 10, 115), row_quantum=20)
        # same band (100/20=5, 105/20≈5) -> compare by x: k2 (x0=0) before k1
        assert k2 < k1
