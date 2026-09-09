#!/usr/bin/env python3
"""Remove AI assistant attribution trailers from a commit message.

This repository's policy is that its commit trailers name humans. Tooling that
appends its own co-authorship is stripped here, mechanically, so the policy does
not depend on anyone remembering it.

Deliberately narrow: it removes only the assistant-specific trailers. A
``Co-Authored-By`` line naming a person is left alone, because co-authorship
between people is real information and deleting it would be a lie in the other
direction.

Installed by pre-commit as a ``commit-msg`` hook, so it runs on every commit
regardless of who or what created it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Each pattern must match a whole line, anchored, so a mention inside prose
# survives and only a real trailer is removed.
TRAILERS = (
    re.compile(r"^Co-Authored-By:\s*Claude\b.*$", re.IGNORECASE),
    re.compile(r"^Claude-Session:\s*\S*$", re.IGNORECASE),
    re.compile(r"^Generated with \[Claude Code\].*$", re.IGNORECASE),
    re.compile(r"^\s*🤖\s*Generated with .*$"),
)


def strip_trailers(message: str) -> str:
    """Return the message with assistant trailers removed.

    Args:
        message: The raw commit message.

    Returns:
        The message without assistant trailers, with at most one blank line
        before the end and no trailing whitespace run.
    """
    kept = [line for line in message.splitlines() if not any(p.match(line) for p in TRAILERS)]

    # Removing trailers usually leaves a dangling blank line or two.
    while kept and not kept[-1].strip():
        kept.pop()

    return "\n".join(kept) + "\n" if kept else ""


def main(argv: list[str]) -> int:
    """Rewrite the commit message file in place. Returns 0 always.

    A commit-msg hook that fails blocks the commit. Stripping a trailer is
    never a reason to do that, so this reports and continues.
    """
    if not argv:
        print("strip_ai_trailers: no commit message file given", file=sys.stderr)
        return 0

    path = Path(argv[0])
    original = path.read_text(encoding="utf-8")
    cleaned = strip_trailers(original)

    if cleaned != original:
        path.write_text(cleaned, encoding="utf-8")
        removed = len(original.splitlines()) - len(cleaned.splitlines())
        print(f"strip_ai_trailers: removed {removed} attribution line(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
