"""Command line interface.

    photo-cull scan DIR [--output FILE] [--json] [--quiet]

Scans are read-only: DIR is never modified. The report goes to stdout
(human summary by default, JSON with --json) or to FILE with --output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .scan import scan_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-cull",
        description="Read-only photo culling assistant. Never modifies your library.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a directory and report technical quality")
    scan.add_argument("directory", type=Path, help="directory to scan (read-only)")
    scan.add_argument("--output", type=Path, default=None,
                      help="write the full JSON report to this file")
    scan.add_argument("--json", action="store_true",
                      help="print the full JSON report to stdout instead of a summary")
    scan.add_argument("--quiet", action="store_true",
                      help="print nothing to stdout (use with --output)")
    return parser


def print_summary(report: dict, stream) -> None:
    s = report["summary"]
    print(f"photo-cull {report['version']} scan of {report['scanned_dir']}")
    print(f"  files seen: {s['files_seen']}  scored: {s['scored']}  errors: {s['errors']}")
    print(f"  suggestions: {s['suggestions']}")
    if s["flags"]:
        print(f"  flags: {s['flags']}")
    for burst in report.get("bursts", []):
        best_name = Path(burst["best"]).name
        span = burst.get("time_span_seconds")
        span_text = f", span {span}s" if span is not None else ""
        print(f"  burst {burst['id']}: {burst['size']} near-duplicates, best {best_name}{span_text}")
    for entry in report["files"]:
        if entry.get("skipped"):
            print(f"  {entry['path']}: skipped ({entry['type']})")
        elif "quality" in entry:
            q = entry["quality"]
            burst = f" [{entry['burst']}]" if "burst" in entry else ""
            print(f"  {entry['path']}: {q['suggestion']}{burst} (sharpness {q['sharpness']}, flags {q['flags'] or 'none'})")
        else:
            print(f"  {entry['path']}: ERROR {entry['error']}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.directory
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    report = scan_directory(root)

    if args.output is not None:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not args.quiet:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_summary(report, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
