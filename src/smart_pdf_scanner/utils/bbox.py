"""Bounding box geometry and spatial analysis utilities.

This module provides pure-Python geometric operations on bounding boxes
(intersection, union, containment, overlap area, IoU) and higher-level
spatial-analysis helpers used to determine reading order and detect column
layouts.

All functions operate on *bounding-box-like* values, i.e. any object exposing
floating-point ``x0``, ``y0``, ``x1`` and ``y1`` attributes (such as the
:class:`~smart_pdf_scanner.models.elements.BoundingBox` Pydantic model) **or** a
4-tuple/list ``(x0, y0, x1, y1)``. Keeping the helpers structurally typed avoids
a hard dependency on the model layer and makes the utilities trivially testable.

Coordinate convention
----------------------
Coordinates follow the layout-analysis convention from Requirement 3: ``(x0, y0)``
is the top-left corner and ``(x1, y1)`` is the bottom-right corner, with the
*y* axis increasing downward (the convention used by PyMuPDF/pdfplumber text
extraction). Inputs are normalised internally so that ``x0 <= x1`` and
``y0 <= y1`` regardless of the order supplied.

These helpers back Requirement 3 (Layout Analysis) and Requirement 5 (Structure
Recognition — reading-order determination and column detection).
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Sequence, Tuple, TypeVar, Union, runtime_checkable

__all__ = [
    "BBoxLike",
    "Coords",
    "normalize",
    "width",
    "height",
    "area",
    "center",
    "intersection",
    "union",
    "merge",
    "overlap_area",
    "intersects",
    "contains",
    "iou",
    "ioa",
    "horizontal_overlap",
    "vertical_overlap",
    "horizontal_overlap_ratio",
    "vertical_overlap_ratio",
    "is_left_of",
    "is_above",
    "same_row",
    "same_column",
    "reading_order_key",
    "detect_columns",
    "assign_to_column",
    "sort_by_reading_order",
]


@runtime_checkable
class BBoxLike(Protocol):
    """Structural protocol for any object that exposes bbox coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float


#: A bounding box expressed as a normalised ``(x0, y0, x1, y1)`` tuple.
Coords = Tuple[float, float, float, float]

#: Anything accepted as a bounding box input: a :class:`BBoxLike` object or a
#: 4-element sequence of coordinates.
BBoxInput = Union[BBoxLike, Sequence[float]]

T = TypeVar("T")

# Default absolute tolerance for floating-point comparisons. Coordinates are
# typically in PDF points (1/72 inch), so values well below a pixel are noise.
_EPS = 1e-6


def _coords(box: BBoxInput) -> Coords:
    """Extract normalised ``(x0, y0, x1, y1)`` coordinates from any bbox input.

    Args:
        box: A :class:`BBoxLike` object or a 4-element sequence of coordinates.

    Returns:
        Normalised coordinates where ``x0 <= x1`` and ``y0 <= y1``.

    Raises:
        TypeError: If ``box`` is neither bbox-like nor a 4-element sequence.
    """
    if isinstance(box, BBoxLike):
        x0, y0, x1, y1 = box.x0, box.y0, box.x1, box.y1
    else:
        try:
            x0, y0, x1, y1 = box  # type: ignore[misc]
        except (ValueError, TypeError) as exc:
            raise TypeError(
                "Expected a bbox-like object with x0/y0/x1/y1 attributes "
                "or a 4-element (x0, y0, x1, y1) sequence; "
                f"got {box!r}"
            ) from exc
    return _normalize_coords(float(x0), float(y0), float(x1), float(y1))


def _normalize_coords(x0: float, y0: float, x1: float, y1: float) -> Coords:
    """Order coordinates so the box has non-negative width and height."""
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def normalize(box: BBoxInput) -> Coords:
    """Return the normalised ``(x0, y0, x1, y1)`` coordinates of ``box``.

    Normalisation guarantees ``x0 <= x1`` and ``y0 <= y1``, fixing boxes whose
    corners were supplied in an unexpected order.
    """
    return _coords(box)


def width(box: BBoxInput) -> float:
    """Return the width (``x1 - x0``) of ``box``; always non-negative."""
    x0, _, x1, _ = _coords(box)
    return x1 - x0


def height(box: BBoxInput) -> float:
    """Return the height (``y1 - y0``) of ``box``; always non-negative."""
    _, y0, _, y1 = _coords(box)
    return y1 - y0


def area(box: BBoxInput) -> float:
    """Return the area of ``box`` (``width * height``); always non-negative."""
    x0, y0, x1, y1 = _coords(box)
    return (x1 - x0) * (y1 - y0)


