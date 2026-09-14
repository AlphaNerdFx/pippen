"""Tests for the box-score metrics and the eligibility filter.

The eligibility filter carries most of the risk here. hoopR labels the All-Star
exhibition as regular season, so a `season_type` check alone lets a 40-point
no-defence game into a player's season, and it does so for exactly the players
whose reliability matters most.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from pippen.data.possession_coefficient import (
    CONVENTIONAL_COEFFICIENT,
    coefficient_for_season,
)
from pippen.reliability.metrics import (
    BY_NAME,
    METRICS,
    MINIMUM_TEAM_GAMES,
    MissingColumnsError,
    compute,
    eligible_rows,
    summarise_totals,
)


def _box(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    defaults: dict[str, Any] = {
        "season_type": 2,
        "did_not_play": False,
        "minutes": 30.0,
        "field_goals_made": 5.0,
        "field_goals_attempted": 10.0,
        "three_point_field_goals_made": 1.0,
        "three_point_field_goals_attempted": 3.0,
        "free_throws_made": 2.0,
        "free_throws_attempted": 3.0,
        "offensive_rebounds": 1.0,
        "defensive_rebounds": 4.0,
        "rebounds": 5.0,
        "assists": 3.0,
        "steals": 1.0,
        "blocks": 1.0,
        "turnovers": 2.0,
        "fouls": 2.0,
        "points": 13.0,
    }
    for column, value in defaults.items():
        if column not in frame.columns:
            frame[column] = value
    return frame


def _season(team_id: int, games: int, athlete_id: int = 1) -> list[dict[str, Any]]:
    return [
        {"game_id": f"{team_id}-{n}", "team_id": team_id, "athlete_id": athlete_id}
        for n in range(games)
    ]


# ------------------------------------------------------------------ eligibility


def test_playoff_rows_are_dropped() -> None:
    box = _box(_season(1, 50) + _season(2, 50))
    box.loc[box.index[:10], "season_type"] = 3
    assert len(eligible_rows(box)) == 90


def test_the_all_star_pseudo_teams_are_dropped() -> None:
    # hoopR files the All-Star Game under season_type 2 with a team that plays
    # one game. A name list would need updating almost every year; a team-games
    # rule removes it by construction.
    real = _season(1, 60) + _season(2, 60)
    all_star = [{"game_id": "as-1", "team_id": 31, "athlete_id": 1}]
    kept = eligible_rows(_box(real + all_star))
    assert 31 not in set(kept["team_id"])
    assert len(kept) == 120


def test_a_team_on_the_threshold_is_kept() -> None:
    box = _box(_season(1, MINIMUM_TEAM_GAMES) + _season(2, MINIMUM_TEAM_GAMES))
    assert len(eligible_rows(box)) == 2 * MINIMUM_TEAM_GAMES


def test_did_not_play_and_zero_minute_rows_are_dropped() -> None:
    box = _box(_season(1, 50) + _season(2, 50))
    box.loc[box.index[0], "did_not_play"] = True
    box.loc[box.index[1], "minutes"] = 0.0
    box.loc[box.index[2], "minutes"] = np.nan
    assert len(eligible_rows(box)) == 97


def test_a_missing_column_is_named() -> None:
    with pytest.raises(MissingColumnsError, match="did_not_play"):
        eligible_rows(
            pd.DataFrame(
                {
                    "season_type": [2],
                    "game_id": ["1"],
                    "team_id": [1],
                    "athlete_id": [1],
                    "minutes": [10.0],
                }
            )
        )


# ------------------------------------------------------------------ totals


def test_totals_sum_counting_stats_and_count_games() -> None:
    rows = eligible_rows(_box(_season(1, 50) + _season(2, 50)))
    totals = summarise_totals(rows)
    assert totals.loc[1, "games"] == 100
    assert totals.loc[1, "points"] == 100 * 13.0
    assert totals.loc[1, "teams"] == 2


def test_teams_counts_franchises_so_a_trade_is_visible() -> None:
    rows = eligible_rows(_box(_season(1, 60, athlete_id=1) + _season(2, 60, athlete_id=2)))
    totals = summarise_totals(rows)
    assert totals.loc[1, "teams"] == 1
    assert totals.loc[2, "teams"] == 1


# ------------------------------------------------------------------ metric values


def test_per_36_rates_scale_by_minutes() -> None:
    rows = eligible_rows(_box(_season(1, 50) + _season(2, 50)))
    totals = summarise_totals(rows)
    value = compute(BY_NAME["points_per_36"], totals, 2024)
    assert value.loc[1] == pytest.approx(36.0 * 13.0 / 30.0)


def test_true_shooting_uses_the_measured_coefficient_not_the_convention() -> None:
    # Every season the project measured came out below 0.44, so using the
    # convention here would contradict the project's own finding.
    rows = eligible_rows(_box(_season(1, 50) + _season(2, 50)))
    totals = summarise_totals(rows)
    measured = compute(BY_NAME["true_shooting"], totals, 2024).loc[1]

    coefficient = coefficient_for_season(2024)
    assert coefficient != CONVENTIONAL_COEFFICIENT
    row = totals.loc[1].astype(float)
    points = row["points"]
    attempted = row["field_goals_attempted"]
    free_throws = row["free_throws_attempted"]
    expected = points / (2.0 * (attempted + coefficient * free_throws))
    assert measured == pytest.approx(expected)

    with_convention = points / (2.0 * (attempted + CONVENTIONAL_COEFFICIENT * free_throws))
    assert measured != pytest.approx(with_convention)


def test_effective_field_goal_counts_a_three_as_one_and_a_half() -> None:
    rows = eligible_rows(_box(_season(1, 50) + _season(2, 50)))
    totals = summarise_totals(rows)
    value = compute(BY_NAME["effective_field_goal"], totals, 2024).loc[1]
    assert value == pytest.approx((5.0 + 0.5 * 1.0) / 10.0)


def test_values_resting_on_too_few_attempts_are_removed_not_kept() -> None:
    # A shooting percentage from two attempts is a different quantity, not a
    # weak measurement of the same one.
    rows = eligible_rows(_box(_season(1, 2)))
    totals = summarise_totals(rows)
    assert compute(BY_NAME["true_shooting"], totals, 2024).isna().all()


def test_a_division_by_zero_becomes_missing_rather_than_infinite() -> None:
    box = _box(_season(1, 60) + _season(2, 60))
    box["field_goals_attempted"] = 0.0
    totals = summarise_totals(eligible_rows(box))
    assert compute(BY_NAME["three_point_rate"], totals, 2024).isna().all()


def test_every_metric_has_a_unique_name_and_a_description() -> None:
    names = [metric.name for metric in METRICS]
    assert len(names) == len(set(names))
    assert all(metric.description for metric in METRICS)
