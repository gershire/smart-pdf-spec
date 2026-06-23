"""Unit tests for :mod:`smart_pdf_scanner.utils.image_utils`."""

import io

import numpy as np
import pytest
from PIL import Image as PILImage

from smart_pdf_scanner.utils import image_utils as iu


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _solid_pil(width=64, height=64, color=(200, 200, 200), mode="RGB") -> PILImage.Image:
    img = PILImage.new(mode, (width, height), color)
    return img


def _solid_cv2(width=64, height=64, value=200) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def _gray_cv2(width=64, height=64, value=200) -> np.ndarray:
    return np.full((height, width), value, dtype=np.uint8)


# ---------------------------------------------------------------------------
# pil_to_cv2
# ---------------------------------------------------------------------------

class TestPilToCv2:
    def test_returns_ndarray(self):
        arr = iu.pil_to_cv2(_solid_pil())
        assert isinstance(arr, np.ndarray)

    def test_shape_matches_image(self):
        arr = iu.pil_to_cv2(_solid_pil(64, 32))
        assert arr.shape == (32, 64, 3)

    def test_dtype_uint8(self):
        arr = iu.pil_to_cv2(_solid_pil())
        assert arr.dtype == np.uint8

    def test_rgba_input_converted(self):
        img = _solid_pil(mode="RGBA", color=(100, 150, 200, 255))
        arr = iu.pil_to_cv2(img)
        assert arr.shape[2] == 3


# ---------------------------------------------------------------------------
# cv2_to_pil
# ---------------------------------------------------------------------------

class TestCv2ToPil:
    def test_returns_pil_image(self):
        pil = iu.cv2_to_pil(_solid_cv2())
        assert isinstance(pil, PILImage.Image)

    def test_mode_is_rgb(self):
        pil = iu.cv2_to_pil(_solid_cv2())
        assert pil.mode == "RGB"

    def test_grayscale_input(self):
        pil = iu.cv2_to_pil(_gray_cv2())
        assert isinstance(pil, PILImage.Image)
        assert pil.mode == "RGB"

    def test_roundtrip(self):
        original = _solid_pil(color=(100, 150, 200))
        arr = iu.pil_to_cv2(original)
        back = iu.cv2_to_pil(arr)
        assert back.size == original.size
        assert back.mode == "RGB"


# ---------------------------------------------------------------------------
# deskew
# ---------------------------------------------------------------------------

class TestDeskew:
    def test_returns_pil_image(self):
        result = iu.deskew(_solid_pil())
        assert isinstance(result, PILImage.Image)

    def test_output_same_size(self):
        img = _solid_pil(80, 60)
        result = iu.deskew(img)
        assert result.size == (80, 60)

    def test_accepts_cv2_input(self):
        result = iu.deskew(_solid_cv2())
        assert isinstance(result, PILImage.Image)

    def test_sparse_image_returns_original(self):
        # An all-white image has < 5 text pixels → early return branch.
        img = PILImage.new("RGB", (64, 64), (255, 255, 255))
        result = iu.deskew(img)
        assert isinstance(result, PILImage.Image)


# ---------------------------------------------------------------------------
# denoise
# ---------------------------------------------------------------------------

class TestDenoise:
    def test_returns_pil_image(self):
        result = iu.denoise(_solid_pil())
        assert isinstance(result, PILImage.Image)

    def test_output_same_size(self):
        img = _solid_pil(80, 60)
        result = iu.denoise(img)
        assert result.size == (80, 60)

    def test_grayscale_cv2_input(self):
        result = iu.denoise(_gray_cv2())
        assert isinstance(result, PILImage.Image)

    def test_custom_strength(self):
        result = iu.denoise(_solid_pil(), strength=5)
        assert isinstance(result, PILImage.Image)


# ---------------------------------------------------------------------------
# enhance_contrast
# ---------------------------------------------------------------------------

class TestEnhanceContrast:
    def test_returns_pil_image(self):
        result = iu.enhance_contrast(_solid_pil())
        assert isinstance(result, PILImage.Image)

    def test_output_same_size(self):
        img = _solid_pil(80, 60)
        result = iu.enhance_contrast(img)
        assert result.size == (80, 60)

    def test_grayscale_input(self):
        result = iu.enhance_contrast(_gray_cv2())
        assert isinstance(result, PILImage.Image)

    def test_custom_clip_limit(self):
        result = iu.enhance_contrast(_solid_pil(), clip_limit=3.0)
        assert isinstance(result, PILImage.Image)


# ---------------------------------------------------------------------------
# preprocess_for_ocr
# ---------------------------------------------------------------------------