def center(box: BBoxInput) -> Tuple[float, float]:
    """Return the ``(cx, cy)`` centre point of ``box``."""
    x0, y0, x1, y1 = _coords(box)
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def intersection(a: BBoxInput, b: BBoxInput) -> Optional[Coords]:
    """Return the overlapping rectangle of ``a`` and ``b``, or ``None``.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        The intersection as ``(x0, y0, x1, y1)``, or ``None`` if the boxes do
        not overlap. Boxes that merely touch along an edge or corner (zero-area
        overlap) are treated as non-intersecting and yield ``None``.
    """
    ax0, ay0, ax1, ay1 = _coords(a)
    bx0, by0, bx1, by1 = _coords(b)

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    if ix1 - ix0 <= _EPS or iy1 - iy0 <= _EPS:
        return None
    return (ix0, iy0, ix1, iy1)


def union(a: BBoxInput, b: BBoxInput) -> Coords:
    """Return the smallest box enclosing both ``a`` and ``b``."""
    ax0, ay0, ax1, ay1 = _coords(a)
    bx0, by0, bx1, by1 = _coords(b)
    return (min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1))


def merge(boxes: Sequence[BBoxInput]) -> Coords:
    """Return the smallest box enclosing every box in ``boxes``.

    Args:
        boxes: A non-empty sequence of bounding boxes.

    Returns:
        The enclosing ``(x0, y0, x1, y1)`` rectangle.

    Raises:
        ValueError: If ``boxes`` is empty.
    """
    if not boxes:
        raise ValueError("merge() requires at least one bounding box")
    x0, y0, x1, y1 = _coords(boxes[0])
    for box in boxes[1:]:
        bx0, by0, bx1, by1 = _coords(box)
        x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
    return (x0, y0, x1, y1)


def overlap_area(a: BBoxInput, b: BBoxInput) -> float:
    """Return the area of overlap between ``a`` and ``b`` (``0.0`` if disjoint)."""
    inter = intersection(a, b)
    if inter is None:
        return 0.0
    ix0, iy0, ix1, iy1 = inter
    return (ix1 - ix0) * (iy1 - iy0)


def intersects(a: BBoxInput, b: BBoxInput) -> bool:
    """Return ``True`` if ``a`` and ``b`` share positive-area overlap."""
    return intersection(a, b) is not None


def contains(outer: BBoxInput, inner: BBoxInput, *, tol: float = _EPS) -> bool:
    """Return ``True`` if ``outer`` fully contains ``inner``.

    Args:
        outer: The candidate containing box.
        inner: The candidate contained box.
        tol: Absolute tolerance allowing ``inner`` to exceed ``outer`` edges by
            a tiny amount (to absorb floating-point noise).

    Returns:
        ``True`` when every edge of ``inner`` lies within ``outer`` (within
        ``tol``).
    """
    ox0, oy0, ox1, oy1 = _coords(outer)
    ix0, iy0, ix1, iy1 = _coords(inner)
    return (
        ix0 >= ox0 - tol
        and iy0 >= oy0 - tol
        and ix1 <= ox1 + tol
        and iy1 <= oy1 + tol
    )


def iou(a: BBoxInput, b: BBoxInput) -> float:
    """Return the Intersection-over-Union of ``a`` and ``b`` in ``[0.0, 1.0]``.

    The union of two zero-area boxes is ``0``; in that degenerate case ``0.0``
    is returned to avoid division by zero.
    """
    inter = overlap_area(a, b)
    if inter <= 0.0:
        return 0.0
    union_area = area(a) + area(b) - inter
    if union_area <= 0.0:
        return 0.0
    return inter / union_area


def ioa(a: BBoxInput, b: BBoxInput) -> float:
    """Return Intersection-over-Area of ``a``: ``overlap / area(a)``.

    Useful for asking "what fraction of ``a`` is covered by ``b``?" — e.g.
    deciding whether a small element effectively sits inside a larger region.
    Returns ``0.0`` when ``a`` has zero area.
    """
    a_area = area(a)
    if a_area <= 0.0:
        return 0.0
    return overlap_area(a, b) / a_area


# --------------------------------------------------------------------------- #
# Spatial-analysis helpers (reading order, columns, alignment)
# --------------------------------------------------------------------------- #


def horizontal_overlap(a: BBoxInput, b: BBoxInput) -> float:
    """Return the length of the horizontal (x-axis) overlap of ``a`` and ``b``.

    Returns ``0.0`` when the x-projections do not overlap.
    """
    ax0, _, ax1, _ = _coords(a)
    bx0, _, bx1, _ = _coords(b)
    return max(0.0, min(ax1, bx1) - max(ax0, bx0))


