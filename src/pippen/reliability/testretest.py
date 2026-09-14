r"""Split-half reliability, measured rather than assigned.

The problem this replaces
-------------------------
Metric surveys score reliability by expert judgment across a handful of
criteria. The survey this project grew from does exactly that, and its own
methodology section concedes the scores "involve some judgment". For a project
whose premise is accounting for reliability, an unfalsifiable reliability score
is the wrong foundation.

Reliability has a standard definition in measurement theory: the share of a
measurement's variance that is signal rather than noise. It is estimated by
measuring the same thing twice and correlating the results. For a season
metric, the two measurements come from splitting the season.

How the season is split
-----------------------
Each player's games are shuffled and dealt alternately into two halves, so the
halves are balanced to within one game. That is repeated
:data:`DEFAULT_SPLITS` times and the correlations averaged.

Repeated random splits rather than one odd-even split, because a single split
is one draw from a sampling distribution with real spread. Measured on 2024,
the standard deviation of the true-shooting correlation across splits is about
0.03, so a single split lands anywhere in a window six hundredths wide, which
moves any downstream weight by roughly fifteen percent. Averaging a hundred
splits cuts that by a factor of ten.

Odd-even remains available through :data:`SplitRule` and is reported alongside,
because it is the convention in the sports-analytics literature and a reader
will ask why the project departed from it.

Correlation type
----------------
Pearson, because the Spearman-Brown correction is derived from classical test
theory, where a score is a true score plus independent additive error, and that
derivation assumes a Pearson correlation. Applying a length correction to a rank
correlation has no theoretical justification, though it is done often. Spearman
is computed and reported alongside as a robustness check and is never corrected.
A large gap between them is a finding about that metric's outliers.

Why the correlation is not weighted by minutes
----------------------------------------------
Weighting pulls the estimate toward the players whose halves agree most, which
raises every reliability figure, and raises it most for the noisiest metrics.
Measured on 2024, minute-weighting adds 0.033 to the true-shooting correlation
and 0.001 to points per game: it inflates exactly where inflation does most
damage. It would also make the figure non-comparable across eras, since two
leagues with identical metrics and different minute distributions would report
different reliabilities.

The sample-size dependence is instead made explicit through
:func:`reliability_curve`, which recomputes at a series of minute floors so a
reader can see it rather than have it folded invisibly into a coefficient.

The length problem
------------------
Spearman-Brown converts a correlation between two half-length measurements into
the reliability of a measurement `n` times as long:

.. math::

    r_{n} = \frac{n \rho}{1 + (n - 1) \rho}

with `n = 2` recovering the familiar half-to-whole form. The correction is the
reason this module never returns a bare reliability figure. A metric at
`rho = 0.5` reports 0.67 at one season and 0.86 at three, and those imply
downstream weights differing by a factor of three. So
:class:`SplitHalfEstimate` stores the half correlation together with the number
of games behind it, and any caller wanting a reliability must say what length
it wants by calling :meth:`SplitHalfEstimate.reliability_at`.

What this module deliberately does not provide
----------------------------------------------
There is no function returning `r / (1 - r)`.

Reliability sets a ceiling on how much a metric can contribute; it does not set
the contribution. Points per game correlates with itself at roughly 0.97 over a
full season, which as an inverse-variance weight is about 65. A one-season RAPM
sits nearer 0.6, giving about 1.5. Weighting by reliability alone would count
scoring volume forty times more heavily than the impact estimate, and every
diagnostic downstream would look healthy while it happened.

The missing piece is how much of each metric's own quantity is the latent
quantity of interest, which is the loading the fusion model estimates. Since the
two must be estimated together, this module exposes only what it measured, and
the fusion model is required to do the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

import numpy as np
import pandas as pd

from pippen.reliability.metrics import METRICS, Metric, compute, summarise_totals

#: Random splits averaged over, unless a caller says otherwise.
DEFAULT_SPLITS: Final = 100

#: Minutes a player-season needs to enter the correlation.
DEFAULT_MINUTES_FLOOR: Final = 500.0

#: Nested floors the reliability curve is reported at. Nested rather than
#: banded: disjoint bands confound precision with range restriction, since
#: high-minute players are more alike than the league at large and a
#: correlation shrinks when the spread of true values shrinks.
DEFAULT_FLOORS: Final = (200.0, 500.0, 1000.0, 1500.0)

#: Seed, matching the project-wide default.
DEFAULT_SEED: Final = 20260910


class SplitRule(str, Enum):
    """How a player's games are dealt into two halves."""

    RANDOM = "random"
    ODD_EVEN = "odd_even"


class NotEnoughPlayersError(ValueError):
    """Too few players cleared the floor for a correlation to mean anything."""


