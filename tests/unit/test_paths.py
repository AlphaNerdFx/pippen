"""Tests for data-location resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from nba_impact import paths


def test_env_var_overrides_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert paths.data_root() == tmp_path.resolve()


def test_env_var_expands_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, "~/nba-impact-data")
    assert "~" not in str(paths.data_root())


def test_repo_checkout_is_used_when_no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    root = paths.data_root()
    assert root.name == "data"


@pytest.mark.parametrize("stage", ["raw", "interim", "processed", "sources"])
def test_every_stage_resolves(stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert paths.stage_dir(stage) == tmp_path.resolve() / stage


def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown stage"):
        paths.stage_dir("nonsense")


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


def test_season_file_creates_parent_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.season_file("raw", "player_box", 2024, create=True)
    assert target.parent.is_dir()
    assert not target.exists()
