"""Capture-time extraction (read-only).

For direct files (JPEG/PNG/...), EXIF comes from Pillow. For RAW files,
Pillow cannot read metadata, so ``exiftool`` is used when it is on PATH
(same fallback policy as preview extraction).

Capture time is optional metadata: absence is normal and never an error.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

# EXIF DateTimeOriginal (in the Exif sub-IFD) then DateTime (IFD0).
_EXIF_DATETIME_ORIGINAL = 36868
_EXIF_DATETIME = 306

_EXIF_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def parse_exif_datetime(value: str | None) -> datetime | None:
    """Parse common EXIF datetime strings ("2026:09:27 10:00:00", ISO-ish)."""
    if not value:
        return None
    for fmt in _EXIF_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _direct_capture_time(path: Path) -> str | None:
    from PIL import Image

    try:
        with Image.open(path) as img:
            exif = img.getexif()
    except Exception:  # noqa: BLE001 - unreadable metadata is not fatal
        return None
    sub = exif.get_ifd(0x8769)
    for source in (sub, exif):
        for tag in (_EXIF_DATETIME_ORIGINAL, _EXIF_DATETIME):
            value = source.get(tag)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _raw_capture_time(path: Path) -> str | None:
    import shutil

    exiftool = shutil.which("exiftool")
    if not exiftool:
        return None
    try:
        result = subprocess.run(
            # exiftool calls IFD0 tag 306 "ModifyDate"; DateTimeOriginal
            # (Exif sub-IFD 36867) is the preferred, more precise tag.
            [exiftool, "-s3", "-DateTimeOriginal", "-ModifyDate", str(path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception:  # noqa: BLE001 - a broken exiftool must not stop a scan
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.decode(errors="replace").splitlines():
        value = line.strip()
        if value:
            return value
    return None


def capture_time(path: Path, kind: str) -> str | None:
    """Capture time string for a file, or None when unavailable."""
    if kind == "direct":
        return _direct_capture_time(path)
    if kind == "raw":
        return _raw_capture_time(path)
    return None
