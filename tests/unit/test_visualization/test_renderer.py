"""Unit tests for PageRenderer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from smart_pdf_scanner.models.elements import BoundingBox, ElementType, TextBlock
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.visualization.colors import DEFAULT_COLOR_SCHEME, get_color_scheme
from smart_pdf_scanner.visualization.renderer import PageRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(
    width: float = 595.0,
    height: float = 842.0,
    elements: list | None = None,
) -> Page:
    return Page(
        page_number=0,
        dimensions=PageDimensions(width=width, height=height),
        elements=elements or [],
    )


def _make_text_element(x0=10.0, y0=10.0, x1=200.0, y1=30.0, page_number=0) -> TextBlock:
    return TextBlock(
        element_id="test-element",
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        page_number=page_number,
        text="sample text",
    )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestPageRendererInit:
    def test_default_dpi(self):
        r = PageRenderer()
        assert r.dpi == 150

    def test_custom_dpi(self):
        r = PageRenderer(dpi=72)
        assert r.dpi == 72

    def test_default_color_scheme(self):
        r = PageRenderer()
        assert r.color_scheme == DEFAULT_COLOR_SCHEME

    def test_custom_color_scheme(self):
        scheme = get_color_scheme({"heading": (1, 2, 3, 4)})
        r = PageRenderer(color_scheme=scheme)
        assert r.color_scheme == scheme

    def test_fill_alpha_clamped(self):
        r = PageRenderer(fill_alpha=300)
        assert r._fill_alpha == 255
        r2 = PageRenderer(fill_alpha=-10)
        assert r2._fill_alpha == 0


# ---------------------------------------------------------------------------
# render_page — blank canvas fallback
# ---------------------------------------------------------------------------


class TestRenderPageBlankCanvas:
    def test_returns_pil_image(self):
        page = _make_page()
        r = PageRenderer(dpi=72)
        img = r.render_page(page)
        assert isinstance(img, PILImage.Image)

    def test_image_mode_is_rgb(self):
        page = _make_page()
        r = PageRenderer(dpi=72)
        img = r.render_page(page)
        assert img.mode == "RGB"

    def test_image_size_matches_page_dims_at_72dpi(self):
        # At 72 dpi: pixels = points * (72/72) = points
        page = _make_page(width=200.0, height=300.0)
        r = PageRenderer(dpi=72)
        img = r.render_page(page)
        assert img.size == (200, 300)

    def test_image_size_scales_with_dpi(self):
        # At 144 dpi: pixels = points * 2
        page = _make_page(width=100.0, height=100.0)
        r = PageRenderer(dpi=144)
        img = r.render_page(page)
        assert img.size == (200, 200)

    def test_blank_canvas_is_white(self):
        page = _make_page(width=10.0, height=10.0)
        r = PageRenderer(dpi=72)
        img = r.render_page(page)
        # Top-left pixel should be white (255, 255, 255)
        assert img.getpixel((0, 0)) == (255, 255, 255)

    def test_zero_dimension_page_returns_1x1_minimum(self):
        page = _make_page(width=0.0, height=0.0)
        r = PageRenderer(dpi=72)
        img = r.render_page(page)
        assert img.width >= 1 and img.height >= 1


# ---------------------------------------------------------------------------
# render_page — PyMuPDF path
# ---------------------------------------------------------------------------


class TestRenderPageWithFitz:
    def _mock_fitz(self, width=100, height=100):
        """Return a mock fitz module that produces a white RGB pixmap."""
        import struct

        samples = bytes([255, 255, 255]) * (width * height)
        pix = MagicMock()
        pix.width = width
        pix.height = height
        pix.samples = samples

        fitz_page = MagicMock()
        fitz_page.get_pixmap.return_value = pix

        doc = MagicMock()
        doc.__getitem__ = MagicMock(return_value=fitz_page)
        doc.close = MagicMock()

        fitz_mod = MagicMock()
        fitz_mod.open.return_value = doc
        fitz_mod.Matrix.return_value = MagicMock()
        return fitz_mod

    def test_render_with_fitz_returns_image(self, tmp_path):
        pdf = tmp_path / "dummy.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        page = _make_page(width=72.0, height=72.0)
        r = PageRenderer(dpi=72)
        with patch("smart_pdf_scanner.visualization.renderer.fitz", self._mock_fitz(), create=True):
            img = r.render_page(page, pdf_path=pdf)
        assert isinstance(img, PILImage.Image)

    def test_fitz_failure_falls_back_to_blank(self, tmp_path):
        pdf = tmp_path / "dummy.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        page = _make_page(width=100.0, height=100.0)
        r = PageRenderer(dpi=72)

        with patch.object(r, "_render_with_fitz", side_effect=RuntimeError("fitz error")):
            img = r.render_page(page, pdf_path=pdf)

        assert isinstance(img, PILImage.Image)
        assert img.mode == "RGB"


# ---------------------------------------------------------------------------
# draw_bbox
# ---------------------------------------------------------------------------


class TestDrawBbox:
    def test_draw_bbox_modifies_image(self):
        img = PILImage.new("RGBA", (200, 200), (255, 255, 255, 255))
        original_pixel = img.getpixel((50, 50))
        r = PageRenderer()
        bbox = BoundingBox(x0=40.0, y0=40.0, x1=80.0, y1=80.0)
        r.draw_bbox(img, bbox, color=(255, 0, 0, 160), scale=1.0)
        # The interior of the bbox should differ from the original white background
        drawn_pixel = img.getpixel((60, 60))
        assert drawn_pixel != original_pixel

    def test_draw_bbox_respects_scale(self):
        img = PILImage.new("RGBA", (400, 400), (255, 255, 255, 255))
        r = PageRenderer(fill_alpha=255)
        # bbox in PDF points; at scale=2 maps to pixels [20,20]→[40,40]
        bbox = BoundingBox(x0=10.0, y0=10.0, x1=20.0, y1=20.0)
        r.draw_bbox(img, bbox, color=(0, 0, 255, 255), scale=2.0)
        # Centre of the scaled box should be colored
        pixel = img.getpixel((30, 30))
        # It should not be pure white anymore (blue fill was drawn)
        assert pixel != (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# apply_colors
# ---------------------------------------------------------------------------


class TestApplyColors:
    def test_returns_rgb_image(self):
        page = _make_page(elements=[_make_text_element()])
        r = PageRenderer(dpi=72)
        base = PILImage.new("RGB", (100, 100), "white")
        result = r.apply_colors(base, page, scale=1.0)
        assert result.mode == "RGB"

    def test_empty_page_returns_unchanged_image(self):
        page = _make_page()  # no elements
        r = PageRenderer(dpi=72)
        base = PILImage.new("RGB", (100, 100), (200, 200, 200))
        result = r.apply_colors(base, page, scale=1.0)
        # All pixels should still be the original gray
        pixels = list(result.getdata())
        assert all(p == (200, 200, 200) for p in pixels)

    def test_multiple_elements_all_drawn(self):
        elements = [
            _make_text_element(10.0, 10.0, 50.0, 30.0),
            _make_text_element(60.0, 60.0, 90.0, 80.0),
        ]
        page = _make_page(elements=elements)
        r = PageRenderer(dpi=72, fill_alpha=255)
        base = PILImage.new("RGB", (200, 200), "white")
        result = r.apply_colors(base, page, scale=1.0)
        # At full alpha, interior pixels of bboxes should not be white
        assert result.getpixel((30, 20)) != (255, 255, 255)
        assert result.getpixel((75, 70)) != (255, 255, 255)


# ---------------------------------------------------------------------------
# render_with_annotations
# ---------------------------------------------------------------------------


class TestRenderWithAnnotations:
    def test_returns_rgb_image(self):
        page = _make_page(elements=[_make_text_element()])
        r = PageRenderer(dpi=72)
        img = r.render_with_annotations(page)
        assert isinstance(img, PILImage.Image)
        assert img.mode == "RGB"

    def test_image_size_matches_page(self):
        page = _make_page(width=100.0, height=200.0)
        r = PageRenderer(dpi=72)
        img = r.render_with_annotations(page)
        assert img.size == (100, 200)
