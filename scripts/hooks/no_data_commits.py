#!/usr/bin/env python3
"""Block data payloads from entering git history.

Data is distributed through releases, not through git. A Parquet file committed
once stays in history forever and cannot be removed without rewriting it.
"""

from __future__ import annotations

import sys
from pathlib import Path

BLOCKED_SUFFIXES = frozenset(
    {".parquet", ".csv", ".pkl", ".joblib", ".feather", ".arrow", ".h5", ".db", ".sqlite"}
)
ALLOWED_PREFIXES = ("tests/fixtures/", "docs/")


def main(argv: list[str]) -> int:
    """Return a non-zero exit code when a staged file looks like a data payload."""
    offenders = [
        name
        for name in argv
        if Path(name).suffix.lower() in BLOCKED_SUFFIXES and not name.startswith(ALLOWED_PREFIXES)
    ]
    if not offenders:
        return 0

    print("Refusing to commit data payloads:", file=sys.stderr)
    for name in offenders:
        print(f"  {name}", file=sys.stderr)
    print(
        "\nData belongs in a release, not in git history.\n"
        "Small test fixtures are allowed under tests/fixtures/.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
