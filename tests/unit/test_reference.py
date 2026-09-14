"""Tests for the external stint reference and the gate comparison.

The reference file is not in the repository, so these build small frames in the
shape the real file has. What matters is the conversion: the reference records
one row per stint with both teams' points, this project records one row per
lineup matchup with an offensive side, and getting the split wrong would make
the gate compare the wrong things while still producing a number.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pippen.rapm.possessions import STINT_COLUMNS, possessions_by_player
from pippen.rapm.reference import (
    ReferenceFormatError,
    compare_ratings,
    load_reference_stints,
)

# ------------------------------------------------------------------ helpers


def _reference_file(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "stints.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _row(
    game_id: str = "0022200002",
    home: str = "1_2_3_4_5",
    away: str = "6_7_8_9_10",
    n_pos: int = 14,
    home_points: int = 5,
    away_points: int = 2,
) -> dict[str, object]:
    return {
        "game_id": game_id,
        "home_lineup": home,
        "away_lineup": away,
        "n_pos": n_pos,
        "home_points": home_points,
        "away_points": away_points,
    }


def _ratings(values: dict[int, float]) -> pd.DataFrame:
    return pd.DataFrame({"player_id": list(values), "total": list(values.values())})


# ------------------------------------------------------------------ conversion


def test_each_reference_stint_becomes_two_rows(tmp_path: Path) -> None:
    converted = load_reference_stints(_reference_file(tmp_path, [_row(), _row()]))
    assert len(converted) == 4
    assert list(converted.columns) == list(STINT_COLUMNS)


def test_each_team_gets_its_own_points_when_on_offence(tmp_path: Path) -> None:
    converted = load_reference_stints(
        _reference_file(tmp_path, [_row(home_points=5, away_points=2)])
    )
    home_row = converted[converted["offense_lineup"] == "1-2-3-4-5"].iloc[0]
    away_row = converted[converted["offense_lineup"] == "6-7-8-9-10"].iloc[0]
    assert home_row["points"] == 5
    assert away_row["points"] == 2
    assert home_row["defense_lineup"] == "6-7-8-9-10"
    assert away_row["defense_lineup"] == "1-2-3-4-5"


def test_possessions_are_halved_because_the_reference_counts_them_once(
    tmp_path: Path,
) -> None:
    # n_pos is the stint's possessions shared by both teams, so each converted
    # row takes half. Carrying the full count would double every weight.
    converted = load_reference_stints(_reference_file(tmp_path, [_row(n_pos=14)]))
    assert set(converted["possessions"]) == {7.0}


def test_lineup_separators_are_rewritten(tmp_path: Path) -> None:
    converted = load_reference_stints(_reference_file(tmp_path, [_row()]))
    assert "_" not in "".join(converted["offense_lineup"])
    assert "-" in converted["offense_lineup"].iloc[0]


def test_a_missing_column_is_named(tmp_path: Path) -> None:
    path = tmp_path / "stints.csv"
    pd.DataFrame([{"game_id": "1", "home_lineup": "1_2_3_4_5"}]).to_csv(path, index=False)
    with pytest.raises(ReferenceFormatError, match="missing columns"):
        load_reference_stints(path)


def test_a_missing_file_explains_where_to_get_it(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="validation-only"):
        load_reference_stints(tmp_path / "absent.csv")


# ------------------------------------------------------------------ possessions


def test_every_player_on_the_floor_is_credited() -> None:
    stints = pd.DataFrame(
        [
            {
                "offense_lineup": "1-2-3-4-5",
                "defense_lineup": "6-7-8-9-10",
                "possessions": 10,
            },
            {
                "offense_lineup": "1-2-3-4-11",
                "defense_lineup": "6-7-8-9-10",
                "possessions": 5,
            },
        ]
    )
    counts = possessions_by_player(stints)
    assert counts.loc[1] == 15
    assert counts.loc[5] == 10
    assert counts.loc[11] == 5
    assert counts.loc[6] == 15
    assert counts.sum() == 150  # ten players per possession


def test_an_empty_frame_gives_an_empty_count() -> None:
    assert possessions_by_player(pd.DataFrame(columns=list(STINT_COLUMNS))).empty


# ------------------------------------------------------------------ the gate


def _floor(players: list[int], value: float = 2000.0) -> pd.Series:
    return pd.Series(dict.fromkeys(players, value), name="possessions")


def test_identical_ratings_correlate_perfectly() -> None:
    values = {1: 3.0, 2: 1.0, 3: -1.0, 4: -3.0, 5: 0.5}
    result = compare_ratings(
        _ratings(values),
        _ratings(values),
        project_possessions=_floor(list(values)),
        reference_possessions=_floor(list(values)),
    )
    assert result.spearman == pytest.approx(1.0)
    assert result.passed
    assert result.mean_absolute_difference == pytest.approx(0.0)


def test_rank_agreement_survives_a_difference_of_scale() -> None:
    # A different ridge penalty shrinks every rating by a different amount
    # without changing the order, which is why rank is the headline.
    ours = {1: 3.0, 2: 1.0, 3: -1.0, 4: -3.0}
    theirs = {player: value / 2 for player, value in ours.items()}
    result = compare_ratings(
        _ratings(ours),
        _ratings(theirs),
        project_possessions=_floor(list(ours)),
        reference_possessions=_floor(list(ours)),
    )
    assert result.spearman == pytest.approx(1.0)
    assert result.mean_absolute_difference > 0


def test_reversed_ratings_fail_the_gate() -> None:
    ours = {1: 3.0, 2: 1.0, 3: -1.0, 4: -3.0}
    theirs = {1: -3.0, 2: -1.0, 3: 1.0, 4: 3.0}
    result = compare_ratings(
        _ratings(ours),
        _ratings(theirs),
        project_possessions=_floor(list(ours)),
        reference_possessions=_floor(list(ours)),
    )
    assert result.spearman == pytest.approx(-1.0)
    assert not result.passed
    assert "FAIL" in result.describe()


def test_players_below_the_possession_floor_are_excluded() -> None:
    values = {1: 3.0, 2: 1.0, 3: -1.0, 4: -3.0}
    low = pd.Series({1: 5000.0, 2: 5000.0, 3: 5000.0, 4: 10.0}, name="possessions")
    result = compare_ratings(
        _ratings(values),
        _ratings(values),
        project_possessions=low,
        reference_possessions=low,
        possession_floor=1000.0,
    )
    assert result.players_compared == 3


def test_too_few_shared_players_is_an_error_not_a_number() -> None:
    values = {1: 3.0, 2: 1.0}
    only_one = pd.Series({1: 5000.0, 2: 10.0}, name="possessions")
    with pytest.raises(ValueError, match="at least two"):
        compare_ratings(
            _ratings(values),
            _ratings(values),
            project_possessions=only_one,
            reference_possessions=only_one,
        )
