"""Tests for the claim under test.

The comparison has to be fair or it says nothing, so most of these check the
fairness rather than the arithmetic: that folds hold out whole seasons, that
every candidate gets the same treatment, and that the verdict is phrased the
same way whichever candidate wins.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.model.claim import (
    ClaimResult,
    NotEnoughSeasonsError,
    TeamSeasonRatings,
    aggregate_to_team,
    compare_candidates,
    paired_comparison,
)

# ------------------------------------------------------------------ aggregation


def test_a_team_rating_is_weighted_by_minutes() -> None:
    values = pd.Series({1: 10.0, 2: 0.0})
    minutes = pd.Series({1: 3000.0, 2: 1000.0})
    teams = pd.Series({1: 100, 2: 100})
    assert aggregate_to_team(values, minutes, teams).loc[100] == pytest.approx(7.5)


def test_players_below_the_minutes_floor_are_dropped() -> None:
    # A rating resting on a handful of minutes is mostly the prior, and would
    # add noise to the aggregate in proportion to how little it knows.
    values = pd.Series({1: 10.0, 2: -100.0})
    minutes = pd.Series({1: 3000.0, 2: 50.0})
    teams = pd.Series({1: 100, 2: 100})
    assert aggregate_to_team(values, minutes, teams, minutes_floor=200.0).loc[100] == 10.0


def test_teams_are_aggregated_separately() -> None:
    values = pd.Series({1: 10.0, 2: 4.0})
    minutes = pd.Series({1: 2000.0, 2: 2000.0})
    teams = pd.Series({1: 100, 2: 200})
    result = aggregate_to_team(values, minutes, teams)
    assert result.loc[100] == 10.0
    assert result.loc[200] == 4.0


def test_an_empty_aggregate_is_empty_rather_than_an_error() -> None:
    values = pd.Series({1: 10.0})
    minutes = pd.Series({1: 10.0})
    teams = pd.Series({1: 100})
    assert aggregate_to_team(values, minutes, teams, minutes_floor=500.0).empty


def test_a_missing_rating_drops_that_player_not_the_team() -> None:
    values = pd.Series({1: 10.0, 2: np.nan})
    minutes = pd.Series({1: 2000.0, 2: 2000.0})
    teams = pd.Series({1: 100, 2: 100})
    assert aggregate_to_team(values, minutes, teams).loc[100] == 10.0


# ------------------------------------------------------------------ the comparison


def _panel(
    seasons: int = 4, teams: int = 30, seed: int = 5
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """A panel where one candidate genuinely predicts and one is noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2016 + seasons):
        for team in range(teams):
            truth = rng.normal(0.0, 4.0)
            rows.append(
                {
                    "season": season,
                    "team": team,
                    "good": truth + rng.normal(0.0, 1.0),
                    "noise": rng.normal(0.0, 1.0),
                    "target": truth + rng.normal(0.0, 2.0),
                }
            )
    frame = pd.DataFrame(rows).set_index(["season", "team"])
    return (
        frame[["good", "noise"]],
        frame["target"],
        pd.Series([i[0] for i in frame.index], index=frame.index),
    )


def test_a_predictive_candidate_beats_a_noise_candidate() -> None:
    features, target, seasons = _panel()
    result = compare_candidates(features, target, seasons)
    assert result.winner == "good"
    assert result.table.iloc[0]["rmse"] < result.table.iloc[1]["rmse"]


def test_every_candidate_is_scored() -> None:
    features, target, seasons = _panel()
    result = compare_candidates(features, target, seasons)
    assert set(result.table["candidate"]) == {"good", "noise"}


def test_the_gap_to_the_best_is_reported() -> None:
    features, target, seasons = _panel()
    result = compare_candidates(features, target, seasons)
    assert result.table.iloc[0]["vs_best"] == 0.0
    assert result.table.iloc[1]["vs_best"] > 0.0


def test_one_season_cannot_be_compared() -> None:
    features, target, seasons = _panel(seasons=1)
    with pytest.raises(NotEnoughSeasonsError, match="at least two"):
        compare_candidates(features, target, seasons)


