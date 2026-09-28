"""Directory scanning: orchestrate preview extraction and scoring.

The scan is strictly read-only over the scanned tree; the only file it
touches is the report the user asks for, written outside this module.

Stage-1 pipeline per file: preview -> technical quality (+ dHash) ->
capture time (EXIF, optional) -> face/eye check (optional, OpenCV).
Across files: near-duplicate frames are grouped into bursts, each burst
gets a technically best frame.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import __version__
from .bursts import best_frame, group_bursts, time_span_seconds
from .capture import capture_time
from .faces import available as faces_available
from .faces import assess_faces
from .formats import classify
from .previews import extract_preview
from .quality import assess, suggestion_from_flags


def scan_file(path: Path) -> dict:
    """Build the report entry for one image file. Never raises."""
    entry: dict = {"path": str(path), "type": classify(path)}
    if entry["type"] == "unknown":
        entry["skipped"] = True
        return entry
    started = time.monotonic()
    try:
        preview = extract_preview(path)
        entry["preview"] = {"kind": preview.kind, "encoding": preview.extension}
        quality = assess(preview.data)
        flags = list(quality.flags)
        face = _face_entry(preview.data, flags)
        if face is not None:
            entry["face_check"] = face
        entry["quality"] = {
            "sharpness": round(quality.sharpness, 2),
            "sharpness_max_tile": round(quality.sharpness_max_tile, 2),
            "mean_luminance": round(quality.mean_luminance, 2),
            "shadow_clip_fraction": round(quality.shadow_clip_fraction, 5),
            "highlight_clip_fraction": round(quality.highlight_clip_fraction, 5),
            "hash": f"{quality.dhash:016x}",
            "flags": flags,
            "suggestion": suggestion_from_flags(flags),
        }
        captured = capture_time(path, entry["type"])
        if captured:
            entry["capture_time"] = captured
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop a scan
        entry["error"] = f"{type(exc).__name__}: {exc}"
    entry["seconds"] = round(time.monotonic() - started, 3)
    return entry


def _face_entry(preview_data: bytes, flags: list[str]) -> dict | None:
    """Face/eye check on the preview; appends its flags to ``flags``.

    Returns None when OpenCV is unavailable. Never raises.
    """
    if not faces_available():
        return None
    try:
        from .quality import load_grayscale

        report = assess_faces(load_grayscale(preview_data))
    except Exception:  # noqa: BLE001 - a bad cascade run must not stop a scan
        return None
    flags.extend(report.flags)
    return {"faces": report.faces, "open_eyes": report.open_eyes, "flags": report.flags}


def scan_directory(root: Path) -> dict:
    """Scan a directory tree read-only and return the report as a dict."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    entries = [scan_file(p) for p in files]

    bursts = group_bursts(entries)
    burst_list = []
    for group_id, members in bursts.items():
        for member in members:
            member["burst"] = group_id
        best = best_frame(members)
        burst_list.append({
            "id": group_id,
            "size": len(members),
            "members": [m["path"] for m in members],
            "best": best["path"],
            "time_span_seconds": time_span_seconds(
                m.get("capture_time") for m in members
            ),
        })

    scored = [e for e in entries if "quality" in e]
    summary = {
        "files_seen": len(entries),
        "scored": len(scored),
        "skipped": sum(1 for e in entries if e.get("skipped")),
        "errors": sum(1 for e in entries if "error" in e),
        "suggestions": {},
        "flags": {},
        "bursts": len(burst_list),
        "burst_frames": sum(len(m) for m in bursts.values()),
    }
    for entry in scored:
        q = entry["quality"]
        summary["suggestions"][q["suggestion"]] = (
            summary["suggestions"].get(q["suggestion"], 0) + 1
        )
        for flag in q["flags"]:
            summary["flags"][flag] = summary["flags"].get(flag, 0) + 1

    return {
        "tool": "photo-cull",
        "version": __version__,
        "scanned_dir": str(root),
        "summary": summary,
        "bursts": burst_list,
        "files": entries,
    }
