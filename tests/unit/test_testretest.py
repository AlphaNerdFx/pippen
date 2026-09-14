"""Tests for split-half reliability.

Two things carry the risk. The Spearman-Brown correction converts between
measurement lengths, and applying it at the wrong length changes any downstream
weight by a factor of three without changing anything visible. And the halves
must be balanced, or the correlation partly measures how unevenly the games
were dealt rather than how consistent the metric is.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.reliability import testretest
from pippen.reliability.metrics import BY_NAME, eligible_rows
from pippen.reliability.testretest import (
    NotEnoughPlayersError,
    SplitHalfEstimate,
    SplitRule,
    _assign_halves,
    measure_season,
    reliability_curve,
    spearman_brown,
    split_half,
)

# ------------------------------------------------------------------ helpers


def _estimate(rho: float = 0.5, games_per_half: float = 41.0) -> SplitHalfEstimate:
    return SplitHalfEstimate(
        metric="m",
        season=2024,
        rule=SplitRule.RANDOM,
        rho_half=rho,
        rho_half_sd=0.01,
        rho_half_spearman=rho,
        games_per_half=games_per_half,
        players=300,
        minutes_floor=500.0,
        splits=100,
        traded_share=0.18,
    )


def _synthetic_box(
    n_players: int = 60,
    n_games: int = 60,
    signal: float = 1.0,
    noise: float = 0.0,
    seed: int = 1,
) -> pd.DataFrame:
    """A season where each player's scoring is a fixed talent plus noise.

    ``signal`` scales the spread of true talent across players and ``noise``
    the game-to-game variation, so the expected split-half correlation can be
    dialled from zero to one.
    """
    rng = np.random.default_rng(seed)
    talent = rng.normal(0.0, 1.0, n_players) * signal
    rows = []
    for player in range(n_players):
        team = 1 + player % 2
        for game in range(n_games):
            points = 15.0 + talent[player] + rng.normal(0.0, 1.0) * noise
            rows.append(
                {
                    "game_id": f"g{game}-{team}",
                    "game_date": pd.Timestamp("2023-10-25") + pd.Timedelta(days=game),
                    "team_id": team,
                    "athlete_id": player,
                    "season_type": 2,
                    "did_not_play": False,
                    "minutes": 30.0,
                    "points": max(points, 0.0),
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
                }
            )
    return eligible_rows(pd.DataFrame(rows))


# ------------------------------------------------------------------ the correction


def test_a_ratio_of_two_is_the_familiar_half_to_whole_form() -> None:
    assert spearman_brown(0.7, 2.0) == pytest.approx(2 * 0.7 / 1.7)
    assert spearman_brown(0.5, 2.0) == pytest.approx(2 / 3)


def test_a_ratio_of_one_changes_nothing() -> None:
    assert spearman_brown(0.42, 1.0) == pytest.approx(0.42)


def test_a_longer_measurement_is_more_reliable() -> None:
    values = [spearman_brown(0.5, ratio) for ratio in (1.0, 2.0, 4.0, 8.0)]
    assert values == sorted(values)
    assert all(value < 1.0 for value in values)


def test_a_non_positive_ratio_is_refused() -> None:
    with pytest.raises(ValueError, match="ratio must be positive"):
        spearman_brown(0.5, 0.0)


# ------------------------------------------------------------------ the length trap


def test_the_same_measurement_implies_very_different_weights_at_different_lengths() -> None:
    # This is the whole reason the estimate stores a length. At rho 0.5 the
    # implied inverse-variance weight is 2.0 at one season and 6.1 at three,
    # and nothing downstream would catch the wrong one.
    estimate = _estimate(rho=0.5, games_per_half=41.0)
    one_season = estimate.reliability_at(82)
    three_seasons = estimate.reliability_at(246)
    assert one_season == pytest.approx(2 / 3, abs=1e-6)
    assert three_seasons == pytest.approx(0.857, abs=1e-3)
    assert (three_seasons / (1 - three_seasons)) / (one_season / (1 - one_season)) > 2.9


def test_the_observed_length_is_both_halves_together() -> None:
    estimate = _estimate(rho=0.6, games_per_half=31.5)
    assert estimate.reliability_at_observed_length == pytest.approx(estimate.reliability_at(63.0))


def test_asking_for_a_non_positive_length_is_refused() -> None:
    with pytest.raises(ValueError, match="games must be positive"):
        _estimate().reliability_at(0)


def test_the_description_never_states_a_bare_reliability() -> None:
    text = _estimate().describe()
    assert "games per half" in text
    assert "at the observed length" in text


def test_the_module_exposes_no_inverse_variance_weight() -> None:
    # Q9, enforced structurally rather than documented. The moment a function
    # returning r / (1 - r) exists, something will call it, and the fusion
    # model will rank scoring volume above impact with no test failing.
    public = [name for name in dir(testretest) if not name.startswith("_")]
    assert not [name for name in public if "weight" in name.lower()]
    assert not [name for name in dir(SplitHalfEstimate) if "weight" in name.lower()]


# ------------------------------------------------------------------ the split


def test_halves_are_balanced_to_within_one_game() -> None:
    # An odd game count, so a player cannot be split evenly and the balance
    # guarantee is actually exercised. Above the team-games floor, or the
    # eligibility filter removes the whole fixture.
    rows = _synthetic_box(n_players=10, n_games=41)
    halves = _assign_halves(rows, SplitRule.RANDOM, np.random.default_rng(3))
    counts = rows.assign(half=halves).groupby(["athlete_id", "half"]).size().unstack()
    assert (counts.max(axis=1) - counts.min(axis=1)).max() <= 1


def test_odd_even_is_deterministic_and_random_is_not() -> None:
    rows = _synthetic_box(n_players=8, n_games=41)
    first = _assign_halves(rows, SplitRule.ODD_EVEN, np.random.default_rng(1))
    second = _assign_halves(rows, SplitRule.ODD_EVEN, np.random.default_rng(999))
    assert first.equals(second)

    generator = np.random.default_rng(1)
    a = _assign_halves(rows, SplitRule.RANDOM, generator)
    b = _assign_halves(rows, SplitRule.RANDOM, generator)
    assert not a.equals(b)


# ------------------------------------------------------------------ the measurement


def test_a_metric_that_is_pure_noise_correlates_near_zero() -> None:
    rows = _synthetic_box(signal=0.0, noise=6.0, seed=5)
    estimate = split_half(rows, BY_NAME["points_per_36"], 2024, splits=25, minutes_floor=500.0)
    assert abs(estimate.rho_half) < 0.25


def test_a_metric_that_is_pure_signal_correlates_near_one() -> None:
    rows = _synthetic_box(signal=6.0, noise=0.0, seed=5)
    estimate = split_half(rows, BY_NAME["points_per_36"], 2024, splits=25, minutes_floor=500.0)
    assert estimate.rho_half > 0.99


def test_more_noise_lowers_the_correlation() -> None:
    quiet = split_half(
        _synthetic_box(signal=3.0, noise=1.0, seed=8),
        BY_NAME["points_per_36"],
        2024,
        splits=25,
    )
    loud = split_half(
        _synthetic_box(signal=3.0, noise=8.0, seed=8),
        BY_NAME["points_per_36"],
        2024,
        splits=25,
    )
    assert loud.rho_half < quiet.rho_half


def test_the_spread_across_splits_is_reported() -> None:
    # A single split is one draw. Reporting the spread is what says how far a
    # single odd-even split could have wandered.
    estimate = split_half(
        _synthetic_box(signal=2.0, noise=4.0, seed=11),
        BY_NAME["points_per_36"],
        2024,
        splits=40,
    )
    assert estimate.rho_half_sd > 0
    assert estimate.splits == 40


def test_odd_even_reports_a_single_split() -> None:
    estimate = split_half(
        _synthetic_box(signal=2.0, noise=2.0),
        BY_NAME["points_per_36"],
        2024,
        rule=SplitRule.ODD_EVEN,
        splits=50,
    )
    assert estimate.splits == 1
    assert estimate.rho_half_sd == 0.0


def test_too_few_qualifying_players_is_an_error() -> None:
    rows = _synthetic_box(n_players=2, n_games=60)
    with pytest.raises(NotEnoughPlayersError, match="at least three"):
        split_half(rows, BY_NAME["points_per_36"], 2024, splits=5)


# ------------------------------------------------------------------ tables


def test_a_season_table_names_the_length_in_every_reliability_column() -> None:
    rows = _synthetic_box(signal=3.0, noise=2.0)
    table = measure_season(
        rows, 2024, metrics=(BY_NAME["points_per_36"], BY_NAME["true_shooting"]), splits=10
    )
    assert len(table) == 2
    reliability_columns = [c for c in table.columns if "reliability" in c]
    assert reliability_columns
    assert all("at" in column for column in reliability_columns)
    assert "reliability" not in table.columns


def test_the_curve_reports_one_row_per_floor_with_its_player_count() -> None:
    rows = _synthetic_box(signal=3.0, noise=2.0, n_games=60)
    curve = reliability_curve(
        rows, BY_NAME["points_per_36"], 2024, floors=(500.0, 1000.0, 1500.0), splits=10
    )
    assert list(curve["minutes_floor"]) == [500.0, 1000.0, 1500.0]
    assert curve["players"].is_monotonic_decreasing