def test_folds_hold_out_whole_seasons() -> None:
    # If a fold split within a season, a model would be predicting the rest of
    # a season it had already seen rather than the future.
    features, target, seasons = _panel(seasons=3)
    result = compare_candidates(features, target, seasons)
    assert result.folds == 3


def test_a_candidate_that_is_entirely_missing_is_skipped_not_crashed() -> None:
    features, target, seasons = _panel()
    features = features.assign(absent=np.nan)
    result = compare_candidates(features, target, seasons)
    assert "absent" not in set(result.table["candidate"])


# ------------------------------------------------------------------ the verdict


def test_the_verdict_is_phrased_the_same_way_whichever_way_it_goes() -> None:
    won = ClaimResult(
        table=pd.DataFrame([{"candidate": "fusion", "rmse": 1.0, "vs_best": 0.0}]),
        squared_errors=pd.DataFrame({"fusion": [1.0]}),
        observations=180,
        folds=6,
    )
    assert won.fusion_wins
    assert "fusion wins" in won.describe()
    assert "180 team-seasons" in won.describe()

    lost = ClaimResult(
        table=pd.DataFrame(
            [
                {"candidate": "rapm", "rmse": 0.9, "vs_best": 0.0},
                {"candidate": "fusion", "rmse": 1.0, "vs_best": 0.1},
            ]
        ),
        squared_errors=pd.DataFrame({"rapm": [0.81], "fusion": [1.0]}),
        observations=180,
        folds=6,
    )
    assert not lost.fusion_wins
    assert "fusion does not win" in lost.describe()
    assert "rapm" in lost.describe()


def test_team_ratings_describe_their_spread() -> None:
    table = pd.DataFrame(
        {"net_rating": [5.0, -5.0, 0.0]}, index=pd.Index([1, 2, 3], name="team_id")
    )
    described = TeamSeasonRatings(season=2018, table=table).describe()
    assert "3 teams" in described
    assert "+5.0" in described


# ------------------------------------------------------------------ significance


def test_a_real_difference_is_detected() -> None:
    features, target, seasons = _panel(seasons=5)
    result = compare_candidates(features, target, seasons)
    comparison = paired_comparison(result, "good", "noise")
    assert comparison.better == "good"
    assert comparison.distinguishable
    assert "beats" in comparison.describe()


def test_a_difference_that_is_only_noise_is_not_claimed() -> None:
    # Two copies of the same signal differ only by sampling, and the verdict
    # has to say so rather than crowning whichever came out lower.
    rng = np.random.default_rng(3)
    rows = []
    for season in range(2016, 2021):
        for team in range(30):
            truth = rng.normal(0.0, 4.0)
            shared = truth + rng.normal(0.0, 1.0)
            rows.append(
                {
                    "season": season,
                    "team": team,
                    "a": shared,
                    "b": shared + rng.normal(0.0, 1e-6),
                    "target": truth + rng.normal(0.0, 2.0),
                }
            )
    frame = pd.DataFrame(rows).set_index(["season", "team"])
    seasons = pd.Series([i[0] for i in frame.index], index=frame.index)
    result = compare_candidates(frame[["a", "b"]], frame["target"], seasons)
    comparison = paired_comparison(result, "a", "b")
    assert not comparison.distinguishable
    assert "not distinguishable" in comparison.describe()


def test_the_better_candidate_is_identified_whichever_order_is_given() -> None:
    features, target, seasons = _panel(seasons=4)
    result = compare_candidates(features, target, seasons)
    forwards = paired_comparison(result, "good", "noise")
    backwards = paired_comparison(result, "noise", "good")
    assert forwards.better == backwards.better == "good"
    assert forwards.p_value == pytest.approx(backwards.p_value)


def test_an_unscored_candidate_is_named() -> None:
    features, target, seasons = _panel()
    result = compare_candidates(features, target, seasons)
    with pytest.raises(KeyError, match="absent"):
        paired_comparison(result, "good", "absent")


def test_squared_errors_are_kept_per_observation() -> None:
    features, target, seasons = _panel(seasons=3, teams=10)
    result = compare_candidates(features, target, seasons)
    assert set(result.squared_errors.columns) == {"good", "noise"}
    assert len(result.squared_errors) == 30
