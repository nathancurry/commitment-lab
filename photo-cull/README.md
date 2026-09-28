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

`opencv-python-headless` (4.x) is required for face/eye detection; without
it the scan still works and simply omits the face check.

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
- **Burst grouping**: a 64-bit dHash of each preview; frames within 8 bits
  of each other are near-duplicates and are chained into burst groups
  (single-link clustering). Each group gets an id (`b1`, `b2`, ...), its
  members, a technically best frame (suggestion rank, then sharpness),
  and — when capture times are available — the group's time span.
  Capture time comes from EXIF `DateTimeOriginal` (JPEG via Pillow, RAW
  via `exiftool` when installed); absence is fine.
- **Closed eyes**: OpenCV Haar cascades (bundled, CPU) detect frontal
  faces; a face with no detected open eye raises `eyes_closed_suspect`.
  A coarse stage-1 heuristic: it only downgrades `keep` to `maybe`, never
  rejects, and awaits validation on real faces.
- **Suggestion**: `reject` if blur is suspected, `maybe` if exposure or
  eye flags, else `keep`. These are heuristic technical verdicts only —
  not taste.

## Status and calibration notes

- Thresholds (`BLUR_THRESHOLD = 40.0`, `CLIP_FRACTION_THRESHOLD = 0.02`,
  `NEAR_FLAT_VARIANCE = 1.0`, `HASH_DISTANCE_THRESHOLD = 8`) are
  placeholders pending calibration against the operator's real library
  and past culls (stage 2).
- Adding sensor-like noise *raises* the Laplacian sharpness metric, so a
  noisy but sharp frame can out-score its clean sibling within a burst;
  a noise-robust sharpness metric is a stage-2 consideration.
- The RAW extraction path is tested offline with a synthesized minimal DNG
  (validated against LibRaw and exiftool). Real Fujifilm RAF extraction is
  expected to work through the same LibRaw path but still needs verification
  on real files (`/data/photo-samples` when mounted).
- Face/eye detection is verified only for well-formed, crash-free behavior
  on synthetic images (OpenCV cannot detect synthetic faces); the decision
  logic is unit-tested with stub detections, and real-face validation
  needs the sample set.
- HEIC is not supported yet (needs `pillow-heif` if the library requires it).

## Privacy

Photos are private data: this tool processes them only with local code and
never uploads anything. Commit code, tests, and reports — never photos.
