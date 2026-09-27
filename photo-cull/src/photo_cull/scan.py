"""Directory scanning: orchestrate preview extraction and scoring.

The scan is strictly read-only over the scanned tree; the only file it
touches is the report the user asks for, written outside this module.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import __version__
from .formats import classify
from .previews import extract_preview
from .quality import assess


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
        entry["quality"] = {
            "sharpness": round(quality.sharpness, 2),
            "sharpness_max_tile": round(quality.sharpness_max_tile, 2),
            "mean_luminance": round(quality.mean_luminance, 2),
            "shadow_clip_fraction": round(quality.shadow_clip_fraction, 5),
            "highlight_clip_fraction": round(quality.highlight_clip_fraction, 5),
            "flags": quality.flags,
            "suggestion": quality.suggestion,
        }
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop a scan
        entry["error"] = f"{type(exc).__name__}: {exc}"
    entry["seconds"] = round(time.monotonic() - started, 3)
    return entry


def scan_directory(root: Path) -> dict:
    """Scan a directory tree read-only and return the report as a dict."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    entries = [scan_file(p) for p in files]

    scored = [e for e in entries if "quality" in e]
    summary = {
        "files_seen": len(entries),
        "scored": len(scored),
        "skipped": sum(1 for e in entries if e.get("skipped")),
        "errors": sum(1 for e in entries if "error" in e),
        "suggestions": {},
        "flags": {},
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
        "files": entries,
    }
