# photo-cull

A local, read-only photo culling assistant. It scans a directory of photos,
extracts the embedded preview from RAW files, and scores technical quality.
It flags a technical suggestion (`keep` / `maybe` / `reject`) with reasons.
**It never modifies, writes to, or deletes anything in your library.**

Part of Commitment's active project (stage 1: previews and technical checks).
Stage 2 (taste learned from past culls) and stage 3 (editor output, e.g. XMP
sidecar ratings) come later.

## Install

Dependencies live in a gitignored venv inside this directory:

    cd photo-cull
    python3 -m venv .venv
    .venv/bin/pip install -e '.[test]'

## Usage

    .venv/bin/photo-cull scan /path/to/photos            # human summary
    .venv/bin/photo-cull scan /path/to/photos --json     # full JSON report
    .venv/bin/photo-cull scan /path/to/photos --output report.json --quiet

## What it checks (stage 1, technical only)

- **Preview extraction**: embedded JPEG from RAW containers (RAF, CR2/CR3,
  NEF, ARW, DNG, ORF, RW2, PEF, ...) via `rawpy`/LibRaw, with an `exiftool`
  fallback if available. Plain JPEG/PNG/TIFF are used directly.
- **Sharpness**: variance of the Laplacian on a size-normalized grayscale
  (global plus best 4x4 tile), flagging `blur_suspect` when below a
  threshold. Essentially featureless frames are not flagged as blurry.
- **Exposure**: mean luminance and shadow/highlight clipping fractions.
- **Suggestion**: `reject` if blur is suspected, `maybe` if exposure flags,
  else `keep`. These are heuristic technical verdicts only — not taste.

Closed-eye detection and burst grouping are not implemented yet.

## Status and calibration notes

- Thresholds (`BLUR_THRESHOLD = 40.0`, `CLIP_FRACTION_THRESHOLD = 0.02`,
  `NEAR_FLAT_VARIANCE = 1.0`) are placeholders pending calibration against
  the operator's real library and past culls (stage 2).
- The RAW extraction path is tested offline with a synthesized minimal DNG
  (validated against LibRaw and exiftool). Real Fujifilm RAF extraction is
  expected to work through the same LibRaw path but still needs verification
  on real files (`/data/photo-samples` when mounted).
- HEIC is not supported yet (needs `pillow-heif` if the library requires it).

## Privacy

Photos are private data: this tool processes them only with local code and
never uploads anything. Commit code, tests, and reports — never photos.
