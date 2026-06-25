"""Unit tests for visualization export functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, TextBlock
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.visualization.export import export_all_pages, export_visualization
from smart_pdf_scanner.visualization.renderer import PageRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(page_number: int = 0, width=72.0, height=72.0) -> Page:
    return Page(
        page_number=page_number,
        dimensions=PageDimensions(width=width, height=height),
    )


def _make_page_with_element(page_number: int = 0) -> Page:
    el = TextBlock(
        element_id="test-el",
        element_type=ElementType.TEXT_BLOCK,
        bbox=BoundingBox(x0=5.0, y0=5.0, x1=30.0, y1=15.0),
        page_number=page_number,
        text="hello",
    )
    return Page(
        page_number=page_number,
        dimensions=PageDimensions(width=72.0, height=72.0),
        elements=[el],
    )


def _make_doc(pages: list[Page]) -> Document:
    return Document(
        metadata=DocumentMetadata(page_count=len(pages), file_size_bytes=0),
        assets_folder=Path("/tmp/assets"),
        pages=pages,
    )


# ---------------------------------------------------------------------------
# export_visualization
# ---------------------------------------------------------------------------


class TestExportVisualization:
    def test_saves_png_file(self, tmp_path):
        page = _make_page()
        out = tmp_path / "page.png"
        result = export_visualization(page, out, dpi=72)
        assert result.exists()
        assert result.suffix == ".png"

    def test_saves_jpeg_file(self, tmp_path):
        page = _make_page()
        out = tmp_path / "page.jpg"
        result = export_visualization(page, out, fmt="jpeg", dpi=72)
        assert result.exists()
        assert result.suffix == ".jpg"

    def test_jpg_alias_accepted(self, tmp_path):
        page = _make_page()
        out = tmp_path / "page.out"
        result = export_visualization(page, out, fmt="jpg", dpi=72)
        assert result.exists()
        assert result.suffix == ".jpg"

    def test_unsupported_format_raises(self, tmp_path):
        page = _make_page()
        with pytest.raises(ValueError, match="Unsupported format"):
            export_visualization(page, tmp_path / "page.bmp", fmt="bmp", dpi=72)

    def test_saved_file_is_valid_image(self, tmp_path):
        page = _make_page()
        out = tmp_path / "page.png"
        export_visualization(page, out, dpi=72)
        img = PILImage.open(out)
        assert img.width > 0 and img.height > 0

    def test_output_dir_created_if_missing(self, tmp_path):
        page = _make_page()
        deep_path = tmp_path / "a" / "b" / "page.png"
        result = export_visualization(page, deep_path, dpi=72)
        assert result.exists()

    def test_metadata_embedded_in_png(self, tmp_path):
        page = _make_page_with_element()
        out = tmp_path / "page.png"
        export_visualization(page, out, include_metadata=True, dpi=72)
        img = PILImage.open(out)
        # PIL stores PNG text chunks in img.info
        assert "page_number" in img.info or "element_count" in img.info

    def test_metadata_skipped_when_disabled(self, tmp_path):
        page = _make_page()
        out = tmp_path / "page.png"
        export_visualization(page, out, include_metadata=False, dpi=72)
        img = PILImage.open(out)
        assert "page_number" not in img.info

    def test_returns_correct_path(self, tmp_path):
        page = _make_page()
        out = tmp_path / "p.png"
        result = export_visualization(page, out, dpi=72)
        assert result == out

    def test_accepts_pre_built_renderer(self, tmp_path):
        page = _make_page()
        renderer = PageRenderer(dpi=72)
        out = tmp_path / "page.png"
        result = export_visualization(page, out, renderer=renderer)
        assert result.exists()

    def test_format_suffix_corrected_on_output_path(self, tmp_path):
        page = _make_page()
        # Pass a .png path but request jpeg format
        out = tmp_path / "page.png"
        result = export_visualization(page, out, fmt="jpeg", dpi=72)
        assert result.suffix == ".jpg"


# ---------------------------------------------------------------------------
# export_all_pages
# ---------------------------------------------------------------------------


class TestExportAllPages:
    def test_saves_one_file_per_page(self, tmp_path):
        doc = _make_doc([_make_page(0), _make_page(1), _make_page(2)])
        saved = export_all_pages(doc, tmp_path / "out", dpi=72)
        assert len(saved) == 3

    def test_all_files_exist(self, tmp_path):
        doc = _make_doc([_make_page(0), _make_page(1)])
        saved = export_all_pages(doc, tmp_path / "out", dpi=72)
        for path in saved:
            assert path.exists()

    def test_filenames_include_page_numbers(self, tmp_path):
        doc = _make_doc([_make_page(0), _make_page(5)])
        saved = export_all_pages(doc, tmp_path / "out", dpi=72)
        names = [p.name for p in saved]
        assert "page_0000.png" in names
        assert "page_0005.png" in names

    def test_empty_document_returns_empty_list(self, tmp_path):
        doc = _make_doc([])
        saved = export_all_pages(doc, tmp_path / "out", dpi=72)
        assert saved == []

    def test_output_dir_created(self, tmp_path):
        new_dir = tmp_path / "new" / "dir"
        doc = _make_doc([_make_page(0)])
        export_all_pages(doc, new_dir, dpi=72)
        assert new_dir.exists()

    def test_jpeg_format(self, tmp_path):
        doc = _make_doc([_make_page(0)])
        saved = export_all_pages(doc, tmp_path / "out", fmt="jpeg", dpi=72)
        assert saved[0].suffix == ".jpg"

    def test_unsupported_format_raises(self, tmp_path):
        doc = _make_doc([_make_page(0)])
        with pytest.raises(ValueError, match="Unsupported format"):
            export_all_pages(doc, tmp_path / "out", fmt="tiff", dpi=72)

    def test_shared_renderer_used(self, tmp_path):
        doc = _make_doc([_make_page(0), _make_page(1)])
        renderer = PageRenderer(dpi=72)
        with patch.object(renderer, "render_with_annotations", wraps=renderer.render_with_annotations) as mock:
            export_all_pages(doc, tmp_path / "out", renderer=renderer, dpi=72)
        assert mock.call_count == 2

    def test_valid_images_saved(self, tmp_path):
        doc = _make_doc([_make_page(0, width=100.0, height=100.0)])
        saved = export_all_pages(doc, tmp_path / "out", dpi=72)
        img = PILImage.open(saved[0])
        assert img.width > 0
