"""Embedded preview extraction.

RAW files are opened read-only via rawpy (LibRaw) and their embedded JPEG
preview is extracted. If rawpy fails, an exiftool fallback is attempted when
exiftool is on PATH. Plain image files are used as-is.

Nothing in this module ever writes to the source file or directory.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .formats import classify


@dataclass
class Preview:
    """An extracted preview image."""

    data: bytes          # encoded image bytes (JPEG for RAW previews)
    kind: str            # "raw-embedded", "raw-exiftool", or "direct"
    extension: str       # best-known encoding, e.g. ".jpg"


def extract_preview(path: Path) -> Preview:
    """Extract the preview for any supported file.

    Raises ValueError for unsupported/unknown files and RuntimeError when
    no extraction route succeeds.
    """
    kind = classify(path)
    if kind == "direct":
        return Preview(path.read_bytes(), "direct", path.suffix.lower())
    if kind == "raw":
        return _extract_raw_preview(path)
    raise ValueError(f"unsupported file type: {path.name}")


def _extract_raw_preview(path: Path) -> Preview:
    errors: list[str] = []
    try:
        import rawpy
    except ImportError as exc:  # pragma: no cover - venv guarantees rawpy
        errors.append(f"rawpy import failed: {exc}")
    else:
        try:
            with rawpy.imread(str(path)) as raw:
                fmt, data = raw.extract_thumb()
            ext = ".jpg" if fmt == rawpy.ThumbFormat.JPEG else ".png"
            if data:
                return Preview(bytes(data), "raw-embedded", ext)
            errors.append("rawpy returned an empty thumbnail")
        except Exception as exc:  # noqa: BLE001 - LibRaw raises many types
            errors.append(f"rawpy: {type(exc).__name__}: {exc}")

    exiftool = shutil.which("exiftool")
    if exiftool:
        for tag in ("PreviewImage", "JpgFromRaw", "ThumbnailImage"):
            result = subprocess.run(
                [exiftool, "-b", f"-{tag}", str(path)],
                capture_output=True,
                timeout=60,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return Preview(result.stdout, "raw-exiftool", ".jpg")
            if result.stderr:
                errors.append(f"exiftool {tag}: {result.stderr.decode(errors='replace').strip()}")
    raise RuntimeError(
        f"no preview for {path.name}: " + ("; ".join(errors) or "unknown error")
    )
