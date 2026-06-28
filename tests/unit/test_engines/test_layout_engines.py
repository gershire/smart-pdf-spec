"""Unit tests for layout engine implementations (task 7.3)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
from smart_pdf_scanner.engines.layout.layoutparser import LayoutParserEngine
from smart_pdf_scanner.models.config import LayoutConfig
from smart_pdf_scanner.models.elements import (
    BoundingBox,
    Element,
    ElementType,
    FontInfo,
    Heading,
    TextBlock,
)
from smart_pdf_scanner.models.page import Page, PageDimensions


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def layout_config() -> LayoutConfig:
    return LayoutConfig(
        engine="heuristic",
        model="",
        confidence_threshold=0.5,
    )


def _make_page(*elements: Element) -> Page:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    for el in elements:
        page.add_element(el)
    return page


def _text_block(text: str, font_size: float, y0: float = 50.0) -> TextBlock:
    return TextBlock(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=50.0, y0=y0, x1=400.0, y1=y0 + 20.0),
        page_number=0,
        text=text,
        font_info=FontInfo(name="Helvetica", size=font_size, weight="normal", style="normal"),
    )


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class TestLayoutEngineInterface:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            LayoutEngine()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# HeuristicEngine
# ---------------------------------------------------------------------------


class TestHeuristicEngine:
    def test_name(self) -> None:
        assert HeuristicEngine().name == "heuristic"

    def test_empty_page_returns_empty(self, layout_config: LayoutConfig) -> None:
        page = _make_page()
        elements = HeuristicEngine().detect_layout(page, layout_config)
        assert elements == []

    def test_text_block_stays_text_block(self, layout_config: LayoutConfig) -> None:
        block = _text_block("Normal paragraph text.", font_size=12.0, y0=100.0)
        page = _make_page(block)
        result = HeuristicEngine().detect_layout(page, layout_config)
        assert len(result) == 1
        assert result[0].element_type == ElementType.TEXT_BLOCK

    def test_large_font_promoted_to_heading(self, layout_config: LayoutConfig) -> None:
        body = _text_block("Body text.", font_size=12.0, y0=100.0)
        big = _text_block("Chapter Title", font_size=24.0, y0=50.0)
        page = _make_page(body, big)
        result = HeuristicEngine().detect_layout(page, layout_config)
        headings = [el for el in result if el.element_type == ElementType.HEADING]
        assert len(headings) == 1
        assert headings[0].text == "Chapter Title"  # type: ignore[attr-defined]

    def test_heading_like_text_promoted(self, layout_config: LayoutConfig) -> None:
        block = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TEXT_BLOCK,
            bbox=BoundingBox(x0=50.0, y0=50.0, x1=400.0, y1=70.0),
            page_number=0,
            text="1. Introduction",
        )
        page = _make_page(block)
        result = HeuristicEngine().detect_layout(page, layout_config)
        assert any(el.element_type == ElementType.HEADING for el in result)

    def test_all_elements_get_confidence(self, layout_config: LayoutConfig) -> None:
        body = _text_block("Some text.", font_size=12.0)
        page = _make_page(body)
        result = HeuristicEngine().detect_layout(page, layout_config)
        assert all(el.confidence > 0.0 for el in result)

    def test_get_confidence_returns_element_confidence(self) -> None:
        engine = HeuristicEngine()
        el = _text_block("x", 12.0)
        el.confidence = 0.75
        assert engine.get_confidence(el) == 0.75

    def test_non_text_elements_passed_through(self, layout_config: LayoutConfig) -> None:
        from smart_pdf_scanner.models.elements import Image, ImageType
        img = Image(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.IMAGE,
            bbox=BoundingBox(x0=50.0, y0=50.0, x1=200.0, y1=200.0),
            page_number=0,
            image_type=ImageType.PHOTOGRAPH,
            description="",
        )
        page = _make_page(img)
        result = HeuristicEngine().detect_layout(page, layout_config)
        assert len(result) == 1
        assert result[0].element_type == ElementType.IMAGE

    def test_median_font_size_even_list(self) -> None:
        sizes = [10.0, 12.0, 14.0, 16.0]
        elements = [_text_block("x", s) for s in sizes]
        median = HeuristicEngine._median_font_size(elements)
        assert median == pytest.approx(13.0)

    def test_median_font_size_no_font_info(self) -> None:
        el = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.TEXT_BLOCK,
            bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
            page_number=0,
            text="x",
        )
        assert HeuristicEngine._median_font_size([el]) == 0.0

    def test_heading_level_mapping(self) -> None:
        engine = HeuristicEngine()
        assert engine._estimate_level(24.0, 12.0) == 1  # ratio 2.0 → H1
        assert engine._estimate_level(20.0, 12.0) == 2  # ratio ~1.67 → H2
        assert engine._estimate_level(17.0, 12.0) == 3  # ratio ~1.42 → H3
        assert engine._estimate_level(15.0, 12.0) == 4  # ratio 1.25 → H4
        assert engine._estimate_level(14.0, 12.0) == 5  # ratio ~1.17 → H5
        assert engine._estimate_level(0.0, 0.0) == 2    # zero median → default H2


# ---------------------------------------------------------------------------
# LayoutParserEngine
# ---------------------------------------------------------------------------


class TestLayoutParserEngine:
    def test_name(self) -> None:
        assert LayoutParserEngine().name == "layoutparser"

    def test_raises_import_error_when_layoutparser_not_installed(
        self, layout_config: LayoutConfig
    ) -> None:
        engine = LayoutParserEngine()
        page = _make_page()
        with patch.dict("sys.modules", {"layoutparser": None}):
            with pytest.raises(ImportError, match="layoutparser"):
                engine.detect_layout(page, layout_config)

    def test_returns_existing_elements_when_page_has_no_image(
        self, layout_config: LayoutConfig
    ) -> None:
        block = _text_block("Some text.", 12.0)
        page = _make_page(block)
        # page has no _image attribute → should fall back to existing elements
        mock_lp = MagicMock()
        mock_model = MagicMock()
        mock_lp.Detectron2LayoutModel.return_value = mock_model
        with patch.dict("sys.modules", {"layoutparser": mock_lp}):
            engine = LayoutParserEngine()
            engine._model = mock_model
            engine._loaded_model_path = layout_config.model
            result = engine.detect_layout(page, layout_config)
        assert len(result) == 1

    def test_get_confidence_returns_element_confidence(self) -> None:
        engine = LayoutParserEngine()
        el = _text_block("x", 12.0)
        el.confidence = 0.9
        assert engine.get_confidence(el) == pytest.approx(0.9)

    def test_text_for_region_collects_overlapping_text(self) -> None:
        block = _text_block("overlapping", 12.0, y0=40.0)
        page = _make_page(block)
        text = LayoutParserEngine._text_for_region(page, 0, 30, 600, 100)
        assert "overlapping" in text

    def test_text_for_region_excludes_non_overlapping(self) -> None:
        block = _text_block("far away", 12.0, y0=500.0)
        page = _make_page(block)
        text = LayoutParserEngine._text_for_region(page, 0, 0, 100, 30)
        assert "far away" not in text
