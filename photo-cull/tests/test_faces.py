"""Tests for face / closed-eye detection.

OpenCV cannot reliably detect faces in synthetic images, so the decision
logic is tested as a pure function with stub observations, the merge into
the scan report is tested with a monkeypatched detector, and the real
cascade path is smoke-tested for well-formed, non-crashing behavior.
Real-face validation awaits the sample set (requests/photo-culling-inputs.md).
"""

import numpy as np
import pytest

from conftest import detailed_array
from photo_cull.faces import FaceObservation, FaceReport, assess_faces, eye_flags
from photo_cull.quality import load_grayscale, suggestion_from_flags
from photo_cull.scan import scan_directory


# ---------------------------------------------------------------- pure logic


def test_no_faces_no_flags():
    assert eye_flags([]) == []


def test_all_faces_with_closed_eyes_flagged():
    obs = [FaceObservation(box=(0, 0, 100, 100)), FaceObservation(box=(200, 0, 100, 100))]
    assert eye_flags(obs) == ["eyes_closed_suspect"]


def test_any_open_eye_clears_flag():
    obs = [FaceObservation(box=(0, 0, 100, 100)), FaceObservation(box=(200, 0, 100, 100), open_eyes=1)]
    assert eye_flags(obs) == []


def test_eye_flag_downgrades_keep_to_maybe():
    assert suggestion_from_flags(["eyes_closed_suspect"]) == "maybe"


# ---------------------------------------------------------------- cascade path


def detailed_array_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(detailed_array(), mode="L").convert("RGB").save(
        buf, "JPEG", quality=95
    )
    return buf.getvalue()


def test_cascade_detection_runs_and_is_well_formed():
    pytest.importorskip("cv2")
    gray = load_grayscale(detailed_array_bytes())
    report = assess_faces(gray)
    assert isinstance(report, FaceReport)
    assert report.faces >= 0
    assert report.open_eyes >= 0
    assert isinstance(report.flags, list)


def test_faceless_images_get_no_eye_flags(sharp_jpeg_bytes, black_jpeg_bytes):
    pytest.importorskip("cv2")
    for data in (sharp_jpeg_bytes, black_jpeg_bytes):
        gray = load_grayscale(data)
        report = assess_faces(gray)
        assert report.faces == 0, "synthetic patterns must not be seen as faces"
        assert report.flags == []


# ---------------------------------------------------------------- scan merge


def test_scan_merges_closed_eye_flag(monkeypatch, tmp_path, sharp_jpeg_bytes):
    """A detector finding a closed-eye face must downgrade keep -> maybe."""
    (tmp_path / "a.jpg").write_bytes(sharp_jpeg_bytes)
    import photo_cull.scan as scan_mod

    def fake_assess_faces(gray):
        return FaceReport(faces=1, open_eyes=0, flags=["eyes_closed_suspect"])

    monkeypatch.setattr(scan_mod, "assess_faces", fake_assess_faces)
    report = scan_directory(tmp_path)
    entry = report["files"][0]
    assert entry["face_check"] == {
        "faces": 1, "open_eyes": 0, "flags": ["eyes_closed_suspect"],
    }
    assert "eyes_closed_suspect" in entry["quality"]["flags"]
    assert entry["quality"]["suggestion"] == "maybe"


def test_scan_reports_face_check(tmp_path, sharp_jpeg_bytes):
    pytest.importorskip("cv2")
    (tmp_path / "a.jpg").write_bytes(sharp_jpeg_bytes)
    report = scan_directory(tmp_path)
    entry = report["files"][0]
    assert entry["face_check"]["faces"] == 0
    assert entry["face_check"]["flags"] == []
    assert entry["quality"]["suggestion"] == "keep"
