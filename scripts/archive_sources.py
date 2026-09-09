#!/usr/bin/env python3
"""Archive the bibliography cited by the research documents.

A citation that has rotted is not a citation. This script walks every ``[SRC-N]``
reference in ``docs/research/``, resolves it to a URL, and saves what it can into
``data/sources/``. Anything it cannot save is listed in the manifest so a human
can save it from a browser.

Usage::

    python scripts/archive_sources.py --dry-run     # classify only, fetch nothing
    python scripts/archive_sources.py               # fetch everything reachable
    python scripts/archive_sources.py --wayback     # also request Wayback snapshots

Output::

    data/sources/pdf/SRC-046__arxiv-2305.13032.pdf
    data/sources/html/SRC-055__basketballbetstrategy-com.html
    data/sources/MANIFEST.md
    data/sources/manifest.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = REPO_ROOT / "docs" / "research"
OUTPUT_DIR = REPO_ROOT / "data" / "sources"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 pippen-source-archiver/1.0"
)
TIMEOUT = 30
MAX_WORKERS = 8
POLITE_DELAY = 0.4

# Rows of the reference tables look like: | SRC-46 | Title | https://... | Claims |
TABLE_ROW = re.compile(
    r"^\|\s*(SRC-\d+)\s*\|(?P<title>[^|]*)\|\s*(?P<url>https?://[^\s|]+)\s*\|",
    re.MULTILINE,
)
ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(?P<id>\d{4}\.\d{4,5})")


@dataclass
class Source:
    """One bibliography entry and the outcome of trying to archive it."""

    src_id: str
    title: str
    url: str
    kind: str = "unknown"  # pdf | arxiv | html
    status: str = "pending"  # saved | blocked | dead | skipped | error
    http_code: int | None = None
    saved_as: str | None = None
    note: str = ""
    corrected_url: str | None = None
    cited_in: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """Return a filesystem-safe name derived from the identifier and host."""
        arxiv = ARXIV_ID.search(self.url)
        tail = f"arxiv-{arxiv.group('id')}" if arxiv else urlparse(self.url).netloc
        tail = re.sub(r"[^A-Za-z0-9]+", "-", tail).strip("-").lower()
        number = int(self.src_id.split("-")[1])
        return f"SRC-{number:03d}__{tail}"


def collect_sources() -> list[Source]:
    """Parse every research document and return one Source per unique SRC id."""
    found: dict[str, Source] = {}
    for path in sorted(RESEARCH_DIR.glob("*.md")):
        for match in TABLE_ROW.finditer(path.read_text(encoding="utf-8", errors="replace")):
            src_id = match.group(1)
            url = match.group("url").rstrip(".,)")
            title = " ".join(match.group("title").split()).strip("* ")
            existing = found.get(src_id)
            if existing is None:
                found[src_id] = Source(src_id=src_id, title=title, url=url, cited_in=[path.name])
            else:
                if path.name not in existing.cited_in:
                    existing.cited_in.append(path.name)
                if existing.url != url:
                    existing.note = f"also cited as {url}"
    return sorted(found.values(), key=lambda s: int(s.src_id.split("-")[1]))


OVERRIDES_PATH = Path(__file__).resolve().parent / "source_overrides.json"


def load_overrides() -> dict[str, dict[str, str]]:
    """Return the hand-maintained outcomes for citations the script cannot fetch."""
    if not OVERRIDES_PATH.exists():
        return {}
    raw = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def apply_override(source: Source, entry: dict[str, str]) -> None:
    """Record a hand-retrieved or permanently unavailable outcome on a source.

    Applied before fetching, so the script does not re-request pages a human has
    already dealt with, and does not keep hammering servers that refuse it.
    """
    status = entry.get("status", "")
    source.note = entry.get("note") or entry.get("reason") or ""
    source.corrected_url = entry.get("corrected_url") or entry.get("replacement_url")

    if status == "manual":
        source.status = "manual"
    elif status == "replaced":
        source.status = "replaced"
    elif status == "duplicate_of":
        source.status = "duplicate"
        source.note = f"duplicate of {entry.get('of', 'another entry')}. {source.note}".strip()
    elif status == "unavailable":
        source.status = "unavailable"


def classify(source: Source) -> None:
    """Set ``kind`` and rewrite arXiv URLs to their PDF endpoint."""
    arxiv = ARXIV_ID.search(source.url)
    if arxiv:
        source.kind = "arxiv"
        source.url = f"https://arxiv.org/pdf/{arxiv.group('id')}"
    elif source.url.lower().endswith(".pdf"):
        source.kind = "pdf"
    else:
        source.kind = "html"


def display_path(path: Path) -> str:
    """Return a path relative to the repository when possible, else absolute.

    The archive normally sits inside the checkout, but the output directory is
    configurable and tests point it elsewhere. Assuming containment turns a
    relocated archive into a crash.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def registrable_domain(url: str) -> str:
    """Return the last two labels of a URL's host, lowercased.

    Enough to tell fivethirtyeight.com from abcnews.com without pulling in a
    public-suffix list. Subdomains are deliberately ignored, since a move from
    ``www.`` to a bare host is not a hijack.
    """
    host = urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def fetch(source: Source, session: requests.Session, *, dry_run: bool) -> Source:
    """Download one source, recording the outcome on the dataclass."""
    if dry_run:
        source.status = "skipped"
        return source

    suffix = "pdf" if source.kind in {"pdf", "arxiv"} else "html"
    target = OUTPUT_DIR / suffix / f"{source.slug}.{suffix}"

    if target.exists() and target.stat().st_size > 0:
        source.status = "saved"
        source.saved_as = display_path(target)
        source.note = "already present"
        return source

    try:
        response = session.get(source.url, timeout=TIMEOUT, allow_redirects=True)
        source.http_code = response.status_code
    except requests.RequestException as exc:
        source.status = "error"
        source.note = type(exc).__name__
        return source

    landed = registrable_domain(response.url)
    wanted = registrable_domain(source.url)
    if wanted and landed and wanted != landed:
        source.status = "redirected"
        source.note = (
            f"redirects off-site to {landed}; the original page is gone. "
            "Nothing useful can be archived."
        )
        return source

    if response.status_code in {401, 402, 403, 429}:
        source.status = "blocked"
        source.note = (
            "rate limited; save from a browser"
            if response.status_code == 429
            else "server refuses automated clients; save from a browser"
        )
        return source
    if response.status_code >= 400:
        source.status = "dead"
        source.note = f"HTTP {response.status_code}"
        return source
    if not response.content:
        source.status = "dead"
        source.note = "empty response"
        return source

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    source.status = "saved"
    source.saved_as = display_path(target)
    time.sleep(POLITE_DELAY)
    return source


