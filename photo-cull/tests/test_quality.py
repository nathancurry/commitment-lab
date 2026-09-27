"""Tests for technical quality scoring."""

import numpy as np
import pytest

from conftest import encode_jpeg
from photo_cull.quality import BLUR_THRESHOLD, QualityReport, assess, load_grayscale, laplacian_variance


def test_sharp_scores_higher_than_blurred(sharp_jpeg_bytes, blurry_jpeg_bytes):
    sharp = assess(sharp_jpeg_bytes)
    blurry = assess(blurry_jpeg_bytes)
    assert sharp.sharpness > blurry.sharpness * 3, (
        f"sharp {sharp.sharpness} vs blurry {blurry.sharpness}"
    )


def test_sharp_image_passes_blur_flag(sharp_jpeg_bytes):
    sharp = assess(sharp_jpeg_bytes)
    assert sharp.sharpness >= BLUR_THRESHOLD
    assert "blur_suspect" not in sharp.flags
    assert sharp.suggestion == "keep"


def test_blurred_image_flags_blur_suspect(blurry_jpeg_bytes):
    blurry = assess(blurry_jpeg_bytes)
    assert blurry.sharpness < BLUR_THRESHOLD
    assert "blur_suspect" in blurry.flags
    assert blurry.suggestion == "reject"


def test_black_image_flags_shadow_clipping(black_jpeg_bytes):
    report = assess(black_jpeg_bytes)
    assert report.shadow_clip_fraction > 0.99
    assert "clipped_shadows" in report.flags
    assert report.suggestion == "maybe"


def test_white_image_flags_highlight_clipping(white_jpeg_bytes):
    report = assess(white_jpeg_bytes)
    assert report.highlight_clip_fraction > 0.99
    assert "clipped_highlights" in report.flags
    assert report.suggestion == "maybe"


def test_laplacian_variance_flat_image_is_zero():
    flat = np.full((64, 64), 128, dtype=np.uint8)
    assert laplacian_variance(flat) == 0.0


def test_load_grayscale_normalizes_size():
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 256, (2048, 3072), dtype=np.uint16).astype(np.uint8)
    gray = load_grayscale(encode_jpeg(arr))
    assert max(gray.shape) == 1024


@pytest.mark.parametrize("flags,expected", [
    ([], "keep"),
    (["clipped_highlights"], "maybe"),
    (["blur_suspect"], "reject"),
    (["blur_suspect", "clipped_shadows"], "reject"),
])
def test_suggestion_mapping(flags, expected):
    report = QualityReport(0.0, 0.0, 128.0, 0.0, 0.0, flags=flags)
    assert report.suggestion == expected
