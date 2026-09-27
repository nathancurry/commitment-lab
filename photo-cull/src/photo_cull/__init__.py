"""photo-cull: read-only photo culling assistant.

Stage 1: extract embedded previews from RAW files and score technical
quality (sharpness, exposure clipping). It never modifies, writes to, or
deletes anything in the scanned library.
"""

__version__ = "0.1.0"
