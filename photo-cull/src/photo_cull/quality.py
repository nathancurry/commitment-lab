"""Technical quality scores computed on preview images.

All metrics work on a size-normalized grayscale array so scores are
comparable across cameras and preview sizes.

Thresholds are heuristic and pre-taste: stage 2 (learned from the
operator's past culls) will calibrate them. They only drive the
"technical suggestion", never any automatic action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image

# Normalize previews to this size (longest side) before scoring.
NORMALIZED_SIZE = 1024

# A pixel is "clipped" if it is within this distance of 0 or 255.
CLIP_MARGIN = 3

# Flag thresholds (calibrated coarsely; see module docstring).
BLUR_THRESHOLD = 40.0        # laplacian variance below this -> blur suspect
CLIP_FRACTION_THRESHOLD = 0.02  # >2% clipped pixels -> exposure flag

# Below this laplacian variance the frame is essentially featureless (flat
# black, white, or out-of-gamut). Calling it "blurry" would be wrong; the
# exposure flags describe the actual problem.
NEAR_FLAT_VARIANCE = 1.0


@dataclass
class QualityReport:
    """Technical scores for one image."""

    sharpness: float                  # variance of the 4-neighbour Laplacian
    sharpness_max_tile: float         # best 4x4-tile laplacian variance
    mean_luminance: float             # 0..255
    shadow_clip_fraction: float       # fraction of pixels <= CLIP_MARGIN
    highlight_clip_fraction: float    # fraction of pixels >= 255 - CLIP_MARGIN
    flags: list[str] = field(default_factory=list)

    @property
    def suggestion(self) -> str:
        """Technical-only suggestion: keep / maybe / reject."""
        if "blur_suspect" in self.flags:
            return "reject"
        if self.flags:
            return "maybe"
        return "keep"


def load_grayscale(data: bytes) -> np.ndarray:
    """Decode image bytes to a normalized uint8 grayscale array."""
    with Image.open(BytesIO(data)) as img:
        img = img.convert("L")
        w, h = img.size
        scale = NORMALIZED_SIZE / max(w, h)
        if scale < 1.0:
            img = img.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))),
                Image.BILINEAR,
            )
        return np.asarray(img, dtype=np.uint8)


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian (classic blur metric)."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    x = gray.astype(np.float64)
    lap = (
        4.0 * x[1:-1, 1:-1]
        - x[:-2, 1:-1]
        - x[2:, 1:-1]
        - x[1:-1, :-2]
        - x[1:-1, 2:]
    )
    return float(lap.var())


def _tile_slices(shape: tuple[int, int], rows: int, cols: int):
    """Yield (row_slice, col_slice) covering the image in rows*cols tiles."""
    h, w = shape
    for r in range(rows):
        r0 = round(r * h / rows)
        r1 = round((r + 1) * h / rows)
        for c in range(cols):
            c0 = round(c * w / cols)
            c1 = round((c + 1) * w / cols)
            yield slice(r0, r1), slice(c0, c1)


def assess(data: bytes) -> QualityReport:
    """Score one preview image and attach technical flags."""
    gray = load_grayscale(data)
    sharp = laplacian_variance(gray)
    max_tile = max(
        (
            laplacian_variance(gray[rs, cs])
            for rs, cs in _tile_slices(gray.shape, 4, 4)
            if rs.stop - rs.start >= 3 and cs.stop - cs.start >= 3
        ),
        default=0.0,
    )
    pixel = gray.astype(np.float64) / 255.0
    shadow_clip = float(np.count_nonzero(pixel <= CLIP_MARGIN / 255.0) / pixel.size)
    highlight_clip = float(
        np.count_nonzero(pixel >= 1.0 - CLIP_MARGIN / 255.0) / pixel.size
    )

    report = QualityReport(
        sharpness=sharp,
        sharpness_max_tile=max_tile,
        mean_luminance=float(gray.mean()),
        shadow_clip_fraction=shadow_clip,
        highlight_clip_fraction=highlight_clip,
    )
    if BLUR_THRESHOLD > sharp >= NEAR_FLAT_VARIANCE:
        report.flags.append("blur_suspect")
    if shadow_clip > CLIP_FRACTION_THRESHOLD:
        report.flags.append("clipped_shadows")
    if highlight_clip > CLIP_FRACTION_THRESHOLD:
        report.flags.append("clipped_highlights")
    return report
