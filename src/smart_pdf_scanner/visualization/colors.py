"""Color scheme for element type visualization.

Defines RGBA color mappings for each :class:`~smart_pdf_scanner.models.elements.ElementType`
and provides helpers to retrieve and customise color schemes for bounding-box
overlays (Requirement 11: Visualization Support).

Colors are chosen to be visually distinct and accessible on a white page
background.  Each color has a default alpha of 160/255 (~63 % opacity) so
the underlying page content remains legible through the overlay.
"""

from __future__ import annotations

from smart_pdf_scanner.models.elements import ElementType

__all__ = [
    "ColorRGBA",
    "ColorScheme",
    "DEFAULT_COLOR_SCHEME",
    "get_color_scheme",
    "get_element_color",
]

# Type aliases
ColorRGBA = tuple[int, int, int, int]
ColorScheme = dict[ElementType, ColorRGBA]

# ---------------------------------------------------------------------------
# Default scheme
# ---------------------------------------------------------------------------

#: Default RGBA colors keyed by :class:`~smart_pdf_scanner.models.elements.ElementType`.
#:
#: Alpha value 160/255 ≈ 63 % provides a semi-transparent overlay that keeps
#: the page content legible while clearly marking element boundaries.
DEFAULT_COLOR_SCHEME: ColorScheme = {
    ElementType.TEXT_BLOCK: (70, 130, 180, 160),   # steel blue
    ElementType.HEADING:    (220, 20,  60,  160),   # crimson
    ElementType.TABLE:      (50,  205, 50,  160),   # lime green
    ElementType.IMAGE:      (255, 140, 0,   160),   # dark orange
    ElementType.CAPTION:    (148, 0,   211, 160),   # violet
    ElementType.FOOTNOTE:   (105, 105, 105, 160),   # dim gray
    ElementType.SIDEBAR:    (0,   206, 209, 160),   # dark turquoise
}

_FALLBACK_COLOR: ColorRGBA = (128, 128, 128, 160)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_color_scheme(
    custom: dict[str, ColorRGBA] | None = None,
) -> ColorScheme:
    """Return a color scheme, optionally merged with custom overrides.

    The base scheme is :data:`DEFAULT_COLOR_SCHEME`.  Keys in *custom* must
    be valid :class:`~smart_pdf_scanner.models.elements.ElementType` string
    values (e.g. ``"heading"``); unrecognised keys are silently ignored.

    Args:
        custom: Optional mapping of element-type string → RGBA tuple that
            overrides specific entries in the default scheme.

    Returns:
        A :data:`ColorScheme` dict mapping every
        :class:`~smart_pdf_scanner.models.elements.ElementType` to an RGBA
        color tuple.

    Example::

        scheme = get_color_scheme({"heading": (255, 0, 0, 200)})
        # headings are now bright red; everything else uses defaults
    """
    scheme: ColorScheme = dict(DEFAULT_COLOR_SCHEME)
    if custom:
        for key, color in custom.items():
            try:
                scheme[ElementType(key)] = color
            except ValueError:
                pass  # silently ignore unknown element-type names
    return scheme


def get_element_color(
    element_type: ElementType,
    scheme: ColorScheme | None = None,
) -> ColorRGBA:
    """Return the RGBA overlay color for *element_type*.

    Args:
        element_type: The element type to look up.
        scheme: The color scheme to use.  Defaults to
            :data:`DEFAULT_COLOR_SCHEME` when ``None``.

    Returns:
        An ``(R, G, B, A)`` tuple with each component in ``[0, 255]``.
    """
    active = DEFAULT_COLOR_SCHEME if scheme is None else scheme
    return active.get(element_type, _FALLBACK_COLOR)
