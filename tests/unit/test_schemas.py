"""Tests for the ingest schemas.

A schema whose tests only feed it valid data has demonstrated nothing. Every
test below either proves a specific corruption is caught, or proves a specific
legitimate variation is allowed through. The corruptions are the ones that
actually happen to this pipeline: a publisher renaming a column, two seasons
read at different integer widths, a re-download concatenated on top of itself,
and a scrape that copies one team into both sides of a fixture.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.data import schemas


def _play_by_play(rows: int = 3) -> pd.DataFrame:
    """Build a minimal play-by-play frame carrying every required column."""
    return pd.DataFrame(
        {
            "game_id": [401_585_000 + i for i in range(rows)],
            "period": [1] * rows,
            "period_number": [1] * rows,
            "period_display_value": ["1st Quarter"] * rows,
            "clock_display_value": ["11:32"] * rows,
            "clock_minutes": [11] * rows,
            "clock_seconds": [32] * rows,
            "wallclock": ["2024-01-15T00:12:03Z"] * rows,
            "type_id": [92] * rows,
            "team_id": [1_610_612_743] * rows,
            "athlete_id_1": [203_999] * rows,
            "athlete_id_2": [None] * rows,
            "athlete_id_3": [None] * rows,
            "athlete_name_1": ["Nikola Jokic"] * rows,
            "athlete_name_2": [None] * rows,
            "athlete_name_3": [None] * rows,
            "coordinate_x": [25.0] * rows,
            "coordinate_y": [5.5] * rows,
            "coordinate_x_raw": [25.0] * rows,
            "coordinate_y_raw": [5.5] * rows,
            "home_team_id": [1_610_612_743] * rows,
            "home_team_name": ["Denver"] * rows,
            "home_team_mascot": ["Nuggets"] * rows,
            "home_team_abbrev": ["DEN"] * rows,
            "home_team_name_alt": ["Denver Nuggets"] * rows,
            "away_team_id": [1_610_612_747] * rows,
            "away_team_name": ["Los Angeles"] * rows,
            "away_team_mascot": ["Lakers"] * rows,
            "away_team_abbrev": ["LAL"] * rows,
            "away_team_name_alt": ["LA Lakers"] * rows,
            "home_team_spread": [-4.5] * rows,
        }
    )


def _player_box(rows: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [401_585_000] * rows,
            "season": [2024] * rows,
            "athlete_id": [203_999 + i for i in range(rows)],
            "team_id": [1_610_612_743] * rows,
            "minutes": [34.5] * rows,
            "field_goal_pct": [0.52] * rows,
        }
    )


def _team_box() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [401_585_000, 401_585_000],
            "season": [2024, 2024],
            "team_id": [1_610_612_743, 1_610_612_747],
            "field_goal_pct": [0.48, 0.51],
        }
    )


def _schedules(rows: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [401_585_000 + i for i in range(rows)],
            "season": [2024] * rows,
            "game_date": ["2024-01-15"] * rows,
            "home_team_id": [1_610_612_743] * rows,
            "away_team_id": [1_610_612_747] * rows,
        }
    )


BUILDERS = {
    "play_by_play": _play_by_play,
    "player_box": _player_box,
    "team_box": _team_box,
    "schedules": _schedules,
}


# ------------------------------------------------------------------ the lookup


def test_every_registered_dataset_has_a_schema() -> None:
    assert set(schemas.SCHEMAS) == {"play_by_play", "player_box", "team_box", "schedules"}


@pytest.mark.parametrize("dataset", sorted(schemas.SCHEMAS))
def test_get_schema_returns_the_registered_schema(dataset: str) -> None:
    assert schemas.get_schema(dataset) is schemas.SCHEMAS[dataset]


def test_unknown_dataset_is_rejected_and_lists_the_known_ones() -> None:
    # The message is the only guidance a caller gets after a typo, so assert
    # its content rather than only the exception type.
    with pytest.raises(ValueError, match="unknown dataset") as caught:
        schemas.get_schema("play_by_plays")
    message = str(caught.value)
    for known in schemas.SCHEMAS:
        assert known in message


# ------------------------------------------------------------------ happy path


@pytest.mark.parametrize("dataset", sorted(BUILDERS))
def test_a_well_formed_table_validates(dataset: str) -> None:
    result = schemas.validate(BUILDERS[dataset](), dataset)
    assert len(result) == len(BUILDERS[dataset]())


def test_validate_rejects_an_unknown_dataset_before_looking_at_the_frame() -> None:
    with pytest.raises(ValueError, match="unknown dataset"):
        schemas.validate(pd.DataFrame(), "not_a_dataset")


# ------------------------------------------------------------- missing columns


def test_a_missing_required_column_fails_and_is_named() -> None:
    frame = _play_by_play().drop(columns=["home_team_id"])
    with pytest.raises(schemas.SchemaValidationError) as caught:
        schemas.validate(frame, "play_by_play")
    assert "home_team_id" in str(caught.value)


def test_several_missing_columns_are_all_reported_not_just_the_first() -> None:
    # Lazy validation exists so a human fixes the file once instead of
    # re-running after every single fix. Prove it collects rather than stops.
    frame = _play_by_play().drop(columns=["home_team_id", "away_team_id", "type_id"])
    with pytest.raises(schemas.SchemaValidationError) as caught:
        schemas.validate(frame, "play_by_play")
    message = str(caught.value)
    for column in ("home_team_id", "away_team_id", "type_id"):
        assert column in message


# ----------------------------------------------------------------- nullability


def test_a_null_in_a_required_column_fails() -> None:
    frame = _play_by_play()
    frame.loc[1, "home_team_id"] = None
    with pytest.raises(schemas.SchemaValidationError, match="home_team_id"):
        schemas.validate(frame, "play_by_play")


def test_a_null_in_a_nullable_column_is_allowed() -> None:
    # Not every event is attributable to a player. A schema that forbade this
    # would fail on period markers, which are legitimate rows.
    frame = _play_by_play()
    frame.loc[0, "athlete_id_1"] = None
    assert len(schemas.validate(frame, "play_by_play")) == 3


# --------------------------------------------------------------- range checks


def test_a_period_below_one_fails() -> None:
    frame = _play_by_play()
    frame.loc[2, "period"] = 0
    with pytest.raises(schemas.SchemaValidationError, match="period"):
        schemas.validate(frame, "play_by_play")


@pytest.mark.parametrize("bad_pct", [1.5, -0.1])
def test_a_percentage_outside_zero_to_one_fails(bad_pct: float) -> None:
    frame = _player_box()
    frame.loc[0, "field_goal_pct"] = bad_pct
    with pytest.raises(schemas.SchemaValidationError, match="field_goal_pct"):
        schemas.validate(frame, "player_box")


@pytest.mark.parametrize("bad_season", [0, 1800, 99_999])
def test_an_implausible_season_fails(bad_season: int) -> None:
    # Catches a year/season mix-up or a four-digit typo, not a precise bound.
    frame = _player_box()
    frame.loc[0, "season"] = bad_season
    with pytest.raises(schemas.SchemaValidationError, match="season"):
        schemas.validate(frame, "player_box")


def test_negative_minutes_fail() -> None:
    frame = _player_box()
    frame.loc[0, "minutes"] = -1.0
    with pytest.raises(schemas.SchemaValidationError, match="minutes"):
        schemas.validate(frame, "player_box")


# ------------------------------------------------------------------ uniqueness


def test_a_duplicated_player_row_fails() -> None:
    # What a re-download concatenated on top of itself looks like.
    frame = pd.concat([_player_box(rows=1), _player_box(rows=1)], ignore_index=True)
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate(frame, "player_box")


def test_the_same_team_twice_in_one_game_fails() -> None:
    frame = _team_box()
    frame.loc[1, "team_id"] = frame.loc[0, "team_id"]
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate(frame, "team_box")


def test_a_repeated_game_in_the_schedule_fails() -> None:
    frame = pd.concat([_schedules(rows=1), _schedules(rows=1)], ignore_index=True)
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate(frame, "schedules")


def test_two_teams_playing_in_different_games_is_allowed() -> None:
    # The uniqueness constraint is on the pair, not on either column alone.
    frame = _player_box(rows=1)
    second = _player_box(rows=1)
    second["game_id"] = 401_585_999
    assert len(schemas.validate(pd.concat([frame, second], ignore_index=True), "player_box")) == 2


# ------------------------------------------------------------ cross-column check


def test_a_team_playing_itself_fails() -> None:
    # A join or scrape bug that copies one side into both, not a real fixture.
    frame = _schedules()
    frame.loc[0, "away_team_id"] = frame.loc[0, "home_team_id"]
    with pytest.raises(schemas.SchemaValidationError) as caught:
        schemas.validate(frame, "schedules")
    assert "home_team_id must differ from away_team_id" in str(caught.value)


# -------------------------------------------------------------------- coercion


def test_narrow_and_wide_integers_leave_validation_in_the_same_dtype() -> None:
    # The silent-divergence case this schema exists for: one season's file read
    # as int32 and another's as int64 for the same column.
    narrow = _player_box().astype({"game_id": "int32"})
    wide = _player_box().astype({"game_id": "int64"})
    assert (
        schemas.validate(narrow, "player_box")["game_id"].dtype
        == schemas.validate(wide, "player_box")["game_id"].dtype
    )


def test_a_numeric_string_is_coerced_rather_than_rejected() -> None:
    frame = _player_box().astype({"game_id": "string"})
    assert str(schemas.validate(frame, "player_box")["game_id"].dtype) == "Int64"


def test_a_value_that_cannot_coerce_fails() -> None:
    frame = _player_box()
    frame["game_id"] = ["not-a-number", "also-not"]
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate(frame, "player_box")


# ------------------------------------------------------------------ strictness


def test_an_unrecognised_column_passes_through_untouched() -> None:
    # hoopR adds columns over time. Failing the day a publisher adds one would
    # break every scheduled refresh for a reason unrelated to data quality.
    frame = _player_box()
    frame["a_column_added_next_season"] = [np.float64(1.0), np.float64(2.0)]
    result = schemas.validate(frame, "player_box")
    assert "a_column_added_next_season" in result.columns
    assert result["a_column_added_next_season"].tolist() == [1.0, 2.0]


# --------------------------------------------------------- error message quality


def test_the_error_names_the_dataset_the_column_and_the_value() -> None:
    frame = _player_box()
    frame.loc[0, "field_goal_pct"] = 2.0
    with pytest.raises(schemas.SchemaValidationError) as caught:
        schemas.validate(frame, "player_box")
    message = str(caught.value)
    assert "player_box" in message
    assert "field_goal_pct" in message
    assert "2.0" in message


def test_the_error_counts_the_problems() -> None:
    frame = _player_box()
    frame.loc[0, "field_goal_pct"] = 2.0
    frame.loc[1, "minutes"] = -5.0
    with pytest.raises(schemas.SchemaValidationError) as caught:
        schemas.validate(frame, "player_box")
    assert "2 problem(s)" in str(caught.value)