def vertical_overlap(a: BBoxInput, b: BBoxInput) -> float:
    """Return the length of the vertical (y-axis) overlap of ``a`` and ``b``.

    Returns ``0.0`` when the y-projections do not overlap.
    """
    _, ay0, _, ay1 = _coords(a)
    _, by0, _, by1 = _coords(b)
    return max(0.0, min(ay1, by1) - max(ay0, by0))


def horizontal_overlap_ratio(a: BBoxInput, b: BBoxInput) -> float:
    """Return horizontal overlap normalised by the narrower box's width.

    The ratio is in ``[0.0, 1.0]``: ``1.0`` means the narrower box is fully
    spanned horizontally by the wider one. Returns ``0.0`` if either box has
    zero width.
    """
    overlap = horizontal_overlap(a, b)
    if overlap <= 0.0:
        return 0.0
    min_width = min(width(a), width(b))
    if min_width <= 0.0:
        return 0.0
    return min(1.0, overlap / min_width)


def vertical_overlap_ratio(a: BBoxInput, b: BBoxInput) -> float:
    """Return vertical overlap normalised by the shorter box's height.

    The ratio is in ``[0.0, 1.0]``: ``1.0`` means the shorter box is fully
    spanned vertically by the taller one. Returns ``0.0`` if either box has
    zero height.
    """
    overlap = vertical_overlap(a, b)
    if overlap <= 0.0:
        return 0.0
    min_height = min(height(a), height(b))
    if min_height <= 0.0:
        return 0.0
    return min(1.0, overlap / min_height)


def is_left_of(a: BBoxInput, b: BBoxInput, *, tol: float = _EPS) -> bool:
    """Return ``True`` if ``a`` lies entirely to the left of ``b``."""
    _, _, ax1, _ = _coords(a)
    bx0, _, _, _ = _coords(b)
    return ax1 <= bx0 + tol


def is_above(a: BBoxInput, b: BBoxInput, *, tol: float = _EPS) -> bool:
    """Return ``True`` if ``a`` lies entirely above ``b``.

    "Above" follows the top-down convention: smaller *y* is higher on the page,
    so ``a`` is above ``b`` when ``a``'s bottom edge is at or above ``b``'s top.
    """
    _, _, _, ay1 = _coords(a)
    _, by0, _, _ = _coords(b)
    return ay1 <= by0 + tol


def same_row(a: BBoxInput, b: BBoxInput, *, min_ratio: float = 0.5) -> bool:
    """Return ``True`` if ``a`` and ``b`` share a row (sufficient vertical overlap).

    Args:
        a: First bounding box.
        b: Second bounding box.
        min_ratio: Minimum :func:`vertical_overlap_ratio` (relative to the
            shorter box) required to consider the boxes on the same line.
    """
    return vertical_overlap_ratio(a, b) >= min_ratio


def same_column(a: BBoxInput, b: BBoxInput, *, min_ratio: float = 0.5) -> bool:
    """Return ``True`` if ``a`` and ``b`` share a column (horizontal overlap)."""
    return horizontal_overlap_ratio(a, b) >= min_ratio


def reading_order_key(
    box: BBoxInput,
    *,
    column: int = 0,
    row_quantum: float = 0.0,
) -> Tuple[float, float, float]:
    """Return a sort key approximating natural reading order for ``box``.

    The key sorts by column (left-to-right reading of columns), then top-to-bottom,
    then left-to-right within a line. ``row_quantum`` snaps the vertical position
    to a grid so that boxes whose tops differ by less than ``row_quantum`` are
    treated as being on the same line and ordered left-to-right.

    Args:
        box: The bounding box to derive a key for.
        column: The column index the box belongs to (see :func:`detect_columns`).
            Pass ``0`` for single-column documents.
        row_quantum: Vertical band size for grouping boxes into lines. ``0``
            disables snapping (pure top position is used).

    Returns:
        A ``(column, banded_top, left)`` tuple suitable for :func:`sorted`.
    """
    x0, y0, _, _ = _coords(box)
    if row_quantum > 0.0:
        banded_top = round(y0 / row_quantum)
    else:
        banded_top = y0
    return (float(column), float(banded_top), x0)


