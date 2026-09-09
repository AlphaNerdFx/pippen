"""Tests for the bibliography archiver.

The archiver's job is to be honest about what it retrieved. Its most dangerous
failure is recording success for a page that is not the cited source, which is
what happened when FiveThirtyEight was shut down and every URL began redirecting
to a different publication's homepage while returning HTTP 200.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str) -> ModuleType:
    """Import a scripts/ file, registering it so dataclasses can resolve it."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def archiver() -> ModuleType:
    return _load_script("archive_sources")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://fivethirtyeight.com/features/x/", "fivethirtyeight.com"),
        ("https://www.fivethirtyeight.com/features/x/", "fivethirtyeight.com"),
        ("https://abcnews.com/politics", "abcnews.com"),
        ("http://squared2020.com:8080/a/b", "squared2020.com"),
        ("https://hoopr.sportsdataverse.org/reference/", "sportsdataverse.org"),
        ("https://localhost/x", "localhost"),
    ],
)
def test_registrable_domain(archiver: ModuleType, url: str, expected: str) -> None:
    assert archiver.registrable_domain(url) == expected


def test_subdomain_change_is_not_treated_as_a_move(archiver: ModuleType) -> None:
    # www to bare host is normal, not a hijack.
    assert archiver.registrable_domain("https://www.nba.com/x") == archiver.registrable_domain(
        "https://nba.com/x"
    )


def _response(url: str, status: int = 200, body: bytes = b"<html>ok</html>") -> SimpleNamespace:
    return SimpleNamespace(url=url, status_code=status, content=body)


def _session(response: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(get=lambda *a, **k: response)


def test_cross_domain_redirect_is_not_recorded_as_saved(
    archiver: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archiver, "OUTPUT_DIR", tmp_path)
    source = archiver.Source(
        src_id="SRC-97", title="A dead article", url="https://fivethirtyeight.com/features/x/"
    )
    archiver.classify(source)
    result = archiver.fetch(
        source, _session(_response("https://abcnews.com/politics")), dry_run=False
    )

    assert result.status == "redirected"
    assert "abcnews.com" in result.note
    assert result.saved_as is None
    assert not list(tmp_path.rglob("*.html"))


def test_same_domain_redirect_is_still_saved(
    archiver: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archiver, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(archiver, "POLITE_DELAY", 0)
    source = archiver.Source(src_id="SRC-1", title="Moved page", url="https://example.com/old")
    archiver.classify(source)
    result = archiver.fetch(
        source, _session(_response("https://www.example.com/new")), dry_run=False
    )

    assert result.status == "saved"
    assert result.saved_as is not None


@pytest.mark.parametrize("code", [401, 402, 403, 429])
def test_refusal_codes_are_blocked_not_dead(
    archiver: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    # A server refusing a script is not the same as a page that no longer exists.
    monkeypatch.setattr(archiver, "OUTPUT_DIR", tmp_path)
    source = archiver.Source(src_id="SRC-2", title="Refused", url="https://example.com/a")
    archiver.classify(source)
    result = archiver.fetch(
        source, _session(_response("https://example.com/a", code)), dry_run=False
    )
    assert result.status == "blocked"


def test_missing_page_is_dead(
    archiver: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archiver, "OUTPUT_DIR", tmp_path)
    source = archiver.Source(src_id="SRC-3", title="Gone", url="https://example.com/a")
    archiver.classify(source)
    result = archiver.fetch(
        source, _session(_response("https://example.com/a", 404)), dry_run=False
    )
    assert result.status == "dead"


def test_arxiv_urls_are_rewritten_to_the_pdf_endpoint(archiver: ModuleType) -> None:
    source = archiver.Source(
        src_id="SRC-34", title="L-RAPM", url="https://arxiv.org/abs/2601.15000"
    )
    archiver.classify(source)
    assert source.kind == "arxiv"
    assert source.url == "https://arxiv.org/pdf/2601.15000"


def test_slug_is_zero_padded(archiver: ModuleType) -> None:
    source = archiver.Source(src_id="SRC-9", title="x", url="https://example.com/a")
    assert source.slug.startswith("SRC-009__")
