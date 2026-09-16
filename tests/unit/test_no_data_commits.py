"""Tests for the hook that keeps data payloads out of git history.

The hook guards a rule that cannot be un-broken. A Parquet file committed once
stays in history until someone rewrites it, so the cases worth pinning are the
ways a payload can look acceptable to a check that measures the wrong thing.

Two of them were live until a review of Phase 4 found them. The hook sized the
file on disk, so ``git add`` followed by ``truncate`` presented a zero-byte file
to the check while the index still held the payload the commit would record. And
matching the exemption prefix against the raw name let a path spelled
``src/pippen/_data/../../../data/x.parquet`` borrow an exemption it sits outside.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "no_data_commits.py"

#: The cap on src/pippen/_data/, from ALLOWED_PREFIXES.
CAP = 1024 * 1024

REFUSED = 1
ALLOWED = 0


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Return an empty repository with the exempt directory already present."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=tmp_path, check=True)
    (tmp_path / "src" / "pippen" / "_data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    return tmp_path


def _stage(repo: Path, name: str, size: int) -> None:
    """Write a file of the given size and stage it."""
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * size)
    subprocess.run(["git", "add", "-f", name], cwd=repo, check=True)


def _verdict(repo: Path, *names: str) -> int:
    """Return the hook's exit code over the given staged names."""
    return subprocess.run(
        [sys.executable, str(HOOK), *names],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def test_a_shipped_table_within_the_cap_is_allowed(repo: Path) -> None:
    _stage(repo, "src/pippen/_data/ratings.parquet", 227_822)
    assert _verdict(repo, "src/pippen/_data/ratings.parquet") == ALLOWED


def test_a_table_over_the_cap_is_refused(repo: Path) -> None:
    _stage(repo, "src/pippen/_data/season.parquet", CAP + 1)
    assert _verdict(repo, "src/pippen/_data/season.parquet") == REFUSED


def test_a_payload_staged_large_then_truncated_is_refused(repo: Path) -> None:
    """The commit records the index, so the index is what the cap must measure."""
    name = "src/pippen/_data/season.parquet"
    _stage(repo, name, CAP * 2)
    (repo / name).write_bytes(b"")
    assert (repo / name).stat().st_size == 0
    assert _verdict(repo, name) == REFUSED


def test_a_staged_deletion_is_allowed(repo: Path) -> None:
    """A deletion has no index entry to size, and removing data is never refused."""
    name = "src/pippen/_data/old.parquet"
    _stage(repo, name, 100)
    subprocess.run(["git", "commit", "-qm", "add"], cwd=repo, check=True)
    subprocess.run(["git", "rm", "-q", name], cwd=repo, check=True)
    assert _verdict(repo, name) == ALLOWED


def test_a_traversal_cannot_borrow_an_exemption(repo: Path) -> None:
    _stage(repo, "data/season.parquet", CAP * 2)
    assert _verdict(repo, "src/pippen/_data/../../../data/season.parquet") == REFUSED


def test_an_absolute_path_cannot_borrow_an_exemption(repo: Path) -> None:
    assert _verdict(repo, "/tmp/src/pippen/_data/season.parquet") == REFUSED


def test_data_outside_every_exemption_is_refused(repo: Path) -> None:
    _stage(repo, "data/season.parquet", 10)
    assert _verdict(repo, "data/season.parquet") == REFUSED


def test_a_source_file_is_untouched(repo: Path) -> None:
    _stage(repo, "src/pippen/published.py", CAP * 2)
    assert _verdict(repo, "src/pippen/published.py") == ALLOWED
