"""End-to-end tests for scan_directory and the CLI."""

import hashlib
import json

from conftest import detailed_array, make_dng_file
from photo_cull.cli import main
from photo_cull.scan import scan_directory


def tree_state(root):
    """Hash of every file (path, bytes) below root: proves read-only scanning."""
    state = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            state[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return state


def test_scan_directory_report(sample_dir):
    report = scan_directory(sample_dir)
    assert report["tool"] == "photo-cull"
    s = report["summary"]
    assert s["files_seen"] == 6
    assert s["scored"] == 5          # 4 jpegs + 1 dng
    assert s["skipped"] == 1         # notes.txt
    assert s["errors"] == 0

    by_name = {f["path"].split("/")[-1]: f for f in report["files"]}
    assert by_name["sharp.jpg"]["quality"]["suggestion"] == "keep"
    assert by_name["blurred.jpg"]["quality"]["suggestion"] == "reject"
    assert "blur_suspect" in by_name["blurred.jpg"]["quality"]["flags"]
    assert "clipped_shadows" in by_name["black.jpg"]["quality"]["flags"]
    assert "clipped_highlights" in by_name["white.jpg"]["quality"]["flags"]
    assert by_name["black.jpg"]["quality"]["suggestion"] == "maybe"
    dng = by_name["sample_01.dng"]
    assert dng["preview"]["kind"] == "raw-embedded"
    assert dng["quality"]["suggestion"] == "keep"
    assert by_name["notes.txt"]["skipped"] is True


def test_scan_is_read_only(sample_dir):
    before = tree_state(sample_dir)
    report = scan_directory(sample_dir)
    after = tree_state(sample_dir)
    assert before == after
    assert set(report["summary"])  # report produced


def test_scan_nested_directories(tmp_path, sharp_jpeg_bytes):
    sub = tmp_path / "2026" / "trip"
    sub.mkdir(parents=True)
    (sub / "a.jpg").write_bytes(sharp_jpeg_bytes)
    report = scan_directory(tmp_path)
    assert report["summary"]["scored"] == 1
    assert report["files"][0]["path"].endswith("a.jpg")


def test_cli_scan_writes_output_and_summary(sample_dir, tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["scan", str(sample_dir), "--output", str(out)])
    assert rc == 0
    assert out.exists()
    report = json.loads(out.read_text())
    assert report["summary"]["scored"] == 5
    printed = capsys.readouterr().out
    assert "suggestions" in printed
    assert "sharp.jpg" in printed


def test_cli_scan_json_stdout(sample_dir, capsys):
    rc = main(["scan", str(sample_dir), "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["files_seen"] == 6


def test_cli_scan_quiet_with_output(sample_dir, tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["scan", str(sample_dir), "--output", str(out), "--quiet"])
    assert rc == 0
    assert capsys.readouterr().out == ""
    assert json.loads(out.read_text())["summary"]["scored"] == 5


def test_cli_rejects_missing_directory(tmp_path, capsys):
    rc = main(["scan", str(tmp_path / "nope")])
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_cli_dng_end_to_end(tmp_path, tmp_path_factory):
    """CLI over a directory whose only image is a RAW (DNG) file."""
    lib = tmp_path / "lib"
    lib.mkdir()
    make_dng_file(lib / "img.dng", detailed_array(256, 192))
    out = tmp_path / "report.json"
    rc = main(["scan", str(lib), "--output", str(out), "--quiet"])
    assert rc == 0
    report = json.loads(out.read_text())
    entry = report["files"][0]
    assert entry["preview"]["kind"] == "raw-embedded"
    assert "quality" in entry
