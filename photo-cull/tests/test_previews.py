"""Tests for preview extraction, including the RAW path via a synthesized DNG."""

from io import BytesIO

import pytest
from PIL import Image

from conftest import detailed_array, make_dng_file
from photo_cull.previews import extract_preview
from photo_cull.formats import classify


def test_classify_extensions():
    assert classify("a.RAF") == "raw"
    assert classify("b.cr3") == "raw"
    assert classify("c.dng") == "raw"
    assert classify("d.jpg") == "direct"
    assert classify("e.PNG") == "direct"
    assert classify("f.txt") == "unknown"


def test_direct_file_passes_through(tmp_path):
    p = tmp_path / "img.jpg"
    p.write_bytes(b"not-a-real-jpeg")  # pass-through must not decode
    preview = extract_preview(p)
    assert preview.kind == "direct"
    assert preview.data == b"not-a-real-jpeg"


def test_unknown_extension_raises(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("hello")
    with pytest.raises(ValueError):
        extract_preview(p)


def test_dng_embedded_preview_extracted(tmp_path):
    """RAW path end-to-end: LibRaw extracts the embedded JPEG from a DNG."""
    expected = detailed_array(256, 192)
    dng = make_dng_file(tmp_path / "sample.dng", expected)
    preview = extract_preview(dng)
    assert preview.kind == "raw-embedded"
    assert preview.extension == ".jpg"
    with Image.open(BytesIO(preview.data)) as img:
        assert img.format == "JPEG"
        assert img.size == (256, 192)


def test_dng_preview_scores_as_detailed(tmp_path):
    """The extracted RAW preview feeds quality scoring like any other image."""
    from photo_cull.quality import BLUR_THRESHOLD, assess

    dng = make_dng_file(tmp_path / "sample.dng", detailed_array(256, 192))
    preview = extract_preview(dng)
    report = assess(preview.data)
    assert report.sharpness >= BLUR_THRESHOLD
    assert "blur_suspect" not in report.flags


# --------------------------------------------------------------------------
# Fallback logic (hermetic: fake rawpy module and stub exiftool binary)
# --------------------------------------------------------------------------


class _BrokenRawpy:
    """Stands in for rawpy when LibRaw cannot handle a file."""

    class ThumbFormat:
        JPEG = 0
        PNG = 1

    @staticmethod
    def imread(_path):
        raise RuntimeError("simulated LibRaw failure")


def _install_stub_exiftool(monkeypatch, payload: bytes, tmp_path):
    stub = tmp_path / "exiftool-stub.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.buffer.write({payload!r})\n"
    )
    stub.chmod(0o755)
    import photo_cull.previews as previews

    monkeypatch.setattr(previews.shutil, "which", lambda name: str(stub))


def test_raw_exiftool_fallback_when_rawpy_fails(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "rawpy", _BrokenRawpy)
    payload = b"\xff\xd8\xff\xe0FAKE"
    _install_stub_exiftool(monkeypatch, payload, tmp_path)

    p = tmp_path / "DSCF0001.RAF"
    p.write_bytes(b"unreadable raw")
    preview = extract_preview(p)
    assert preview.kind == "raw-exiftool"
    assert preview.data == payload
    assert preview.extension == ".jpg"


def test_raw_extraction_failure_raises_with_reasons(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "rawpy", _BrokenRawpy)
    import photo_cull.previews as previews

    monkeypatch.setattr(previews.shutil, "which", lambda name: None)

    p = tmp_path / "DSCF0002.RAF"
    p.write_bytes(b"unreadable raw")
    with pytest.raises(RuntimeError) as excinfo:
        extract_preview(p)
    assert "rawpy" in str(excinfo.value)
