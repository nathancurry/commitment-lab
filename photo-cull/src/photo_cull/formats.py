"""File-type classification for photo libraries."""

from __future__ import annotations

from pathlib import Path

# RAW formats whose pixels live in a proprietary container. The embedded
# preview is extracted (never a full decode in stage 1).
RAW_EXTENSIONS = {
    ".raf",  # Fujifilm
    ".cr2", ".cr3",  # Canon
    ".crw",
    ".nef", ".nrw",  # Nikon
    ".arw", ".srf", ".sr2",  # Sony
    ".dng",  # Adobe / Leica / others
    ".orf",  # Olympus
    ".rw2",  # Panasonic
    ".pef", ".ptx",  # Pentax
    ".srw",  # Samsung
    ".x3f",  # Sigma
}

# Formats Pillow can open directly: the file itself is the image.
DIRECT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def classify(path) -> str:
    """Return "raw", "direct", or "unknown" for a file path (str or Path)."""
    ext = Path(path).suffix.lower()
    if ext in RAW_EXTENSIONS:
        return "raw"
    if ext in DIRECT_EXTENSIONS:
        return "direct"
    return "unknown"
