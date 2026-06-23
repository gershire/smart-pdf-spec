"""Image preprocessing and format conversion utilities.

Provides functions for preparing images before OCR (deskew, denoise, contrast
enhancement) and for converting/saving image data in various formats.

Requires Pillow and OpenCV; both are declared in pyproject.toml.

References
----------
- Requirement 4: OCR Processing  (preprocessing improves recognition accuracy)
- Requirement 7: Image Processing (images extracted from PDFs must be saved)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image as PILImage

__all__ = [
    "pil_to_cv2",
    "cv2_to_pil",
    "deskew",
    "denoise",
    "enhance_contrast",
    "preprocess_for_ocr",
    "convert_format",
    "save_image",
    "load_image",
    "image_to_bytes",
]

# Type accepted anywhere a source image is expected.
ImageInput = Union[PILImage.Image, np.ndarray]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_pil(img: ImageInput) -> PILImage.Image:
    if isinstance(img, PILImage.Image):
        return img
    return cv2_to_pil(img)


def _ensure_cv2(img: ImageInput) -> np.ndarray:
    if isinstance(img, np.ndarray):
        return img
    return pil_to_cv2(img)


# ---------------------------------------------------------------------------
# Conversion utilities
# ---------------------------------------------------------------------------


def pil_to_cv2(img: PILImage.Image) -> np.ndarray:
    """Convert a Pillow image to a BGR NumPy array (OpenCV format).

    Args:
        img: Source Pillow image (any mode).

    Returns:
        NumPy array in BGR channel order as expected by OpenCV.
    """
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.uint8)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def cv2_to_pil(arr: np.ndarray) -> PILImage.Image:
    """Convert a BGR NumPy array (OpenCV format) to a Pillow RGB image.

    Args:
        arr: OpenCV image array (BGR or grayscale).

    Returns:
        Pillow image in RGB mode.
    """
    if arr.ndim == 2:
        # Grayscale → RGB
        return PILImage.fromarray(arr, mode="L").convert("RGB")
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return PILImage.fromarray(rgb)


# ---------------------------------------------------------------------------
# Preprocessing functions
# ---------------------------------------------------------------------------


def deskew(img: ImageInput) -> PILImage.Image:
    """Straighten a slightly rotated/skewed image.

    Uses the Hough line transform to estimate the dominant skew angle and
    rotates the image to compensate. The background is filled with white to
    avoid artefacts at the edges.

    Args:
        img: Source image.

    Returns:
        Deskewed Pillow image.
    """
    arr = _ensure_cv2(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr.copy()

    # Binarise and invert so text pixels become white on black background.
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 5:
        return _ensure_pil(img)

    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect returns angles in [-90, 0); map to [-45, 45].
    if angle < -45:
        angle = 90 + angle

    h, w = arr.shape[:2]
    centre = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(centre, angle, 1.0)
    rotated = cv2.warpAffine(
        arr,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return cv2_to_pil(rotated)


def denoise(img: ImageInput, *, strength: int = 10) -> PILImage.Image:
    """Remove noise from an image using OpenCV's Non-Local Means Denoising.

    Args:
        img: Source image.
        strength: Filter strength controlling noise removal vs. detail
            preservation. Higher values remove more noise but may blur text.
            Typical useful range is 5–20.

    Returns:
        Denoised Pillow image.
    """
    arr = _ensure_cv2(img)
    if arr.ndim == 2:
        denoised = cv2.fastNlMeansDenoising(arr, h=float(strength))
    else:
        denoised = cv2.fastNlMeansDenoisingColored(arr, h=float(strength))
    return cv2_to_pil(denoised)


def enhance_contrast(img: ImageInput, *, clip_limit: float = 2.0, tile_grid_size: int = 8) -> PILImage.Image:
    """Improve local contrast using CLAHE (Adaptive Histogram Equalisation).

    CLAHE operates in the L channel of the LAB colour space so that only
    luminance contrast is enhanced without shifting hue or saturation.

    Args:
        img: Source image.
        clip_limit: Threshold for contrast limiting (prevents over-amplification
            of uniform regions). Typical range is 1.0–4.0.
        tile_grid_size: Size of the grid tiles used for histogram computation.

    Returns:
        Contrast-enhanced Pillow image.
    """
    arr = _ensure_cv2(img)
    if arr.ndim == 2:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
        enhanced = clahe.apply(arr)
        return cv2_to_pil(enhanced)

    lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
    l_channel = clahe.apply(l_channel)
    enhanced_lab = cv2.merge([l_channel, a_channel, b_channel])
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    return cv2_to_pil(enhanced_bgr)


def preprocess_for_ocr(
    img: ImageInput,
    *,
    do_deskew: bool = True,
    do_denoise: bool = True,
    do_enhance: bool = True,
    denoise_strength: int = 10,
    clahe_clip: float = 2.0,
) -> PILImage.Image:
    """Apply a standard OCR preprocessing pipeline to an image.

    Sequentially applies: deskew → denoise → contrast enhancement. Each step
    can be disabled independently for performance or quality tuning.

    Args:
        img: Source image.
        do_deskew: Apply :func:`deskew` if ``True``.
        do_denoise: Apply :func:`denoise` if ``True``.
        do_enhance: Apply :func:`enhance_contrast` if ``True``.
        denoise_strength: Passed to :func:`denoise`.
        clahe_clip: Passed to :func:`enhance_contrast`.

    Returns:
        Preprocessed Pillow image ready for OCR.
    """
    result: ImageInput = img
    if do_deskew:
        result = deskew(result)
    if do_denoise:
        result = denoise(result, strength=denoise_strength)
    if do_enhance:
        result = enhance_contrast(result, clip_limit=clahe_clip)
    return _ensure_pil(result)


# ---------------------------------------------------------------------------
# I/O utilities
# ---------------------------------------------------------------------------


def convert_format(img: ImageInput, target_format: str) -> PILImage.Image:
    """Convert an image to the requested colour mode / format.

    Args:
        img: Source image.
        target_format: Target Pillow mode (e.g. ``"RGB"``, ``"L"``, ``"RGBA"``,
            ``"1"``).

    Returns:
        Converted Pillow image.
    """
    pil = _ensure_pil(img)
    return pil.convert(target_format)


def save_image(img: ImageInput, path: Union[str, Path], *, quality: int = 95) -> Path:
    """Save an image to disk, inferring the format from the file extension.

    Args:
        img: Source image.
        path: Destination file path. The extension determines the output format
            (e.g. ``.png``, ``.jpg``, ``.tiff``).
        quality: JPEG quality setting (1–95); ignored for lossless formats.

    Returns:
        The resolved ``Path`` the image was written to.

    Raises:
        ValueError: If the file extension is not a recognised image format.
    """
    dest = Path(path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    pil = _ensure_pil(img)
    ext = dest.suffix.lower().lstrip(".")
    fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "tiff": "TIFF", "tif": "TIFF", "bmp": "BMP", "webp": "WEBP"}
    fmt = fmt_map.get(ext)
    if fmt is None:
        raise ValueError(f"Unsupported image format: {dest.suffix!r}")
    if fmt == "JPEG" and pil.mode in ("RGBA", "P"):
        pil = pil.convert("RGB")
    save_kwargs: dict = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
    pil.save(dest, format=fmt, **save_kwargs)
    return dest


def load_image(path: Union[str, Path]) -> PILImage.Image:
    """Load an image from disk.

    Args:
        path: Path to the image file.

    Returns:
        Pillow image in RGB mode.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image file not found: {p}")
    return PILImage.open(p).convert("RGB")


def image_to_bytes(img: ImageInput, *, fmt: str = "PNG") -> bytes:
    """Serialise an image to a bytes object in the given format.

    Useful for passing images to APIs (e.g. LLM vision endpoints) without
    writing to disk.

    Args:
        img: Source image.
        fmt: Output image format understood by Pillow (``"PNG"``, ``"JPEG"``, …).

    Returns:
        Raw image bytes.
    """
    pil = _ensure_pil(img)
    buf = io.BytesIO()
    if fmt.upper() == "JPEG" and pil.mode in ("RGBA", "P"):
        pil = pil.convert("RGB")
    pil.save(buf, format=fmt.upper())
    return buf.getvalue()