class TestPreprocessForOcr:
    def test_all_steps_enabled(self):
        img = _solid_pil()
        result = iu.preprocess_for_ocr(img)
        assert isinstance(result, PILImage.Image)
        assert result.size == img.size

    def test_all_steps_disabled_returns_pil(self):
        img = _solid_pil()
        result = iu.preprocess_for_ocr(img, do_deskew=False, do_denoise=False, do_enhance=False)
        assert isinstance(result, PILImage.Image)

    def test_only_deskew(self):
        img = _solid_pil()
        result = iu.preprocess_for_ocr(img, do_deskew=True, do_denoise=False, do_enhance=False)
        assert isinstance(result, PILImage.Image)

    def test_custom_denoise_strength(self):
        result = iu.preprocess_for_ocr(_solid_pil(), do_deskew=False, do_denoise=True, do_enhance=False, denoise_strength=5)
        assert isinstance(result, PILImage.Image)


# ---------------------------------------------------------------------------
# convert_format
# ---------------------------------------------------------------------------

class TestConvertFormat:
    def test_rgb_to_l(self):
        img = _solid_pil()
        result = iu.convert_format(img, "L")
        assert result.mode == "L"

    def test_rgb_to_rgba(self):
        img = _solid_pil()
        result = iu.convert_format(img, "RGBA")
        assert result.mode == "RGBA"

    def test_accepts_cv2_array(self):
        arr = _solid_cv2()
        result = iu.convert_format(arr, "L")
        assert result.mode == "L"

    def test_same_mode_noop(self):
        img = _solid_pil(mode="RGB")
        result = iu.convert_format(img, "RGB")
        assert result.mode == "RGB"


# ---------------------------------------------------------------------------
# save_image / load_image
# ---------------------------------------------------------------------------

class TestSaveLoadImage:
    def test_save_png(self, tmp_path):
        img = _solid_pil()
        path = iu.save_image(img, tmp_path / "out.png")
        assert path.exists()
        assert path.suffix == ".png"

    def test_save_returns_path(self, tmp_path):
        img = _solid_pil()
        result = iu.save_image(img, tmp_path / "out.png")
        assert isinstance(result, type(tmp_path))

    def test_save_jpeg(self, tmp_path):
        img = _solid_pil()
        path = iu.save_image(img, tmp_path / "out.jpg")
        assert path.exists()

    def test_save_jpeg_quality(self, tmp_path):
        img = _solid_pil()
        path = iu.save_image(img, tmp_path / "out.jpg", quality=50)
        assert path.exists()

    def test_save_unsupported_extension_raises(self, tmp_path):
        img = _solid_pil()
        with pytest.raises(ValueError, match="Unsupported"):
            iu.save_image(img, tmp_path / "out.xyz")

    def test_save_rgba_as_jpeg_converts(self, tmp_path):
        img = _solid_pil(mode="RGBA", color=(100, 150, 200, 255))
        path = iu.save_image(img, tmp_path / "out.jpg")
        assert path.exists()

    def test_load_image_returns_pil(self, tmp_path):
        img = _solid_pil()
        path = iu.save_image(img, tmp_path / "out.png")
        loaded = iu.load_image(path)
        assert isinstance(loaded, PILImage.Image)
        assert loaded.mode == "RGB"
        assert loaded.size == img.size

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            iu.load_image(tmp_path / "missing.png")

    def test_save_creates_parent_directories(self, tmp_path):
        img = _solid_pil()
        nested = tmp_path / "a" / "b" / "out.png"
        iu.save_image(img, nested)
        assert nested.exists()

    def test_roundtrip_png(self, tmp_path):
        img = _solid_pil(color=(10, 20, 30))
        path = iu.save_image(img, tmp_path / "out.png")
        loaded = iu.load_image(path)
        assert list(loaded.getpixel((0, 0))) == [10, 20, 30]


# ---------------------------------------------------------------------------
# image_to_bytes
# ---------------------------------------------------------------------------

class TestImageToBytes:
    def test_returns_bytes(self):
        result = iu.image_to_bytes(_solid_pil())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_png_header(self):
        result = iu.image_to_bytes(_solid_pil(), fmt="PNG")
        assert result[:4] == b"\x89PNG"

    def test_jpeg_output(self):
        result = iu.image_to_bytes(_solid_pil(), fmt="JPEG")
        assert result[:2] == b"\xff\xd8"

    def test_rgba_to_jpeg_converts(self):
        img = _solid_pil(mode="RGBA", color=(100, 150, 200, 255))
        result = iu.image_to_bytes(img, fmt="JPEG")
        assert result[:2] == b"\xff\xd8"

    def test_accepts_cv2_array(self):
        result = iu.image_to_bytes(_solid_cv2())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_bytes_are_valid_image(self):
        img = _solid_pil()
        data = iu.image_to_bytes(img, fmt="PNG")
        reloaded = PILImage.open(io.BytesIO(data))
        assert reloaded.size == img.size
