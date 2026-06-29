"""Visualization utilities for the PDF processing pipeline."""

from smart_pdf_scanner.visualization.colors import (
    DEFAULT_COLOR_SCHEME,
    ColorRGBA,
    ColorScheme,
    get_color_scheme,
    get_element_color,
)
from smart_pdf_scanner.visualization.export import export_all_pages, export_visualization
from smart_pdf_scanner.visualization.renderer import PageRenderer

__all__ = [
    "ColorRGBA",
    "ColorScheme",
    "DEFAULT_COLOR_SCHEME",
    "get_color_scheme",
    "get_element_color",
    "export_all_pages",
    "export_visualization",
    "PageRenderer",
]
