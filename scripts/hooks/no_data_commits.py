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


def _verdict(name: str) -> str | None:
    """Return why a staged file is refused, or None when it is acceptable.

    Args:
        name: Path of a staged file, relative to the repository root.

    Returns:
        A human-readable reason, or None.
    """
    if Path(name).suffix.lower() not in BLOCKED_SUFFIXES:
        return None

    for prefix, limit in ALLOWED_PREFIXES.items():
        if not name.startswith(prefix):
            continue
        path = Path(name)
        # A staged deletion has no file on disk and needs no size check.
        if not path.is_file():
            return None
        size = path.stat().st_size
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
