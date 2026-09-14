"""Tests for RAPM split-half stability.

The module exists because bootstrap standard errors turned out to measure
shrinkage rather than information. These check the replacement behaves: that it
splits on games rather than rows, that a fixed cohort is honoured so windows of
different lengths stay comparable, and that a window with more signal reproduces
better than one with less.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.rapm.stability import (
    NotEnoughGamesError,
    StabilityEstimate,
    split_half_stability,
)


def _stints(
    n_games: int = 60,
    stints_per_game: int = 25,
    star_effect: float = 8.0,
    noise: float = 0.0,
    seed: int = 3,
) -> pd.DataFrame:
    """Stints where player 1 raises his team's scoring by ``star_effect``."""
    rng = np.random.default_rng(seed)
    pool = np.arange(1, 41)
    rows = []
    for game in range(n_games):
        for _ in range(stints_per_game):
            picked = rng.choice(pool, size=10, replace=False)
            offense = tuple(int(x) for x in picked[:5])
            defense = tuple(int(x) for x in picked[5:])
            possessions = int(rng.integers(6, 18))
            rate = 110.0 + (star_effect if 1 in offense else 0.0)
            rate += rng.normal(0.0, noise) if noise else 0.0
            rows.append(
                {
                    "game_id": f"G{game}",
                    "offense_team_id": 1,
                    "defense_team_id": 2,
                    "offense_lineup": "-".join(str(p) for p in offense),
                    "defense_lineup": "-".join(str(p) for p in defense),
                    "possessions": possessions,
                    "points": max(round(possessions * rate / 100.0), 0),
                    "opponent_points": 0,
                }
            )
    return pd.DataFrame(rows)


def test_a_clean_signal_reproduces_across_halves() -> None:
    estimate = split_half_stability(
        _stints(star_effect=8.0, noise=0.0),
        seasons=(2016,),
        alpha=500.0,
        draws=4,
        possession_floor=500.0,
    )
    assert estimate.rho_half > 0.8
    assert estimate.reliability_of_window > estimate.rho_half


def test_noise_lowers_reproducibility() -> None:
    quiet = split_half_stability(
        _stints(star_effect=8.0, noise=2.0, seed=9),
        seasons=(2016,),
        alpha=500.0,
        draws=4,
        possession_floor=500.0,
    )
    loud = split_half_stability(
        _stints(star_effect=8.0, noise=40.0, seed=9),
        seasons=(2016,),
        alpha=500.0,
        draws=4,
        possession_floor=500.0,
    )
    assert loud.rho_half < quiet.rho_half


def test_the_full_window_is_more_reliable_than_a_half() -> None:
    # Spearman-Brown, same correction the metric side uses.
    estimate = StabilityEstimate(
        seasons=(2016, 2017, 2018),
        possessions=683356.0,
        players=228,
        rho_half=0.661,
        rho_half_sd=0.033,
        draws=8,
        alpha=3000.0,
    )
    assert estimate.reliability_of_window == pytest.approx(2 * 0.661 / 1.661)
    assert "3 season(s)" in estimate.describe()
    assert "2016-2018" in estimate.describe()


def test_a_cohort_restricts_who_is_compared() -> None:
    stints = _stints()
    everyone = split_half_stability(
        stints, seasons=(2016,), alpha=500.0, draws=2, possession_floor=100.0
    )
    narrowed = split_half_stability(
        stints,
        seasons=(2016,),
        alpha=500.0,
        draws=2,
        possession_floor=100.0,
        cohort={1, 2, 3, 4, 5, 6, 7, 8},
    )
    assert narrowed.players < everyone.players


def test_a_window_too_small_to_split_is_refused() -> None:
    with pytest.raises(NotEnoughGamesError, match="too little to fit"):
        split_half_stability(
            _stints(n_games=3), seasons=(2016,), alpha=500.0, draws=2, possession_floor=10.0
        )


def test_the_same_seed_gives_the_same_answer() -> None:
    stints = _stints()
    first = split_half_stability(
        stints, seasons=(2016,), alpha=500.0, draws=3, seed=7, possession_floor=500.0
    )
    again = split_half_stability(
        stints, seasons=(2016,), alpha=500.0, draws=3, seed=7, possession_floor=500.0
    )
    assert first.rho_half == pytest.approx(again.rho_half)
