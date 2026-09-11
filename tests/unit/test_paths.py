"""Tests for data-location resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from pippen import paths


def test_env_var_overrides_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert paths.data_root() == tmp_path.resolve()


def test_env_var_expands_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, "~/pippen-data")
    assert "~" not in str(paths.data_root())


def test_repo_checkout_is_used_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    checkout_data = tmp_path / "data"
    checkout_data.mkdir()
    monkeypatch.setattr(paths, "_repo_data_dir", lambda: checkout_data)
    assert paths.data_root() == checkout_data


def test_falls_back_to_user_cache_outside_a_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    # Installed copies of the package have no sibling data directory. Do not
    # assume a checkout layout here: mutation testing runs from mutants/,
    # where that assumption is false.
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.setattr(paths, "_repo_data_dir", lambda: None)
    assert paths.data_root().name == "pippen"


@pytest.mark.parametrize("stage", ["raw", "interim", "processed", "sources"])
def test_every_stage_resolves(stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert paths.stage_dir(stage) == tmp_path.resolve() / stage


def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown stage"):
        paths.stage_dir("nonsense")


def test_unknown_stage_error_lists_the_valid_stages() -> None:
    # The message is the only guidance a caller gets, so assert its content
    # rather than only its type.
    with pytest.raises(ValueError, match="expected one of") as caught:
        paths.stage_dir("nonsense")
    message = str(caught.value)
    for stage in ("raw", "interim", "processed", "sources"):
        assert stage in message


def test_stage_dir_creates_missing_parent_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A data root several levels deep must be created in full, not just its
    # last segment.
    nested = tmp_path / "does" / "not" / "exist" / "yet"
    monkeypatch.setenv(paths.ENV_VAR, str(nested))
    created = paths.stage_dir("raw", create=True)
    assert created.is_dir()
    assert created == nested.resolve() / "raw"


def test_stage_dir_creates_on_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    created = paths.stage_dir("raw", create=True)
    assert created.is_dir()


def test_stage_dir_does_not_create_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert not paths.stage_dir("interim").exists()


def test_season_file_names_include_dataset_and_season(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.season_file("raw", "play_by_play", 2024)
    assert target.name == "play_by_play_2024.parquet"
    assert target.parent.name == "play_by_play"


def test_stage_dir_creation_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Refresh jobs call this repeatedly. The second call must not raise.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    first = paths.stage_dir("processed", create=True)
    second = paths.stage_dir("processed", create=True)
    assert first == second
    assert second.is_dir()


def test_season_file_does_not_create_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Resolving a path must never have the side effect of making directories.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.season_file("raw", "play_by_play", 2024)
    assert not target.parent.exists()


def test_season_file_creates_parent_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.season_file("raw", "player_box", 2024, create=True)
    assert target.parent.is_dir()
    assert not target.exists()


def test_dataset_file_is_season_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Some sources publish one file covering every season. Giving it a
    # season-numbered path would store the same file once per season.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.dataset_file("raw", "schedules", "nba_schedule_master")
    assert target.name == "nba_schedule_master.parquet"
    assert target.parent.name == "schedules"


def test_dataset_file_does_not_create_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert not paths.dataset_file("raw", "schedules", "master").parent.exists()


def test_dataset_file_creates_parent_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.dataset_file("raw", "schedules", "master", create=True)
    assert target.parent.is_dir()
    assert not target.exists()