@dataclass(frozen=True)
class SplitHalfEstimate:
    """What was measured for one metric in one season.

    Deliberately stores a half-length correlation and the number of games
    behind it, never a bare reliability. See the module docstring.

    Attributes:
        metric: Metric name.
        season: hoopR season label.
        rule: How the halves were formed.
        rho_half: Mean Pearson correlation between halves across splits.
        rho_half_sd: Standard deviation of that correlation across splits,
            which says how much a single split would have wandered.
        rho_half_spearman: Mean rank correlation, uncorrected, for comparison.
        games_per_half: Mean games behind each half measurement.
        players: Players entering the correlation.
        minutes_floor: Minutes a player needed.
        splits: How many splits were averaged.
        traded_share: Fraction of included players who appeared for more than
            one team.
    """

    metric: str
    season: int
    rule: SplitRule
    rho_half: float
    rho_half_sd: float
    rho_half_spearman: float
    games_per_half: float
    players: int
    minutes_floor: float
    splits: int
    traded_share: float

    def reliability_at(self, games: float) -> float:
        """Return the reliability this metric would have over ``games`` games.

        Args:
            games: Length to quote at, in games. One season is about 82; a
                three-season window about 246.

        Returns:
            The Spearman-Brown corrected reliability, clipped to below 1.

        Raises:
            ValueError: If ``games`` is not positive.
        """
        if games <= 0:
            raise ValueError(f"games must be positive, got {games!r}")
        ratio = games / self.games_per_half
        corrected = ratio * self.rho_half / (1.0 + (ratio - 1.0) * self.rho_half)
        return float(min(corrected, 0.9999))

    @property
    def reliability_at_observed_length(self) -> float:
        """Reliability over both halves together, which is the season as played.

        Named for the observed length rather than "one season" on purpose.
        ``games_per_half`` counts games a qualifying player actually appeared
        in, which averaged 31.5 in 2024 rather than 41, because players miss
        games. So this is the reliability of the metric as computed over a
        typical qualifying player's real season, not over a hypothetical 82.
        For the latter, call ``reliability_at(82)``.
        """
        return self.reliability_at(self.games_per_half * 2.0)

    def describe(self) -> str:
        """Return a one-line summary naming the length, never a bare figure."""
        return (
            f"{self.metric} {self.season}: rho_half {self.rho_half:.3f} "
            f"(sd {self.rho_half_sd:.3f}) over {self.games_per_half:.1f} games per half, "
            f"{self.players} players, reliability at the observed length "
            f"{self.reliability_at_observed_length:.3f}"
        )


def spearman_brown(rho: float, ratio: float) -> float:
    """Correct a correlation for a change in measurement length.

    Args:
        rho: Correlation between two measurements of the current length.
        ratio: How many times longer the target measurement is. ``2`` converts
            a half-season correlation to a full-season reliability.

    Returns:
        The corrected reliability.

    Raises:
        ValueError: If ``ratio`` is not positive.
    """
    if ratio <= 0:
        raise ValueError(f"ratio must be positive, got {ratio!r}")
    return float(ratio * rho / (1.0 + (ratio - 1.0) * rho))


def _assign_halves(
    rows: pd.DataFrame, rule: SplitRule, generator: np.random.Generator
) -> pd.Series:
    """Deal each player's games alternately into two halves.

    Alternating a shuffled order rather than flipping a coin per game, so the
    halves are balanced to within one game. Independent coin flips would leave
    some players with a 12-game half against a 30-game half, and the resulting
    correlation would partly measure that imbalance.

    Args:
        rows: Eligible box score rows for one season.
        rule: Random deals a shuffled order; odd-even deals by date.
        generator: Source of randomness for the shuffle.

    Returns:
        A Series of 0 or 1 aligned to ``rows``.
    """
    if rule is SplitRule.RANDOM:
        order = pd.Series(generator.random(len(rows)), index=rows.index)
    else:
        order = rows["game_date"]
    position = order.groupby(rows["athlete_id"]).rank(method="first")
    return (position.astype(int) % 2).astype(int)