def request_wayback(source: Source, session: requests.Session) -> None:
    """Ask the Internet Archive to snapshot a URL that could not be saved."""
    try:
        session.get(f"https://web.archive.org/save/{source.url}", timeout=TIMEOUT)
        source.note = f"{source.note}; wayback snapshot requested".lstrip("; ")
    except requests.RequestException:
        pass
    time.sleep(2.0)


def write_manifest(sources: list[Source]) -> None:
    """Write the human-readable and machine-readable manifests."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    by_status: dict[str, list[Source]] = {}
    for source in sources:
        by_status.setdefault(source.status, []).append(source)

    lines = [
        "# Archived sources",
        "",
        "Generated by `scripts/archive_sources.py`. Do not edit by hand.",
        "",
        "The archived files themselves are gitignored. Regenerate them with:",
        "",
        "```bash",
        "python scripts/archive_sources.py",
        "```",
        "",
        "## Summary",
        "",
        "| Outcome | Count |",
        "|---|---|",
    ]
    order = (
        "saved",
        "manual",
        "replaced",
        "duplicate",
        "unavailable",
        "blocked",
        "dead",
        "error",
        "skipped",
    )
    for status in order:
        if status in by_status:
            lines.append(f"| {status} | {len(by_status[status])} |")
    lines += ["", f"Total entries: {len(sources)}", ""]

    if by_status.get("manual"):
        lines += [
            "## Retrieved by hand",
            "",
            "These servers refuse automated clients, so a person saved them from a",
            "browser. See `scripts/source_overrides.json`.",
            "",
            "| SRC | Corrected URL | Note |",
            "|---|---|---|",
        ]
        for source in by_status["manual"]:
            corrected = f"<{source.corrected_url}>" if source.corrected_url else "unchanged"
            lines.append(f"| {source.src_id} | {corrected} | {source.note} |")
        lines.append("")

    if by_status.get("replaced"):
        lines += [
            "## Substituted sources",
            "",
            "The original is gone and a different page was used. **Read the note before",
            "relying on any of these**: a substitute is not automatically equivalent.",
            "",
            "| SRC | Replacement | Note |",
            "|---|---|---|",
        ]
        for source in by_status["replaced"]:
            lines.append(f"| {source.src_id} | <{source.corrected_url}> | {source.note} |")
        lines.append("")

    if by_status.get("redirected"):
        lines += [
            "## Redirected off-site",
            "",
            "The server answered, but with a different publication's page. The original",
            "is gone. These returned HTTP 200, which is why a naive archiver records them",
            "as saved.",
            "",
            "| SRC | Requested | Note |",
            "|---|---|---|",
        ]
        for source in by_status["redirected"]:
            lines.append(f"| {source.src_id} | <{source.url}> | {source.note} |")
        lines.append("")

    if by_status.get("unavailable") or by_status.get("duplicate"):
        lines += [
            "## Cannot be archived",
            "",
            "Permanently unavailable, or not a real source. Any claim resting on one of",
            "these needs a new citation or needs removing.",
            "",
            "| SRC | Reason |",
            "|---|---|",
        ]
        for source in by_status.get("unavailable", []) + by_status.get("duplicate", []):
            lines.append(f"| {source.src_id} | {source.note} |")
        lines.append("")

    if by_status.get("blocked"):
        lines += [
            "## Save these by hand",
            "",
            "These servers refuse automated clients. Open each in a browser and",
            "print to PDF into `data/sources/pdf/` using the filename given.",
            "",
            "| SRC | Save as | URL |",
            "|---|---|---|",
        ]
        for source in by_status["blocked"]:
            lines.append(f"| {source.src_id} | `{source.slug}.pdf` | <{source.url}> |")
        lines.append("")

    if by_status.get("dead") or by_status.get("error"):
        lines += [
            "## Broken citations",
            "",
            "These no longer resolve. A claim resting on one of these needs a new",
            "source or needs removing.",
            "",
            "| SRC | Problem | Title | URL |",
            "|---|---|---|---|",
        ]
        for source in by_status.get("dead", []) + by_status.get("error", []):
            lines.append(f"| {source.src_id} | {source.note} | {source.title} | <{source.url}> |")
        lines.append("")

    if by_status.get("saved"):
        lines += ["## Archived", "", "| SRC | Kind | File | Title |", "|---|---|---|---|"]
        for source in by_status["saved"]:
            lines.append(
                f"| {source.src_id} | {source.kind} | `{source.saved_as}` | {source.title} |"
            )
        lines.append("")

    (OUTPUT_DIR / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps([asdict(s) for s in sources], indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Entry point. Returns a non-zero code when nothing could be archived."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="classify without downloading")
    parser.add_argument("--wayback", action="store_true", help="request Wayback snapshots")
    parser.add_argument("--only", help="restrict to one SRC id, for example SRC-46")
    args = parser.parse_args()

    sources = collect_sources()
    if args.only:
        sources = [s for s in sources if s.src_id == args.only]
    if not sources:
        print("No sources found. Is docs/research/ populated?", file=sys.stderr)
        return 1

    for source in sources:
        classify(source)

    overrides = load_overrides()
    for source in sources:
        if source.src_id in overrides:
            apply_override(source, overrides[source.src_id])
    handled = {s.src_id for s in sources if s.status != "pending"}
    to_fetch = [s for s in sources if s.src_id not in handled]

    print(
        f"Found {len(sources)} unique citations across {len(list(RESEARCH_DIR.glob('*.md')))} documents."
    )

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    print(f"{len(handled)} handled by scripts/source_overrides.json, {len(to_fetch)} to fetch.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(fetch, s, session, dry_run=args.dry_run) for s in to_fetch]
        for done, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            print(f"  [{done:3d}/{len(to_fetch)}] {result.status:11s} {result.src_id}")

    if args.wayback:
        unreachable = [s for s in to_fetch if s.status in {"blocked", "dead", "error"}]
        print(f"Requesting Wayback snapshots for {len(unreachable)} unreachable sources.")
        for source in unreachable:
            request_wayback(source, session)

    if args.only:
        print("\n--only was used, so the manifest was left untouched.")
    else:
        write_manifest(sources)

    counts: dict[str, int] = {}
    for source in sources:
        counts[source.status] = counts.get(source.status, 0) + 1
    print("\nOutcome:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Manifest: {(OUTPUT_DIR / 'MANIFEST.md').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
