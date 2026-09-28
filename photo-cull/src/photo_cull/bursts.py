"""Near-duplicate / burst grouping.

Every scored frame carries a 64-bit dHash of its preview (computed in
``quality.assess``). Frames whose hashes are within
``HASH_DISTANCE_THRESHOLD`` bits of each other are treated as
near-duplicates (burst frames); groups are built with single-link
clustering so a burst chains through its middle frames.

Capture time is handled in ``capture.py`` and only annotates groups here:
the grouping signal is purely visual.
"""

from __future__ import annotations

import re
from datetime import datetime

import numpy as np

# Two 64-bit dHashes within this many bits -> same burst (near-duplicate).
HASH_DISTANCE_THRESHOLD = 8

_SUGGESTION_RANK = {"keep": 0, "maybe": 1, "reject": 2}


def dhash(gray: np.ndarray, hash_size: int = 8) -> int:
    """64-bit difference hash: sign of each horizontal gradient.

    ``gray`` is any uint8 grayscale array; it is squeezed to
    (hash_size + 1) x hash_size before comparing neighbours, so the hash
    is stable across preview sizes.
    """
    import cv2  # local import keeps numpy-only use cheap elsewhere

    if gray.ndim == 3:  # pragma: no cover - callers pass grayscale
        gray = gray.mean(axis=2).astype(np.uint8)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two hashes."""
    return (a ^ b).bit_count()


def _entry_hash(entry: dict) -> int | None:
    """The entry's hash as an int (reports carry it as 16-hex-digit text)."""
    value = entry.get("quality", {}).get("hash")
    if value is None:
        return None
    return int(value, 16)


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------

def _find(parent: dict[str, str], item: str) -> str:
    root = item
    while parent[root] != root:
        root = parent[root]
    while parent[item] != root:  # path compression
        parent[item], item = root, parent[item]
    return root


def _union(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def group_bursts(entries: list[dict]) -> dict[str, list[dict]]:
    """Cluster scanned entries into burst groups.

    ``entries`` are scan report entries; only scored ones (with a hash)
    participate. Returns {group_id: [entries]} for groups of two or more;
    singletons are omitted (they are not bursts). Group ids are ``b1``,
    ``b2``, ... in order of the first member's path, so reports are
    deterministic.
    """
    scored = [e for e in entries if _entry_hash(e) is not None]
    scored.sort(key=lambda e: e["path"])
    parent = {e["path"]: e["path"] for e in scored}
    for i, a in enumerate(scored):
        for b in scored[i + 1:]:
            if hamming(_entry_hash(a), _entry_hash(b)) <= HASH_DISTANCE_THRESHOLD:
                _union(parent, a["path"], b["path"])

    clusters: dict[str, list[dict]] = {}
    for entry in scored:
        clusters.setdefault(_find(parent, entry["path"]), []).append(entry)

    groups = {root: members for root, members in clusters.items() if len(members) >= 2}
    ordered = sorted(groups.values(), key=lambda m: m[0]["path"])
    return {f"b{i}": members for i, members in enumerate(ordered, start=1)}


def best_frame(members: list[dict]) -> dict:
    """The technically best frame of a burst group.

    Rank by suggestion (keep < maybe < reject), then by sharpness (the
    best tile first), then path for determinism.
    """
    return min(
        members,
        key=lambda e: (
            _SUGGESTION_RANK.get(e["quality"]["suggestion"], 3),
            -e["quality"]["sharpness_max_tile"],
            -e["quality"]["sharpness"],
            e["path"],
        ),
    )


_SPAN_RE = re.compile(r"(\d+):(\d+):(\d+)[ T](\d+):(\d+):(\d+)")


def time_span_seconds(times: list[str | None]) -> float | None:
    """Span of the group's capture times, when at least two parse."""
    parsed: list[datetime] = []
    for t in times:
        if not t:
            continue
        m = _SPAN_RE.search(t)
        if m:
            y, mo, d, h, mi, s = (int(g) for g in m.groups())
            try:
                parsed.append(datetime(y, mo, d, h, mi, s))
            except ValueError:
                continue
    if len(parsed) < 2:
        return None
    return round((max(parsed) - min(parsed)).total_seconds(), 3)
