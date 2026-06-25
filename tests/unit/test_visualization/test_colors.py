"""Unit tests for visualization color scheme utilities."""

from __future__ import annotations

import pytest

from smart_pdf_scanner.models.elements import ElementType
from smart_pdf_scanner.visualization.colors import (
    DEFAULT_COLOR_SCHEME,
    ColorScheme,
    get_color_scheme,
    get_element_color,
)


class TestDefaultColorScheme:
    def test_all_element_types_have_colors(self):
        for et in ElementType:
            assert et in DEFAULT_COLOR_SCHEME, f"Missing color for {et}"

    def test_colors_are_valid_rgba(self):
        for et, color in DEFAULT_COLOR_SCHEME.items():
            assert len(color) == 4, f"Color for {et} must be RGBA (4-tuple)"
            assert all(0 <= c <= 255 for c in color), f"Color values out of range for {et}"

    def test_colors_are_distinct(self):
        # RGB triples (ignore alpha) should be unique enough to tell apart
        rgb_values = [c[:3] for c in DEFAULT_COLOR_SCHEME.values()]
        assert len(set(rgb_values)) == len(rgb_values), "Duplicate RGB colors in default scheme"


class TestGetColorScheme:
    def test_returns_copy_of_default_when_no_custom(self):
        scheme = get_color_scheme()
        assert scheme == DEFAULT_COLOR_SCHEME
        # Mutating returned scheme should not affect the module-level default
        scheme[ElementType.HEADING] = (0, 0, 0, 0)
        assert DEFAULT_COLOR_SCHEME[ElementType.HEADING] != (0, 0, 0, 0)

    def test_custom_overrides_specific_type(self):
        custom = {"heading": (255, 0, 0, 200)}
        scheme = get_color_scheme(custom)
        assert scheme[ElementType.HEADING] == (255, 0, 0, 200)
        # Other types unchanged
        assert scheme[ElementType.TEXT_BLOCK] == DEFAULT_COLOR_SCHEME[ElementType.TEXT_BLOCK]

    def test_custom_ignores_unknown_keys(self):
        custom = {"not_a_real_type": (1, 2, 3, 4)}
        scheme = get_color_scheme(custom)
        assert scheme == DEFAULT_COLOR_SCHEME  # unknown key silently dropped

    def test_custom_multiple_overrides(self):
        custom = {
            "heading": (10, 20, 30, 40),
            "table": (50, 60, 70, 80),
        }
        scheme = get_color_scheme(custom)
        assert scheme[ElementType.HEADING] == (10, 20, 30, 40)
        assert scheme[ElementType.TABLE] == (50, 60, 70, 80)

    def test_empty_custom_returns_default(self):
        assert get_color_scheme({}) == DEFAULT_COLOR_SCHEME


class TestGetElementColor:
    def test_returns_correct_color_for_known_type(self):
        for et in ElementType:
            color = get_element_color(et)
            assert color == DEFAULT_COLOR_SCHEME[et]

    def test_uses_provided_scheme(self):
        custom_scheme: ColorScheme = {et: (0, 0, 0, 0) for et in ElementType}
        color = get_element_color(ElementType.HEADING, custom_scheme)
        assert color == (0, 0, 0, 0)

    def test_fallback_color_for_missing_type_in_custom_scheme(self):
        # Provide a scheme that is missing some types
        partial_scheme: ColorScheme = {ElementType.HEADING: (1, 2, 3, 4)}
        color = get_element_color(ElementType.TABLE, partial_scheme)
        # Should return fallback gray, not raise
        assert len(color) == 4
        assert all(0 <= c <= 255 for c in color)

    def test_none_scheme_uses_default(self):
        color = get_element_color(ElementType.IMAGE, None)
        assert color == DEFAULT_COLOR_SCHEME[ElementType.IMAGE]
