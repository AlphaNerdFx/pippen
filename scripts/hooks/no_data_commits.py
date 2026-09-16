#!/usr/bin/env python3
"""Block data payloads from entering git history.

Data is distributed through releases, not through git. A Parquet file committed
once stays in history forever and cannot be removed without rewriting it.

Three paths are exempt, and every exemption is capped by size. The cap is what
keeps an exemption narrow: a directory allowed to hold a 40 KiB reference table
should not quietly become the place someone puts a 500 MiB season of
play-by-play. See docs/architecture/decisions/0006-shipping-computed-tables.md.
"""

from __future__ import annotations

import posixpath
import subprocess
import sys
from pathlib import Path
from typing import Final

BLOCKED_SUFFIXES: Final = frozenset(
    {".parquet", ".csv", ".pkl", ".joblib", ".feather", ".arrow", ".h5", ".db", ".sqlite"}
)

#: Prefixes allowed to carry a blocked suffix, each with the largest file it may
#: hold, in bytes.
ALLOWED_PREFIXES: Final = {
    "tests/fixtures/": 256 * 1024,
    "docs/": 256 * 1024,
    # The computed tables shipped inside the wheel. They have to be in git
    # because the wheel is built from git and rebuilding them needs hours of
    # rate-limited downloading that a CI runner cannot do.
    "src/pippen/_data/": 1024 * 1024,
}


def _staged_size(name: str) -> int | None:
    """Return the size of the blob git has staged for a path.

    The copy on disk is the wrong thing to measure. ``git add`` snapshots a file
    into the index and the commit records the index, so a file staged at 500 MiB
    and then truncated in the worktree passes a ``stat`` check and still enters
    history at its full size.

    Args:
        name: Path of a staged file, relative to the repository root.

    Returns:
        Size in bytes, or None when the path has no index entry, which is what a
        staged deletion looks like.
    """
    found = subprocess.run(
        ["git", "cat-file", "-s", f":{name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode != 0:
        return None
    return int(found.stdout.strip())


def _verdict(name: str) -> str | None:
    """Return why a staged file is refused, or None when it is acceptable.

    Args:
        name: Path of a staged file, relative to the repository root.

    Returns:
        A human-readable reason, or None.
    """
    # Match on the normalised path. A name like
    # "src/pippen/_data/../../../data/season.parquet" starts with an exempt
    # prefix while landing somewhere else entirely, so borrowing the exemption
    # is a matter of spelling unless the traversal is collapsed first.
    name = posixpath.normpath(name.replace("\\", "/"))

    if Path(name).suffix.lower() not in BLOCKED_SUFFIXES:
        return None

    for prefix, limit in ALLOWED_PREFIXES.items():
        if not name.startswith(prefix):
            continue
        size = _staged_size(name)
        # A staged deletion has no index entry and needs no size check.
        if size is None:
            return None
        if size > limit:
            return f"{size:,} bytes exceeds the {limit:,} byte cap for {prefix}"
        return None

    return "data belongs in a release, not in git history"


def main(argv: list[str]) -> int:
    """Return a non-zero exit code when a staged file looks like a data payload."""
    offenders = [(name, reason) for name in argv if (reason := _verdict(name)) is not None]
    if not offenders:
        return 0

    print("Refusing to commit data payloads:", file=sys.stderr)
    for name, reason in offenders:
        print(f"  {name}: {reason}", file=sys.stderr)
    allowed = ", ".join(
        f"{prefix} up to {limit // 1024} KiB" for prefix, limit in ALLOWED_PREFIXES.items()
    )
    print(f"\nAllowed with a size cap: {allowed}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
