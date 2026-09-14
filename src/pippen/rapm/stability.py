"""How stable a RAPM rating is, measured the way the project measures metrics.

Why not bootstrap standard errors
---------------------------------
Phase 2 originally asked for bootstrap standard errors that shrink as seasons
are added. Measured, they do not: on a fixed cohort of 228 players present in
all of 2016-17 to 2018-19, the median standard error ran 1.217, 1.303, 1.253
across one-, two- and three-season windows. Flat.

The reason is that a bootstrap standard error on a *ridge* coefficient does not
measure information. Within a single window, the standard error **rises** with
a player's possessions, correlating +0.79 with their log:

===================  =========  ===========
Possessions (median)  Players    Median SE
===================  =========  ===========
388                   98         0.56
2,174                 97         1.10
4,764                 97         1.24
6,919                 97         1.23
9,393                 97         1.19
===================  =========  ===========

A player with two hundred possessions is shrunk almost entirely to zero, so his
coefficient barely moves between resamples and his standard error is tiny. That
is not precision, it is the prior. The statistic conflates "estimated
precisely" with "shrunk to nothing", which makes it useless for comparing
players or window lengths.

It also explains why the cross-window comparison came out flat. Holding the
penalty fixed while tripling the data weakens the shrinkage in relative terms,
and the extra variance that releases roughly cancels the extra information.
Scaling the penalty with the data makes the number fall, from 1.210 to 0.727,
but that buys variance reduction with bias rather than with information.

What replaces it
----------------
Split-half reliability, the same instrument this project applies to every other
metric. Split the window's games in two, fit RAPM on each half, and correlate
the ratings across players. That measures whether the ratings reproduce, which
is the thing the criterion was reaching for.

Measured on the same cohort, it rises monotonically:

==========  ==========  ==================
Window      rho (half)  Reliability (full)
==========  ==========  ==================
1 season    0.429       0.601
2 seasons   0.578       0.732
3 seasons   0.661       0.796
==========  ==========  ==================

Three-season RAPM at 0.796 sits inside the 80-85 percent band the source
research assigns to RAPM. Single-season RAPM at 0.601 does not, which is the
concrete reason this project publishes multi-season windows.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from pippen.rapm.design import build_design
from pippen.rapm.ridge import fit_ridge
from pippen.reliability.testretest import spearman_brown

#: Halves drawn by default. Fewer than the metric side uses, because each draw
#: here costs two ridge fits rather than two groupby sums.
DEFAULT_DRAWS: Final = 8

#: Possessions a player needs in the window to enter the correlation. Below
#: this a rating is mostly the ridge prior, and two priors correlate with each
#: other for reasons that have nothing to do with the data.
DEFAULT_POSSESSION_FLOOR: Final = 2000.0

#: Seed, matching the project-wide default.
DEFAULT_SEED: Final = 20260910


class NotEnoughGamesError(ValueError):
    """Too few games in the window to split it in half."""


@dataclass(frozen=True)
class StabilityEstimate:
    """How well a window's ratings reproduce across a split of its games.

    Attributes:
        seasons: Seasons pooled into the window.
        possessions: Possessions in the window.
        players: Players entering the correlation.
        rho_half: Mean correlation between half-window ratings.
        rho_half_sd: Spread of that correlation across draws.
        draws: Splits averaged.
        alpha: Ridge penalty held fixed across both halves and all draws.
    """

    seasons: tuple[int, ...]
    possessions: float
    players: int
    rho_half: float
    rho_half_sd: float
    draws: int
    alpha: float

    @property
    def reliability_of_window(self) -> float:
        """Reliability of a rating fitted on the whole window, not a half."""
        return spearman_brown(self.rho_half, 2.0)

    def describe(self) -> str:
        """Return a one-line summary naming the window length."""
        span = (
            f"{self.seasons[0]}-{self.seasons[-1]}"
            if len(self.seasons) > 1
            else str(self.seasons[0])
        )
        return (
            f"{span} ({len(self.seasons)} season(s), {self.possessions:,.0f} possessions): "
            f"half-window rho {self.rho_half:.3f} (sd {self.rho_half_sd:.3f}) over "
            f"{self.players} players, reliability of the full window "
            f"{self.reliability_of_window:.3f}"
        )


def split_half_stability(
    stints: pd.DataFrame,
    *,
    seasons: tuple[int, ...],
    alpha: float,
    draws: int = DEFAULT_DRAWS,
    possession_floor: float = DEFAULT_POSSESSION_FLOOR,
    cohort: Collection[int] | None = None,
    seed: int = DEFAULT_SEED,
) -> StabilityEstimate:
    """Measure how well a window's RAPM reproduces across a split of its games.

    Games are split rather than possessions, for the same reason the solver's
    cross-validation folds on games: stints within a game share opponents,
    officials and pace, so splitting inside a game would leave each half
    carrying information about the other.

    Args:
        stints: Pooled stint rows for the window.
        seasons: Which seasons the rows came from, for reporting.
        alpha: Ridge penalty, held fixed across both halves and every draw so
            that only the data differs.
        draws: Random splits to average.
        possession_floor: Possessions a player needs in the window.
        cohort: Restrict to these player ids as well. Pass a fixed cohort when
            comparing windows of different lengths, or the comparison is
            contaminated by players entering and leaving.
        seed: Seed for the splits.

    Returns:
        A :class:`StabilityEstimate`.

    Raises:
        NotEnoughGamesError: If the window holds fewer than four games, which
            cannot be split into two halves each able to support a fit.
    """
    from pippen.rapm.possessions import possessions_by_player

    games = np.unique(stints["game_id"].to_numpy())
    if len(games) < 4:
        raise NotEnoughGamesError(
            f"only {len(games)} games in the window; splitting it in half leaves too little to fit"
        )

    counts = possessions_by_player(stints)
    eligible = set(counts[counts >= possession_floor].index)
    if cohort is not None:
        eligible &= set(cohort)

    generator = np.random.default_rng(seed)
    correlations: list[float] = []
    compared: list[float] = []

    for _ in range(draws):
        shuffled = generator.permutation(games)
        left_games = set(shuffled[: len(shuffled) // 2])
        left_rows = stints["game_id"].isin(left_games)

        left = fit_ridge(build_design(stints[left_rows]), alpha).ratings()
        right = fit_ridge(build_design(stints[~left_rows]), alpha).ratings()

        left_ratings = left.set_index("player_id")["total"]
        right_ratings = right.set_index("player_id")["total"]
        shared = sorted(set(left_ratings.index) & set(right_ratings.index) & eligible)
        if len(shared) < 3:
            continue
        correlations.append(
            float(left_ratings.loc[shared].corr(right_ratings.loc[shared], method="pearson"))
        )
        compared.append(float(len(shared)))

    if not correlations:
        raise NotEnoughGamesError(
            f"no split left three players above {possession_floor:,.0f} possessions in both halves"
        )

    return StabilityEstimate(
        seasons=seasons,
        possessions=float(stints["possessions"].sum()),
        players=int(np.mean(compared)),
        rho_half=float(np.mean(correlations)),
        rho_half_sd=float(np.std(correlations, ddof=1)) if len(correlations) > 1 else 0.0,
        draws=len(correlations),
        alpha=alpha,
    )
