"""Shared fixtures: synthetic images and a synthesized minimal DNG.

No real photos are used anywhere: every test image is generated here, in
tmp directories, at test time.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

# --------------------------------------------------------------------------
# Synthetic images
# --------------------------------------------------------------------------


def detailed_array(w: int = 1024, h: int = 768, seed: int = 7) -> np.ndarray:
    """A sharply detailed synthetic pattern (noise + checkerboard + ramps).

    Values stay in mid-range (roughly 70..190) so the pattern has detail
    but no shadow or highlight clipping.
    """
    rng = np.random.default_rng(seed)
    x = np.arange(w)[None, :]
    y = np.arange(h)[:, None]
    checker = ((x // 8 + y // 8) % 2) * 60 + 98
    ramp = (x * 30 // w + y * 30 / h).astype(np.float64)
    noise = rng.uniform(0, 50, size=(h, w))
    img = checker + ramp + noise
    return np.clip(img, 0, 255).astype(np.uint8)


def encode_jpeg(arr: np.ndarray, quality: int = 95) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, mode="L").convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def blur_bytes(data: bytes, radius: float = 4.0) -> bytes:
    """Return a Gaussian-blurred copy of an encoded image."""
    with Image.open(io.BytesIO(data)) as img:
        buf = io.BytesIO()
        img.filter(ImageFilter.GaussianBlur(radius)).save(
            buf, "JPEG", quality=95
        )
        return buf.getvalue()


# --------------------------------------------------------------------------
# Minimal DNG builder (validated against LibRaw/rawpy and exiftool)
# --------------------------------------------------------------------------

BYTE, ASCII, SHORT, LONG, RATIONAL, SRATIONAL = 1, 2, 3, 4, 5, 10
TYPESZ = {BYTE: 1, ASCII: 1, SHORT: 2, LONG: 4, RATIONAL: 8, SRATIONAL: 8}


def _pack_value(typ, value):
    if typ == ASCII:
        return value.encode() + b"\0"
    if typ == BYTE:
        return bytes(value)
    if typ == SHORT:
        return struct.pack(f"<{len(value)}H", *value)
    if typ == LONG:
        return struct.pack(f"<{len(value)}I", *value)
    if typ == RATIONAL:
        return b"".join(struct.pack("<II", n, d) for n, d in value)
    if typ == SRATIONAL:
        return b"".join(struct.pack("<ii", n, d) for n, d in value)
    raise ValueError(typ)


def _count(typ, value) -> int:
    if typ == ASCII:
        return len(value) + 1
    return len(value)


def make_minimal_dng(
    jpeg: bytes,
    raw_cfa: np.ndarray,
    width: int,
    height: int,
    camera: str = "SynthCam",
) -> bytes:
    """Build a minimal DNG: IFD0 (embedded JPEG preview) + CFA SubIFD.

    The preview extraction code path exercised by LibRaw for this file is
    the same one used for camera RAWs (RAF, CR2, NEF, ...); only LibRaw's
    internal container parser differs per format.
    """
    raw_bytes = raw_cfa.astype("<u2").tobytes()

    thumbnail_ifd = {
        254: (LONG, [1]),              # reduced-resolution image
        256: (LONG, [width]),
        257: (LONG, [height]),
        258: (SHORT, [8, 8, 8]),
        259: (SHORT, [6]),             # old-style JPEG
        262: (SHORT, [6]),             # YCbCr
        273: (LONG, [("JPEG", 0)]),
        277: (SHORT, [3]),
        278: (LONG, [height]),
        279: (LONG, [len(jpeg)]),
        513: (LONG, [("JPEG", 0)]),    # JPEGInterchangeFormat
        514: (LONG, [len(jpeg)]),
        282: (RATIONAL, [(72, 1)]),
        283: (RATIONAL, [(72, 1)]),
        296: (SHORT, [2]),
    }
    raw_ifd = {
        254: (LONG, [0]),
        256: (LONG, [width]),
        257: (LONG, [height]),
        258: (SHORT, [16]),
        259: (SHORT, [1]),
        262: (SHORT, [32803]),         # CFA
        277: (SHORT, [1]),
        278: (LONG, [height]),
        279: (LONG, [len(raw_bytes)]),
        284: (SHORT, [1]),
        0x828D: (SHORT, [2, 2]),       # CFARepeatPatternDim
        0x828E: (BYTE, [0, 1, 1, 2]),  # CFAPattern: RGGB
        0xC61A: (LONG, [0]),           # BlackLevel
        0xC61D: (LONG, [65535]),       # WhiteLevel
        0xC621: (SRATIONAL, [(1, 1), (0, 1), (0, 1),
                              (0, 1), (1, 1), (0, 1),
                              (0, 1), (0, 1), (1, 1)]),  # ColorMatrix1
        0xC628: (RATIONAL, [(1, 1), (1, 1), (1, 1)]),    # AsShotNeutral
    }
    ifd0 = dict(thumbnail_ifd)
    ifd0[0x014A] = (LONG, [("IFD", 1)])          # SubIFDs -> raw IFD
    ifd0[0xC612] = (BYTE, [1, 4, 0, 0])          # DNGVersion
    ifd0[0xC614] = (ASCII, camera)               # UniqueCameraModel

    ifds = [ifd0, raw_ifd]

    def is_placeholder(val):
        return (isinstance(val, list) and len(val) == 1
                and isinstance(val[0], tuple) and isinstance(val[0][0], str))

    # Layout: header | IFD entries | out-of-line values | jpeg | raw
    pos = 8
    ifd_offsets = []
    for tags in ifds:
        ifd_offsets.append(pos)
        pos += 2 + 12 * len(tags) + 4
    value_pos = pos
    value_offsets, blob_offsets = [], {}
    for tags in ifds:
        value_offsets.append(value_pos)
        for typ, val in tags.values():
            if is_placeholder(val):
                continue  # placeholder: inline LONG, no out-of-line data
            data = _pack_value(typ, val)
            if len(data) > 4:
                value_pos += len(data) + (len(data) & 1)
    for name, blob in (("JPEG", jpeg), ("RAW", raw_bytes)):
        blob_offsets[name] = value_pos
        value_pos += len(blob)

    def field_for(typ, val, extra):
        if is_placeholder(val):
            kind, i = val[0]
            if kind == "IFD":
                return struct.pack("<I", ifd_offsets[i])
            return struct.pack("<I", blob_offsets[kind])
        data = _pack_value(typ, val)
        if len(data) <= 4:
            return data + b"\0" * (4 - len(data))
        field = struct.pack("<I", value_offsets[idx] + len(extra))
        extra.extend(data)
        if len(data) & 1:
            extra.append(0)
        return field

    out = bytearray(b"II" + struct.pack("<HI", 42, 8))
    extras = []
    for idx, tags in enumerate(ifds):
        buf = bytearray(struct.pack("<H", len(tags)))
        extra = bytearray()
        for tag, (typ, val) in sorted(tags.items()):
            count = _count(typ, val)
            buf += struct.pack("<HHI", tag, typ, count)
            buf += field_for(typ, val, extra)
        buf += struct.pack("<I", 0)
        extras.append(bytes(extra))
        out += buf
    for extra in extras:
        out += extra
    out += jpeg + raw_bytes
    assert len(out) == value_pos, (len(out), value_pos)
    return bytes(out)


def make_dng_file(path: Path, preview_arr: np.ndarray) -> Path:
    """Write a minimal DNG whose embedded preview shows preview_arr."""
    h, w = preview_arr.shape
    jpeg = encode_jpeg(preview_arr)
    cfa = np.zeros((h, w), dtype=np.uint16)
    cfa[0::2, 0::2] = 400
    cfa[0::2, 1::2] = 800
    cfa[1::2, 0::2] = 800
    cfa[1::2, 1::2] = 200
    cfa += (np.arange(w, dtype=np.uint16)[None, :] * 4)
    path.write_bytes(make_minimal_dng(jpeg, cfa, w, h))
    return path


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sharp_jpeg_bytes() -> bytes:
    return encode_jpeg(detailed_array())


@pytest.fixture
def blurry_jpeg_bytes(sharp_jpeg_bytes) -> bytes:
    return blur_bytes(sharp_jpeg_bytes)


@pytest.fixture
def black_jpeg_bytes() -> bytes:
    return encode_jpeg(np.zeros((256, 256), dtype=np.uint8))


@pytest.fixture
def white_jpeg_bytes() -> bytes:
    return encode_jpeg(np.full((256, 256), 255, dtype=np.uint8))


@pytest.fixture
def sample_dir(tmp_path, sharp_jpeg_bytes, blurry_jpeg_bytes):
    """A synthetic library: sharp, blurred, black, white, DNG, and junk."""
    black = np.zeros((64, 48), dtype=np.uint8)
    white = np.full((64, 48), 255, dtype=np.uint8)
    (tmp_path / "sharp.jpg").write_bytes(sharp_jpeg_bytes)
    (tmp_path / "blurred.jpg").write_bytes(blurry_jpeg_bytes)
    (tmp_path / "black.jpg").write_bytes(encode_jpeg(black))
    (tmp_path / "white.jpg").write_bytes(encode_jpeg(white))
    make_dng_file(tmp_path / "sample_01.dng", detailed_array(256, 192))
    (tmp_path / "notes.txt").write_text("not a photo")
    return tmp_path