def _half_values(
    rows: pd.DataFrame, halves: pd.Series, metric: Metric, season: int
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return each half's metric values and the games behind them."""
    first = summarise_totals(rows[halves == 0])
    second = summarise_totals(rows[halves == 1])
    shared = first.index.intersection(second.index)
    games = (first.loc[shared, "games"] + second.loc[shared, "games"]) / 2.0
    return (
        compute(metric, first.loc[shared], season),
        compute(metric, second.loc[shared], season),
        games,
    )


def split_half(
    rows: pd.DataFrame,
    metric: Metric,
    season: int,
    *,
    rule: SplitRule = SplitRule.RANDOM,
    splits: int = DEFAULT_SPLITS,
    minutes_floor: float = DEFAULT_MINUTES_FLOOR,
    seed: int = DEFAULT_SEED,
) -> SplitHalfEstimate:
    """Measure one metric's split-half correlation for one season.

    Args:
        rows: Eligible box score rows, from
            :func:`pippen.reliability.metrics.eligible_rows`.
        metric: The metric to measure.
        season: hoopR season label.
        rule: How to form the halves. Odd-even ignores ``splits``, since it is
            deterministic and repeating it would average identical numbers.
        splits: Random splits to average.
        minutes_floor: Minutes a player needs across the whole season.
        seed: Seed for the shuffles.

    Returns:
        A :class:`SplitHalfEstimate`.

    Raises:
        NotEnoughPlayersError: If fewer than three players clear the floor.
    """
    season_totals = summarise_totals(rows)
    qualified = season_totals[season_totals["minutes"] >= minutes_floor]
    if len(qualified) < 3:
        raise NotEnoughPlayersError(
            f"only {len(qualified)} players reached {minutes_floor:.0f} minutes in "
            f"{season}; a split-half correlation needs at least three"
        )

    eligible = rows[rows["athlete_id"].isin(qualified.index)]
    traded_share = float((qualified["teams"] > 1).mean())

    generator = np.random.default_rng(seed)
    draws = 1 if rule is SplitRule.ODD_EVEN else splits

    pearson: list[float] = []
    spearman: list[float] = []
    games: list[float] = []
    players: list[int] = []

    for _ in range(draws):
        halves = _assign_halves(eligible, rule, generator)
        first, second, per_half = _half_values(eligible, halves, metric, season)
        usable = first.notna() & second.notna()
        if usable.sum() < 3:
            continue
        left, right = first[usable], second[usable]
        pearson.append(float(left.corr(right, method="pearson")))
        spearman.append(float(left.corr(right, method="spearman")))
        games.append(float(per_half[usable].mean()))
        players.append(int(usable.sum()))

    if not pearson:
        raise NotEnoughPlayersError(
            f"no split of {season} left three players with a defined {metric.name}"
        )

    return SplitHalfEstimate(
        metric=metric.name,
        season=season,
        rule=rule,
        rho_half=float(np.mean(pearson)),
        rho_half_sd=float(np.std(pearson, ddof=1)) if len(pearson) > 1 else 0.0,
        rho_half_spearman=float(np.mean(spearman)),
        games_per_half=float(np.mean(games)),
        players=int(np.mean(players)),
        minutes_floor=minutes_floor,
        splits=len(pearson),
        traded_share=traded_share,
    )


def measure_season(
    rows: pd.DataFrame,
    season: int,
    *,
    metrics: tuple[Metric, ...] = METRICS,
    rule: SplitRule = SplitRule.RANDOM,
    splits: int = DEFAULT_SPLITS,
    minutes_floor: float = DEFAULT_MINUTES_FLOOR,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """Measure every metric for one season.

    Args:
        rows: Eligible box score rows for the season.
        season: hoopR season label.
        metrics: Metrics to measure.
        rule: How to form the halves.
        splits: Random splits to average.
        minutes_floor: Minutes a player needs.
        seed: Seed for the shuffles.

    Returns:
        One row per metric, carrying the half correlation, its spread, the
        games behind it, and the reliability implied at two lengths. No column
        is named ``reliability`` on its own: the length is always in the name,
        because the same metric implies very different weights at one season
        and at three.
    """
    records = []
    for metric in metrics:
        estimate = split_half(
            rows,
            metric,
            season,
            rule=rule,
            splits=splits,
            minutes_floor=minutes_floor,
            seed=seed,
        )
        records.append(
            {
                "metric": estimate.metric,
                "season": estimate.season,
                "rho_half": estimate.rho_half,
                "rho_half_sd": estimate.rho_half_sd,
                "rho_half_spearman": estimate.rho_half_spearman,
                "games_per_half": estimate.games_per_half,
                "players": estimate.players,
                "traded_share": estimate.traded_share,
                "reliability_at_observed_length": estimate.reliability_at_observed_length,
                "reliability_at_82_games": estimate.reliability_at(82.0),
            }
        )
    return pd.DataFrame(records).sort_values("rho_half", ascending=False).reset_index(drop=True)


def reliability_curve(
    rows: pd.DataFrame,
    metric: Metric,
    season: int,
    *,
    floors: tuple[float, ...] = DEFAULT_FLOORS,
    splits: int = DEFAULT_SPLITS,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """Measure one metric at a series of nested minute floors.

    Reliability is a property of a metric *at a given sample size*, and
    collapsing it to one number repeats the mistake the tier system made. The
    floors are nested rather than banded on purpose: disjoint bands confound
    precision with range restriction, because high-minute players are more
    alike than the league at large and a correlation falls when the spread of
    true values falls, however precisely each is measured.

    Args:
        rows: Eligible box score rows.
        metric: The metric to measure.
        season: hoopR season label.
        floors: Minute floors, ascending.
        splits: Random splits to average at each floor.
        seed: Seed for the shuffles.

    Returns:
        One row per floor.
    """
    records = []
    for floor in floors:
        try:
            estimate = split_half(
                rows, metric, season, splits=splits, minutes_floor=floor, seed=seed
            )
        except NotEnoughPlayersError:
            continue
        records.append(
            {
                "metric": metric.name,
                "season": season,
                "minutes_floor": floor,
                "players": estimate.players,
                "rho_half": estimate.rho_half,
                "rho_half_sd": estimate.rho_half_sd,
                "reliability_at_observed_length": estimate.reliability_at_observed_length,
                "reliability_at_82_games": estimate.reliability_at(82.0),
            }
        )
    return pd.DataFrame(records)
