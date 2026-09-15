"""Tests for the command-line interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import typer
from typer.testing import CliRunner

from pippen import __version__, cli, paths
from pippen.cli import app
from pippen.data import hoopr

runner = CliRunner()


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_bare_invocation_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Reliability-adjusted NBA player impact" in result.stdout


def test_paths_lists_every_stage() -> None:
    result = runner.invoke(app, ["paths"])
    assert result.exit_code == 0
    for stage in ("raw", "interim", "processed", "sources"):
        assert stage in result.stdout


def test_commands_needing_a_season_range_refuse_to_guess() -> None:
    # `evaluate` previously defaulted its season range, so a bare invocation
    # started a multi-minute fit. A command that expensive should say what it
    # needs rather than assume.
    for argv in (["train"], ["evaluate"]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 2, argv


def test_a_command_exits_nonzero_when_its_inputs_are_missing() -> None:
    # 2015 has no stints on disk; data.nba.com does not serve it.
    result = runner.invoke(app, ["rapm", "--seasons", "2015-2024"])
    assert result.exit_code == 2


def test_parse_seasons_accepts_a_single_season() -> None:
    assert cli._parse_seasons("2024") == [2024]


def test_parse_seasons_expands_an_inclusive_range() -> None:
    assert cli._parse_seasons("2020-2023") == [2020, 2021, 2022, 2023]


@pytest.mark.parametrize("spec", ["", "abc", "2020-", "20-20-20", "2020-abc"])
def test_parse_seasons_rejects_nonsense(spec: str) -> None:
    with pytest.raises(typer.BadParameter):
        cli._parse_seasons(spec)


def test_parse_seasons_rejects_a_backwards_range() -> None:
    with pytest.raises(typer.BadParameter, match="runs backwards"):
        cli._parse_seasons("2024-2015")


@pytest.mark.parametrize("spec", ["1990", "2030", "1990-2030"])
def test_parse_seasons_rejects_seasons_hoopr_does_not_publish(spec: str) -> None:
    # Failing here beats 25 downloads that each 404 with no explanation.
    with pytest.raises(typer.BadParameter, match="falls outside"):
        cli._parse_seasons(spec)


def test_parse_seasons_accepts_the_full_published_range() -> None:
    first, last = hoopr.PLAY_BY_PLAY_FIRST_SEASON, hoopr.PLAY_BY_PLAY_LAST_SEASON
    assert cli._parse_seasons(f"{first}-{last}") == list(range(first, last + 1))


def test_fetch_rejects_an_unknown_dataset() -> None:
    result = runner.invoke(app, ["fetch", "--seasons", "2024", "--dataset", "not_a_table"])
    assert result.exit_code == 2
    assert "unknown dataset" in result.stdout


def test_season_schedule_returns_none_when_the_master_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert cli._season_schedule(2024) is None


def test_season_schedule_filters_the_master_to_one_season(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.dataset_file("raw", "schedules", "nba_schedule_master", create=True)
    pd.DataFrame({"game_id": [1, 2, 3], "season": [2023, 2024, 2024]}).to_parquet(target)
    rows = cli._season_schedule(2024)
    assert rows is not None
    assert len(rows) == 2


def test_season_schedule_returns_none_for_a_season_with_no_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # None means absent, which makes the checks report skipped rather than
    # passing on an empty table.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.dataset_file("raw", "schedules", "nba_schedule_master", create=True)
    pd.DataFrame({"game_id": [1], "season": [2023]}).to_parquet(target)
    assert cli._season_schedule(2024) is None


@pytest.mark.parametrize(
    ("seasons", "expected"),
    [
        ([], ""),
        ([2024], "2024"),
        ([2002, 2003, 2004], "2002-2004"),
        ([2002, 2003, 2009], "2002-2003, 2009"),
        ([2002, 2005, 2006, 2010], "2002, 2005-2006, 2010"),
    ],
)
def test_compact_collapses_runs_so_a_gap_is_visible(seasons: list[int], expected: str) -> None:
    # A flat list of twenty-five numbers hides which ones are missing. Runs
    # collapse so the gap is the thing a reader sees.
    assert cli._compact(seasons) == expected


def test_coefficient_exits_nonzero_when_nothing_is_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    result = runner.invoke(app, ["coefficient", "--seasons", "2024"])
    assert result.exit_code == 1
    assert "pippen fetch" in result.stdout


def test_coefficient_names_the_seasons_it_could_not_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Silently measuring four seasons when five were asked for would understate
    # the sample without saying so.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    result = runner.invoke(app, ["coefficient", "--seasons", "2020-2022"])
    assert "2020-2022" in result.stdout


def test_coefficient_measures_what_is_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    target = paths.season_file("raw", "play_by_play", 2024, create=True)
    pd.DataFrame(
        {
            "game_id": [1, 1, 1],
            "game_play_number": [1, 2, 3],
            "type_text": ["Free Throw - 1 of 2", "Free Throw - 2 of 2", "Defensive Rebound"],
            "scoring_play": [False, True, False],
            "shooting_play": [True, True, False],
        }
    ).to_parquet(target)

    result = runner.invoke(app, ["coefficient", "--seasons", "2024"])
    assert result.exit_code == 0
    assert "2024" in result.stdout
    assert "0.44" in result.stdout
