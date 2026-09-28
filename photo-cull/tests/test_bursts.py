"""Tests for dHash, burst grouping, and capture-time extraction."""

import numpy as np
import pytest

from conftest import (
    detailed_array,
    encode_jpeg,
    make_dng_file,
    perturb,
    write_exif_jpeg,
)
from photo_cull.bursts import (
    HASH_DISTANCE_THRESHOLD,
    best_frame,
    dhash,
    hamming,
    time_span_seconds,
)
from photo_cull.quality import assess
from photo_cull.scan import scan_directory

# ---------------------------------------------------------------- dHash


def test_dhash_stable_under_burst_perturbations():
    base = detailed_array()
    base_hash = assess(encode_jpeg(base)).dhash
    variants = [
        perturb(base, noise=6.0, seed=3),
        perturb(base, brightness=8.0, noise=4.0, seed=4),
        perturb(base, blur=2.0, noise=4.0, seed=5),
    ]
    for i, arr in enumerate(variants):
        h = assess(encode_jpeg(arr)).dhash
        assert hamming(base_hash, h) <= HASH_DISTANCE_THRESHOLD, f"variant {i}"


def test_dhash_separates_distinct_structures():
    h, w = 768, 1024
    x = np.arange(w)[None, :]
    y = np.arange(h)[:, None]
    base_hash = assess(encode_jpeg(detailed_array())).dhash
    stripes = {
        "vertical": (((x // 40) % 2 * 120 + 60) * np.ones((h, w))).astype(np.uint8),
        "horizontal": (((y // 40) % 2 * 120 + 60) * np.ones((h, w))).astype(np.uint8),
        "diagonal": (((x // 40) + (y // 40)) % 2 * 120 + 60).astype(np.uint8),
    }
    for name, arr in stripes.items():
        hsh = assess(encode_jpeg(arr)).dhash
        assert hamming(base_hash, hsh) > HASH_DISTANCE_THRESHOLD, name


def test_dhash_is_stable_across_sizes():
    """The same content at two preview sizes hashes (nearly) identically."""
    arr = detailed_array(512, 384)
    big = assess(encode_jpeg(arr)).dhash
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(arr, mode="L").convert("RGB").resize(
        (1024, 768)
    ).save(buf, "JPEG", quality=95)
    small = assess(buf.getvalue()).dhash
    assert hamming(big, small) <= HASH_DISTANCE_THRESHOLD


# ---------------------------------------------------------------- grouping


@pytest.fixture
def burst_dir(tmp_path):
    """A synthetic burst of 4 + two distinct stripe images."""
    base = detailed_array()
    members = {
        "img_0001.jpg": base,                              # clean reference frame
        "img_0002.jpg": perturb(base, noise=6.0, seed=3),
        "img_0003.jpg": perturb(base, brightness=8.0, seed=4),
        "img_0004.jpg": perturb(base, blur=2.0, seed=5),
    }
    for name, arr in members.items():
        (tmp_path / name).write_bytes(encode_jpeg(arr))
    h, w = 768, 1024
    x = np.arange(w)[None, :]
    y = np.arange(h)[:, None]
    (tmp_path / "stripes_v.jpg").write_bytes(
        encode_jpeg((((x // 40) % 2 * 120 + 60) * np.ones((h, w))).astype(np.uint8))
    )
    (tmp_path / "stripes_h.jpg").write_bytes(
        encode_jpeg((((y // 40) % 2 * 120 + 60) * np.ones((h, w))).astype(np.uint8))
    )
    return tmp_path


def test_synthetic_burst_groups_together(burst_dir):
    report = scan_directory(burst_dir)
    bursts = report["bursts"]
    assert len(bursts) == 1
    burst = bursts[0]
    assert burst["size"] == 4
    assert {m.split("/")[-1] for m in burst["members"]} == {
        "img_0001.jpg", "img_0002.jpg", "img_0003.jpg", "img_0004.jpg",
    }


def test_distinct_images_stay_out_of_bursts(burst_dir):
    report = scan_directory(burst_dir)
    burst_members = {
        m.split("/")[-1] for burst in report["bursts"] for m in burst["members"]
    }
    assert "stripes_v.jpg" not in burst_members
    assert "stripes_h.jpg" not in burst_members
    for entry in report["files"]:
        if entry["path"].split("/")[-1].startswith("stripes"):
            assert "burst" not in entry


def test_best_frame_is_sharpest_member(burst_dir):
    report = scan_directory(burst_dir)
    assert len(report["bursts"]) == 1
    burst = report["bursts"][0]
    by_path = {e["path"]: e for e in report["files"]}
    ranked = sorted(
        burst["members"],
        key=lambda p: (
            {"keep": 0, "maybe": 1, "reject": 2}[by_path[p]["quality"]["suggestion"]],
            -by_path[p]["quality"]["sharpness_max_tile"],
            -by_path[p]["quality"]["sharpness"],
            p,
        ),
    )
    assert burst["best"] == ranked[0]


def test_summary_counts_bursts(burst_dir):
    report = scan_directory(burst_dir)
    assert report["summary"]["bursts"] == 1
    assert report["summary"]["burst_frames"] == 4


def test_best_frame_prefers_keep_over_sharper_reject():
    members = [
        {"path": "a", "quality": {"suggestion": "reject", "sharpness_max_tile": 999.0, "sharpness": 999.0}},
        {"path": "b", "quality": {"suggestion": "keep", "sharpness_max_tile": 1.0, "sharpness": 1.0}},
    ]
    assert best_frame(members)["path"] == "b"


def test_group_ids_are_deterministic(burst_dir):
    one = scan_directory(burst_dir)["bursts"]
    two = scan_directory(burst_dir)["bursts"]
    assert [b["id"] for b in one] == [b["id"] for b in two]


# ---------------------------------------------------------------- capture time


def test_capture_time_from_jpeg_exif(tmp_path):
    write_exif_jpeg(
        tmp_path / "a.jpg", detailed_array(256, 192), "2026:09:27 10:00:00"
    )
    report = scan_directory(tmp_path)
    entry = report["files"][0]
    assert entry["capture_time"] == "2026:09:27 10:00:00"


def test_capture_time_missing_is_absent_safe(tmp_path, sharp_jpeg_bytes):
    (tmp_path / "plain.jpg").write_bytes(sharp_jpeg_bytes)
    report = scan_directory(tmp_path)
    assert "capture_time" not in report["files"][0]


def test_capture_time_from_dng_via_exiftool(tmp_path):
    pytest.importorskip("shutil")
    import shutil

    if not shutil.which("exiftool"):
        pytest.skip("exiftool not available")
    make_dng_file(
        tmp_path / "raw.dng", detailed_array(256, 192),
        datetime="2026:09:27 10:00:05",
    )
    report = scan_directory(tmp_path)
    assert report["files"][0]["capture_time"] == "2026:09:27 10:00:05"


def test_burst_time_span_computed(tmp_path):
    base = detailed_array(256, 192)
    for name, seconds in (("a.jpg", "2026:09:27 10:00:00"),
                          ("b.jpg", "2026:09:27 10:00:01"),
                          ("c.jpg", "2026:09:27 10:00:04")):
        write_exif_jpeg(tmp_path / name, perturb(base, seed=hash(name) % 100), seconds)
    report = scan_directory(tmp_path)
    assert len(report["bursts"]) == 1
    assert report["bursts"][0]["time_span_seconds"] == 4.0


def test_time_span_seconds_parsing():
    assert time_span_seconds(["2026:09:27 10:00:00", "2026:09:27 10:00:02"]) == 2.0
    assert time_span_seconds([None, None]) is None
    assert time_span_seconds(["garbage", "2026:09:27 10:00:00"]) is None
    assert time_span_seconds([]) is None
