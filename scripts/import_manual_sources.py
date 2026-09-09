#!/usr/bin/env python3
"""Move hand-retrieved citation files into the source archive.

Some citations cannot be fetched by script: the server refuses automated
clients, the page is behind a session, or the original URL is dead and a
replacement had to be found by hand. Those files get dropped in the repository
root, and this moves them into ``data/sources/`` under the archive's naming
convention.

The mapping lives in ``scripts/source_overrides.json``, which is checked into
git so the knowledge survives regenerating the archive.

Usage::

    python scripts/import_manual_sources.py --dry-run
    python scripts/import_manual_sources.py
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = REPO_ROOT / "scripts" / "source_overrides.json"
OUTPUT_DIR = REPO_ROOT / "data" / "sources"

SUFFIX_FOR_KIND = {"html": ".html", "pdf": ".pdf", "image": ".png", "url": ".url.txt"}
SUBDIR_FOR_KIND = {"html": "html", "pdf": "pdf", "image": "image", "url": "url"}

# Recover the page's own address from the markup, so a hand-saved file still
# records where it came from even when the original citation URL is dead.
CANONICAL = re.compile(
    rb'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE
)
OG_URL = re.compile(
    rb'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE
)


def load_overrides() -> dict[str, dict[str, str]]:
    """Return the override registry, without its leading comment key."""
    raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def slug_for(src_id: str, source_name: str) -> str:
    """Return the archive filename stem for one citation."""
    number = int(src_id.split("-")[1])
    stem = Path(source_name).stem
    tail = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()[:60]
    return f"SRC-{number:03d}__{tail}"


def recover_url(path: Path) -> str | None:
    """Return the page's self-declared address, if the markup states one."""
    if path.suffix.lower() not in {".txt", ".html", ".htm"}:
        return None
    head = path.read_bytes()[:200_000]
    for pattern in (CANONICAL, OG_URL):
        found = pattern.search(head)
        if found:
            return found.group(1).decode("utf-8", errors="replace")
    return None


def main() -> int:
    """Move each declared file into the archive. Returns non-zero on any miss."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without moving")
    args = parser.parse_args()

    overrides = load_overrides()
    moved: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []

    for src_id, entry in sorted(overrides.items(), key=lambda kv: int(kv[0].split("-")[1])):
        status = entry.get("status")
        if status in {"unavailable", "duplicate_of"}:
            skipped.append(f"{src_id}: {status}")
            continue

        source_name = entry.get("saved_from")
        if not source_name:
            missing.append(f"{src_id}: no saved_from declared")
            continue

        origin = REPO_ROOT / source_name
        kind = entry.get("kind", "html")
        target = (
            OUTPUT_DIR
            / SUBDIR_FOR_KIND[kind]
            / f"{slug_for(src_id, source_name)}{SUFFIX_FOR_KIND[kind]}"
        )

        if not origin.exists():
            if target.exists():
                skipped.append(f"{src_id}: already imported")
            else:
                missing.append(f"{src_id}: {source_name} not found in the repository root")
            continue

        recovered = recover_url(origin)
        detail = f" (page reports {recovered})" if recovered else ""

        if args.dry_run:
            moved.append(f"{src_id}: {source_name} -> {target.relative_to(REPO_ROOT)}{detail}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origin), str(target))
        moved.append(f"{src_id}: {target.relative_to(REPO_ROOT)}{detail}")

    verb = "would import" if args.dry_run else "imported"
    print(f"{verb} {len(moved)}:")
    for line in moved:
        print(f"  {line}")

    if skipped:
        print(f"\nskipped {len(skipped)}:")
        for line in skipped:
            print(f"  {line}")

    if missing:
        print(f"\nMISSING {len(missing)}:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
