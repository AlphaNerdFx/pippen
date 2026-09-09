"""Integrity checks on the manual source override registry.

The registry decides what the bibliography manifest claims about every citation
the archiver cannot fetch. A typo in it produces a manifest that quietly lies,
which is worse than no manifest at all.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERRIDES_PATH = REPO_ROOT / "scripts" / "source_overrides.json"
RESEARCH_DIR = REPO_ROOT / "docs" / "research"

VALID_STATUSES = {"manual", "replaced", "unavailable", "duplicate_of"}
NEEDS_A_FILE = {"manual", "replaced"}
VALID_KINDS = {"html", "pdf", "image", "url"}


def _load_script(name: str) -> ModuleType:
    """Import a file from scripts/ that is not part of the installed package.

    The module must be registered in ``sys.modules`` before it is executed.
    ``dataclasses`` looks its owning module up by name while building each
    class, and a module absent from the registry resolves to ``None``.
    """
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
def overrides() -> dict[str, dict[str, str]]:
    raw = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


@pytest.fixture(scope="module")
def cited_ids() -> set[str]:
    """Every SRC identifier that appears in the research bibliography."""
    found: set[str] = set()
    for path in RESEARCH_DIR.glob("*.md"):
        found.update(re.findall(r"SRC-\d+", path.read_text(encoding="utf-8", errors="replace")))
    return found


def test_registry_is_not_empty(overrides: dict[str, dict[str, str]]) -> None:
    assert overrides


def test_every_key_is_a_src_identifier(overrides: dict[str, dict[str, str]]) -> None:
    for key in overrides:
        assert re.fullmatch(r"SRC-\d+", key), key


def test_every_entry_refers_to_a_real_citation(
    overrides: dict[str, dict[str, str]], cited_ids: set[str]
) -> None:
    # Catches a typo'd identifier, which would otherwise silently annotate nothing.
    unknown = set(overrides) - cited_ids
    assert not unknown, f"not present in the bibliography: {sorted(unknown)}"


def test_every_status_is_recognised(overrides: dict[str, dict[str, str]]) -> None:
    for key, entry in overrides.items():
        assert entry.get("status") in VALID_STATUSES, f"{key}: {entry.get('status')!r}"


def test_retrieved_entries_declare_a_file_and_kind(overrides: dict[str, dict[str, str]]) -> None:
    for key, entry in overrides.items():
        if entry["status"] in NEEDS_A_FILE:
            assert entry.get("saved_from"), f"{key} has no saved_from"
            assert entry.get("kind") in VALID_KINDS, f"{key}: {entry.get('kind')!r}"


def test_unavailable_entries_explain_themselves(overrides: dict[str, dict[str, str]]) -> None:
    # An entry that says "unavailable" without a reason is an unanswered question.
    for key, entry in overrides.items():
        if entry["status"] == "unavailable":
            assert entry.get("reason"), f"{key} gives no reason"


def test_duplicates_name_their_original(overrides: dict[str, dict[str, str]]) -> None:
    for entry in overrides.values():
        if entry["status"] == "duplicate_of":
            assert entry.get("of") in overrides or re.fullmatch(r"SRC-\d+", entry.get("of", ""))


def test_replaced_entries_carry_a_replacement_url(overrides: dict[str, dict[str, str]]) -> None:
    for key, entry in overrides.items():
        if entry["status"] == "replaced":
            url = entry.get("replacement_url", "")
            assert url.startswith("https://"), f"{key}: {url!r}"


def test_corrected_urls_are_absolute(overrides: dict[str, dict[str, str]]) -> None:
    for key, entry in overrides.items():
        corrected = entry.get("corrected_url")
        if corrected is not None:
            assert corrected.startswith("https://"), f"{key}: {corrected!r}"


def test_no_two_entries_claim_the_same_file(overrides: dict[str, dict[str, str]]) -> None:
    files = [e["saved_from"] for e in overrides.values() if e.get("saved_from")]
    assert len(files) == len(set(files))


def test_slug_is_zero_padded_and_filesystem_safe() -> None:
    importer = _load_script("import_manual_sources")
    assert importer.slug_for("SRC-7", "Some File Name.pdf") == "SRC-007__some-file-name"
    assert importer.slug_for("SRC-221", "squared2020_2.txt") == "SRC-221__squared2020-2"


def test_slug_padding_keeps_identifiers_sortable() -> None:
    # Zero padding is what makes a directory listing sort in citation order.
    importer = _load_script("import_manual_sources")
    slugs = [importer.slug_for(f"SRC-{n}", "x.txt") for n in (7, 39, 221)]
    assert slugs == sorted(slugs)


def test_archiver_loads_the_same_registry(overrides: dict[str, dict[str, str]]) -> None:
    archiver = _load_script("archive_sources")
    assert archiver.load_overrides() == overrides
