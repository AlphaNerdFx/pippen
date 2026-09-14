"""Tests for the RAPM design matrix and the ridge solve.

These use synthetic stints rather than real games, so the expected answer is
known in advance. That matters more here than anywhere else in the project: a
sign error in the design matrix produces a fit that converges, reports a
plausible intercept, and ranks every defender backwards, and no amount of
checking against real data would catch it without knowing the truth first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.rapm.design import DesignMatrix, EmptyDesignError, build_design
from pippen.rapm.ridge import (
    bootstrap_standard_errors,
    fit_ridge,
    select_alpha,
    solve,
)

# ------------------------------------------------------------------ helpers


def _lineup(*player_ids: int) -> str:
    return "-".join(str(pid) for pid in player_ids)


def _stint(
    game_id: str,
    offense: tuple[int, ...],
    defense: tuple[int, ...],
    possessions: int,
    points: int,
) -> dict[str, object]:
    return {
        "game_id": game_id,
        "offense_team_id": 1,
        "defense_team_id": 2,
        "offense_lineup": _lineup(*offense),
        "defense_lineup": _lineup(*defense),
        "possessions": possessions,
        "points": points,
    }


def _simple_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _stint("G1", (1, 2, 3, 4, 5), (6, 7, 8, 9, 10), 10, 11),
            _stint("G1", (6, 7, 8, 9, 10), (1, 2, 3, 4, 5), 20, 20),
        ]
    )


def _synthetic_season(
    n_games: int = 40,
    star: int = 1,
    star_effect: float = 10.0,
    seed: int = 7,
) -> pd.DataFrame:
    """Build stints where exactly one player raises his team's scoring.

    Every lineup is drawn at random from a 40-player pool, so no two players
    are collinear and the effect is recoverable. The offense scores at a base
    rate plus ``star_effect`` per 100 possessions whenever ``star`` is on
    offense, and nothing else varies systematically.
    """
    rng = np.random.default_rng(seed)
    pool = np.arange(1, 41)
    rows = []
    for game in range(n_games):
        for _ in range(25):
            picked = rng.choice(pool, size=10, replace=False)
            offense = tuple(int(x) for x in picked[:5])
            defense = tuple(int(x) for x in picked[5:])
            possessions = int(rng.integers(4, 16))
            rate = 110.0 + (star_effect if star in offense else 0.0)
            points = round(possessions * rate / 100.0)
            rows.append(_stint(f"G{game}", offense, defense, possessions, points))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ design shape


def test_every_row_has_five_offensive_and_five_defensive_entries() -> None:
    design = build_design(_simple_frame())
    dense = design.matrix.toarray()
    assert (dense == 1.0).sum(axis=1).tolist() == [5, 5]
    assert (dense == -1.0).sum(axis=1).tolist() == [5, 5]


def test_offence_is_positive_and_defence_is_negative() -> None:
    # The sign convention is what makes "higher is better" hold for both
    # components, so a player's total is a sum rather than a difference.
    design = build_design(_simple_frame())
    dense = design.matrix.toarray()
    assert dense[0, design.offense_column(1)] == 1.0
    assert dense[0, design.defense_column(6)] == -1.0
    assert dense[1, design.offense_column(6)] == 1.0
    assert dense[1, design.defense_column(1)] == -1.0


def test_a_player_gets_one_column_per_side_of_the_ball() -> None:
    design = build_design(_simple_frame())
    assert design.n_players == 10
    assert design.matrix.shape == (2, 20)
    assert design.defense_column(1) == design.offense_column(1) + design.n_players


def test_the_target_is_points_per_hundred_possessions() -> None:
    design = build_design(_simple_frame())
    assert list(design.target) == [110.0, 100.0]


def test_rows_are_weighted_by_possessions() -> None:
    design = build_design(_simple_frame())
    assert list(design.weights) == [10.0, 20.0]


def test_rows_carry_their_game_so_folds_can_split_on_it() -> None:
    frame = _simple_frame()
    frame.loc[1, "game_id"] = "G2"
    design = build_design(frame)
    assert design.groups.tolist() == ["G1", "G2"]


# ------------------------------------------------------------------ filtering


def test_a_lineup_without_five_players_is_dropped_and_counted() -> None:
    frame = pd.DataFrame(
        [
            _stint("G1", (1, 2, 3, 4, 5), (6, 7, 8, 9, 10), 10, 11),
            _stint("G1", (1, 2, 3, 4), (6, 7, 8, 9, 10), 10, 11),
        ]
    )
    design = build_design(frame)
    assert design.n_rows == 1
    assert design.dropped_rows == 1


def test_min_possessions_filters_short_stints() -> None:
    frame = pd.DataFrame(
        [
            _stint("G1", (1, 2, 3, 4, 5), (6, 7, 8, 9, 10), 1, 2),
            _stint("G1", (1, 2, 3, 4, 5), (6, 7, 8, 9, 10), 9, 10),
        ]
    )
    assert build_design(frame, min_possessions=1).n_rows == 2
    assert build_design(frame, min_possessions=5).n_rows == 1


def test_an_empty_problem_raises_rather_than_fitting_zeros() -> None:
    # A silent empty fit returns coefficients of zero, which look like a valid
    # answer meaning "every player is exactly average".
    frame = pd.DataFrame([_stint("G1", (1, 2, 3, 4), (6, 7, 8, 9, 10), 10, 11)])
    with pytest.raises(EmptyDesignError, match="malformed lineups"):
        build_design(frame)


# ------------------------------------------------------------------ the solve


def test_a_zero_or_negative_penalty_is_refused() -> None:
    design = build_design(_simple_frame())
    for alpha in (0.0, -1.0):
        with pytest.raises(ValueError, match="unregularised APM"):
            fit_ridge(design, alpha)


def test_total_impact_is_the_sum_of_the_two_components() -> None:
    design = build_design(_synthetic_season(n_games=6))
    ratings = fit_ridge(design, 1000.0).ratings()
    assert np.allclose(ratings["total"], ratings["offensive"] + ratings["defensive"])


def test_a_larger_penalty_shrinks_the_ratings() -> None:
    design = build_design(_synthetic_season(n_games=6))
    light = np.abs(fit_ridge(design, 100.0).coefficients).sum()
    heavy = np.abs(fit_ridge(design, 100000.0).coefficients).sum()
    assert heavy < light


def test_the_planted_player_is_found() -> None:
    # The only systematic effect in this data is that player 1 adds 10 points
    # per 100 possessions on offense. If the design or the solve had a sign or
    # indexing error, this would fail.
    design = build_design(_synthetic_season(star=1, star_effect=10.0))
    ratings = fit_ridge(design, 300.0).ratings()
    assert ratings.iloc[0]["player_id"] == 1
    assert ratings.iloc[0]["offensive"] > ratings["offensive"].drop(0).max()


def test_a_planted_defender_ranks_top_too() -> None:
    # Same experiment with the effect on the other side of the ball, which is
    # the case a sign error would reverse.
    frame = _synthetic_season(star=1, star_effect=0.0)
    on_defense = frame["defense_lineup"].str.split("-").apply(lambda ids: "1" in ids)
    frame.loc[on_defense, "points"] = (frame.loc[on_defense, "possessions"] * 1.00).round()
    design = build_design(frame)
    ratings = fit_ridge(design, 300.0).ratings()
    assert ratings.iloc[0]["player_id"] == 1
    assert ratings.iloc[0]["defensive"] > 0


def test_the_intercept_recovers_the_league_rate() -> None:
    design = build_design(_synthetic_season(star_effect=0.0))
    fit = fit_ridge(design, 1000.0)
    assert 105.0 < fit.intercept < 115.0


# ------------------------------------------------------------------ penalty choice


def test_cross_validation_reports_every_penalty_it_tried() -> None:
    design = build_design(_synthetic_season(n_games=10))
    alphas = (100.0, 1000.0, 10000.0)
    best, table = select_alpha(design, alphas=alphas, folds=3)
    assert list(table["alpha"]) == list(alphas)
    assert best in alphas
    assert table["weighted_mse"].notna().all()


def test_folds_cannot_outnumber_games() -> None:
    design = build_design(_simple_frame())
    with pytest.raises(ValueError, match="distinct games"):
        select_alpha(design, folds=5)


def test_folds_split_on_games_not_rows() -> None:
    # Two stints from one game must never land in different folds, or the model
    # sees part of the game it is tested on.
    design = build_design(_synthetic_season(n_games=8))
    from pippen.rapm.ridge import _game_folds

    masks = _game_folds(design.groups, folds=4, seed=1)
    for mask in masks:
        held_out_games = set(design.groups[mask])
        kept_games = set(design.groups[~mask])
        assert held_out_games.isdisjoint(kept_games)


def test_solve_fits_at_the_penalty_it_selected() -> None:
    design = build_design(_synthetic_season(n_games=10))
    fit, table = solve(design, alphas=(100.0, 1000.0), folds=3)
    best_row = table.loc[table["weighted_mse"].idxmin()]
    assert fit.alpha == best_row["alpha"]


# ------------------------------------------------------------------ uncertainty


def test_bootstrap_reports_one_standard_error_per_player() -> None:
    design = build_design(_synthetic_season(n_games=8))
    errors = bootstrap_standard_errors(design, 1000.0, resamples=8)
    assert len(errors) == design.n_players
    assert set(errors["player_id"]) == set(design.player_ids)
    assert (errors[["offensive_se", "defensive_se", "total_se"]] >= 0).all().all()


def test_a_heavier_penalty_gives_tighter_standard_errors() -> None:
    # Shrinkage trades bias for variance, so the penalty that shrinks harder
    # must produce the smaller spread across resamples.
    design = build_design(_synthetic_season(n_games=8))
    light = bootstrap_standard_errors(design, 100.0, resamples=10)["total_se"].median()
    heavy = bootstrap_standard_errors(design, 30000.0, resamples=10)["total_se"].median()
    assert heavy < light


def test_bootstrap_resamples_games_rather_than_rows() -> None:
    design = build_design(_synthetic_season(n_games=6))
    first = bootstrap_standard_errors(design, 1000.0, resamples=6, seed=1)
    again = bootstrap_standard_errors(design, 1000.0, resamples=6, seed=1)
    assert np.allclose(first["total_se"], again["total_se"])


def test_the_design_describes_itself_honestly() -> None:
    design: DesignMatrix = build_design(_synthetic_season(n_games=4))
    text = design.describe()
    assert f"{design.n_rows:,} stints" in text
    assert "possessions" in text