def detect_columns(
    boxes: Sequence[BBoxInput],
    *,
    min_gap_ratio: float = 0.05,
) -> List[Coords]:
    """Detect column boundaries by clustering boxes on horizontal overlap.

    Boxes are grouped greedily: any two boxes whose x-projections overlap are
    placed in the same column. Each resulting column is returned as the
    horizontal span ``(x0, 0.0, x1, 0.0)`` covered by its members, sorted
    left-to-right.

    Args:
        boxes: The bounding boxes on a page.
        min_gap_ratio: Minimum horizontal gap between adjacent column spans,
            expressed as a fraction of the total content width, required to keep
            them as separate columns. Columns separated by a smaller gap are
            merged. Prevents over-segmenting justified text into spurious
            columns.

    Returns:
        A list of column spans ``(x0, 0.0, x1, 0.0)`` ordered left-to-right.
        Empty input yields an empty list.
    """
    spans: List[List[float]] = []  # each entry: [x0, x1]
    for box in boxes:
        bx0, _, bx1, _ = _coords(box)
        spans.append([bx0, bx1])
    if not spans:
        return []

    # Sort by left edge and greedily merge spans that overlap horizontally.
    spans.sort(key=lambda s: s[0])
    merged: List[List[float]] = [spans[0][:]]
    for bx0, bx1 in spans[1:]:
        last = merged[-1]
        if bx0 <= last[1]:  # overlap -> same column
            last[1] = max(last[1], bx1)
        else:
            merged.append([bx0, bx1])

    # Merge columns whose horizontal gap is below the configured threshold.
    total_width = merged[-1][1] - merged[0][0]
    if total_width > 0.0 and len(merged) > 1:
        min_gap = total_width * min_gap_ratio
        collapsed: List[List[float]] = [merged[0][:]]
        for col in merged[1:]:
            gap = col[0] - collapsed[-1][1]
            if gap < min_gap:
                collapsed[-1][1] = max(collapsed[-1][1], col[1])
            else:
                collapsed.append(col[:])
        merged = collapsed

    return [(x0, 0.0, x1, 0.0) for x0, x1 in merged]


def assign_to_column(box: BBoxInput, columns: Sequence[Coords]) -> int:
    """Return the index of the column ``box`` belongs to.

    The box is assigned to the column with the greatest horizontal overlap; ties
    and zero-overlap boxes fall back to the column whose span is nearest the
    box's horizontal centre.

    Args:
        box: The bounding box to place.
        columns: Column spans from :func:`detect_columns`, ordered left-to-right.

    Returns:
        The 0-based column index, or ``0`` when ``columns`` is empty.
    """
    if not columns:
        return 0

    best_idx = 0
    best_overlap = -1.0
    for idx, col in enumerate(columns):
        ov = horizontal_overlap(box, col)
        if ov > best_overlap:
            best_overlap = ov
            best_idx = idx

    if best_overlap > 0.0:
        return best_idx

    # No horizontal overlap with any column: assign to the nearest by centre.
    cx, _ = center(box)
    nearest_idx = 0
    nearest_dist = float("inf")
    for idx, (x0, _, x1, _) in enumerate(columns):
        col_center = (x0 + x1) / 2.0
        dist = abs(cx - col_center)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_idx = idx
    return nearest_idx


def sort_by_reading_order(
    items: Sequence[T],
    *,
    key=None,
    detect_cols: bool = True,
    row_quantum: Optional[float] = None,
    min_gap_ratio: float = 0.05,
) -> List[T]:
    """Sort ``items`` into natural reading order using spatial analysis.

    Implements the Requirement 5 reading-order strategy: detect columns, then
    read each column top-to-bottom and lines within a column left-to-right.

    Args:
        items: The items to order. Each item must be bbox-like, or ``key`` must
            map it to a bbox-like value.
        key: Optional callable mapping an item to its bounding box. Defaults to
            treating each item as its own bounding box.
        detect_cols: When ``True`` (default), columns are detected and items are
            grouped column-by-column. When ``False`` all items are treated as a
            single column (pure top-to-bottom, left-to-right).
        row_quantum: Vertical band size for grouping boxes into lines. When
            ``None`` it is auto-estimated as the median box height, which keeps
            words/lines at the same vertical position ordered left-to-right.
        min_gap_ratio: Passed through to :func:`detect_columns`.

    Returns:
        A new list containing ``items`` in reading order. Input order is
        preserved for items that compare equal (stable sort).
    """
    if not items:
        return []

    get_box = key if key is not None else (lambda item: item)
    boxes = [get_box(item) for item in items]

    if row_quantum is None:
        heights = sorted(height(b) for b in boxes)
        mid = len(heights) // 2
        median_height = (
            heights[mid]
            if len(heights) % 2 == 1
            else (heights[mid - 1] + heights[mid]) / 2.0
        )
        row_quantum = median_height if median_height > 0.0 else 0.0

    if detect_cols:
        columns = detect_columns(boxes, min_gap_ratio=min_gap_ratio)
        col_of = [assign_to_column(b, columns) for b in boxes]
    else:
        col_of = [0] * len(boxes)

    indexed = list(enumerate(items))
    indexed.sort(
        key=lambda pair: reading_order_key(
            boxes[pair[0]],
            column=col_of[pair[0]],
            row_quantum=row_quantum,
        )
    )
    return [item for _, item in indexed]
