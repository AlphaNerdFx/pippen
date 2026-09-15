"""The falsifiable claim this project was built to test.

The claim
---------
Does a reliability-aware fusion of public metrics predict a team's *next*
season net rating better than any single one of its inputs does?

Stated in advance, tested out of sample, and published whichever way it comes
out. A negative answer is a result: it would say that fusing these metrics adds
nothing over the best of them, which is worth knowing and is not something the
existing literature reports either way.

Why next-season net rating
--------------------------
It needs no external reference. Every alternative target this project
considered is either paywalled, unlicensed, or itself a modelling choice by
someone else. A team's net rating is arithmetic on the scoreboard.

Using *next* season rather than the current one is what makes it a test rather
than a restatement. Any player metric computed from a season's play will
correlate with that season's team results, because it was computed from them.
Predicting the following season asks whether the metric captured something
about the players that persists.

How a player rating becomes a team prediction
---------------------------------------------
Each team-season's players are aggregated by minutes played, which is the usual
convention and treats a rating as an estimate of value per unit of time on the
floor. The aggregate for season *N* is then used to predict net rating in
season *N+1*.

Rosters change between seasons, and no attempt is made to hide that. The
aggregate deliberately uses the roster as it was, not as it became: knowing
next season's roster would leak information the predictor would not have at the
time. The turnover is a real source of error and it is the same for every
metric being compared, which is what keeps the comparison fair.

What makes the comparison fair
------------------------------
Every candidate goes through the same pipeline: the same aggregation, the same
model class, the same folds. The only thing that differs is which player rating
goes in. A result where the fusion wins because it was given a better regressor
or more tuning would say nothing.

Folds are by season, never by team. Two teams in the same season share
opponents, and a model that saw part of a season would be predicting the rest
of it rather than the future.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from pippen.model.panel import TeamPanel
from pippen.rapm.possessions import read_season_stints

#: Points are quoted per this many possessions.
POSSESSIONS_PER_RATING: Final = 100

#: Minutes a player needs in a team-season to contribute to its aggregate.
DEFAULT_MINUTES_FLOOR: Final = 200.0


@dataclass(frozen=True)
class TeamSeasonRatings:
    """Offensive, defensive and net rating for every team in one season.

    Attributes:
        season: NBA season label.
        table: One row per team with ``possessions``, ``offensive_rating``,
            ``defensive_rating`` and ``net_rating``.
    """

    season: int
    table: pd.DataFrame

    def describe(self) -> str:
        """Return a one-line summary of the spread of net ratings."""
        net = self.table["net_rating"]
        return (
            f"NBA {self.season}: {len(self.table)} teams, net rating "
            f"{net.min():+.1f} to {net.max():+.1f}, sd {net.std():.2f}"
        )


def team_ratings(season: int) -> TeamSeasonRatings:
    """Compute each team's offensive, defensive and net rating from possessions.

    Built from the same stint data the RAPM uses rather than from a box score,
    so the possession definition is identical on both sides of the comparison.

    Args:
        season: NBA season label.

    Returns:
        A :class:`TeamSeasonRatings`.

    Raises:
        FileNotFoundError: If the season's stints have not been extracted.
    """
    stints = read_season_stints(season)

    scored = stints.groupby("offense_team_id").agg(
        points_for=("points", "sum"), offensive_possessions=("possessions", "sum")
    )
    conceded = stints.groupby("defense_team_id").agg(
        points_against=("points", "sum"), defensive_possessions=("possessions", "sum")
    )

    table = scored.join(conceded, how="inner")
    table["offensive_rating"] = (
        POSSESSIONS_PER_RATING * table["points_for"] / table["offensive_possessions"]
    )
    table["defensive_rating"] = (
        POSSESSIONS_PER_RATING * table["points_against"] / table["defensive_possessions"]
    )
    table["net_rating"] = table["offensive_rating"] - table["defensive_rating"]
    table["possessions"] = table["offensive_possessions"] + table["defensive_possessions"]
    table.index.name = "team_id"
    return TeamSeasonRatings(season=season, table=table.sort_values("net_rating", ascending=False))


def aggregate_to_team(
    player_values: pd.Series,
    minutes: pd.Series,
    team_of_player: pd.Series,
    *,
    minutes_floor: float = DEFAULT_MINUTES_FLOOR,
) -> pd.Series:
    """Aggregate a player rating to team level, weighted by minutes.

    Args:
        player_values: Rating per player.
        minutes: Minutes per player in the team-season.
        team_of_player: Team each player belongs to.
        minutes_floor: Players below this are dropped, since a rating resting
            on a handful of minutes is mostly the prior and would add noise to
            the team aggregate in proportion to how little it knows.

    Returns:
        One value per team, the minutes-weighted mean of its players' ratings.
    """
    frame = pd.DataFrame(
        {"value": player_values, "minutes": minutes, "team_id": team_of_player}
    ).dropna()
    frame = frame[frame["minutes"] >= minutes_floor]
    if frame.empty:
        return pd.Series(dtype="float64", name="team_value")

    weighted = frame.assign(product=frame["value"] * frame["minutes"])
    grouped = weighted.groupby("team_id").agg(total=("product", "sum"), weight=("minutes", "sum"))
    result = grouped["total"] / grouped["weight"]
    result.name = "team_value"
    return result


@dataclass(frozen=True)
class ClaimResult:
    """Out-of-sample accuracy of every candidate at the same task.

    Attributes:
        table: One row per candidate with its root mean squared error and how
            it compares to the best single input.
        squared_errors: Per-observation squared error for each candidate, so a
            difference in RMSE can be tested rather than eyeballed. Two
            candidates scored on the same team-seasons are paired, and a
            paired test is far more sensitive than comparing two RMSEs and
            guessing.
        observations: Team-seasons used.
        folds: How many leave-one-season-out folds were run.
    """

    table: pd.DataFrame
    squared_errors: pd.DataFrame
    observations: int
    folds: int

    @property
    def winner(self) -> str:
        """Name of the candidate with the lowest error."""
        return str(self.table.iloc[0]["candidate"])

    @property
    def fusion_wins(self) -> bool:
        """True when the fused rating has the lowest error of any candidate."""
        return self.winner == "fusion"

    def describe(self) -> str:
        """Return a one-line verdict, stated the same way whichever way it goes."""
        best = self.table.iloc[0]
        verdict = (
            "fusion wins" if self.fusion_wins else f"fusion does not win, {best['candidate']} does"
        )
        return (
            f"{verdict}: RMSE {best['rmse']:.3f} over {self.observations} team-seasons "
            f"in {self.folds} leave-one-season-out folds"
        )


def compare_candidates(panel: TeamPanel) -> ClaimResult:
    """Score every candidate at predicting the target, out of sample.

    Each candidate is a single column of the panel. Every one is fitted with
    the same one-variable linear model over the same leave-one-season-out
    folds, so the comparison isolates the rating rather than the modelling.

    A single variable has nothing to tune, so there is no nested search here.
    That makes these numbers directly comparable with the baselines only
    because the baselines do tune nested; a tuned model scored on the folds
    that chose its parameters would have an advantage this has no way to match.

    Args:
        panel: The table to score. Its construction has already dropped rows
            with no target, so every candidate sees the same team-seasons.

    Returns:
        A :class:`ClaimResult`, ordered best first.

    Raises:
        NotEnoughSeasonsError: If fewer than two seasons are present.
    """
    folds = panel.folds()

    records = []
    per_observation: dict[str, pd.Series] = {}
    for candidate in panel.candidates:
        column = panel.features[candidate]
        errors = pd.Series(np.nan, index=panel.features.index, dtype="float64")
        for fold in folds:
            usable_train = fold.train & column.notna()
            usable_test = fold.test & column.notna()
            if usable_train.sum() < 3 or usable_test.sum() == 0:
                continue
            slope, intercept = np.polyfit(column[usable_train], panel.target[usable_train], 1)
            predicted = slope * column[usable_test] + intercept
            errors.loc[usable_test] = ((predicted - panel.target[usable_test]) ** 2).to_numpy()
        if errors.notna().any():
            per_observation[candidate] = errors
            records.append({"candidate": candidate, "rmse": float(np.sqrt(errors.mean()))})

    table = pd.DataFrame(records).sort_values("rmse").reset_index(drop=True)
    if not table.empty:
        table["vs_best"] = (table["rmse"] - table["rmse"].iloc[0]).round(4)
    return ClaimResult(
        table=table,
        squared_errors=pd.DataFrame(per_observation),
        observations=panel.n_observations,
        folds=len(folds),
    )


@dataclass(frozen=True)
class PairedComparison:
    """Whether one candidate really beats another, or only appears to.

    Attributes:
        better: Candidate with the lower error.
        worse: The other one.
        rmse_gap: Difference in root mean squared error.
        mean_difference: Mean difference in squared error per observation.
        t_statistic: Paired t statistic on that difference.
        p_value: Two-sided p value.
        observations: Observations both candidates scored.
    """

    better: str
    worse: str
    rmse_gap: float
    mean_difference: float
    t_statistic: float
    p_value: float
    observations: int

    @property
    def distinguishable(self) -> bool:
        """True when the difference clears the conventional five percent."""
        return self.p_value < 0.05

    def describe(self) -> str:
        """Return a one-line verdict that does not overstate the evidence."""
        verdict = (
            f"{self.better} beats {self.worse}"
            if self.distinguishable
            else f"{self.better} and {self.worse} are not distinguishable"
        )
        return (
            f"{verdict}: RMSE gap {self.rmse_gap:+.3f}, paired t = {self.t_statistic:.2f}, "
            f"p = {self.p_value:.3f}, n = {self.observations}"
        )


def paired_comparison(result: ClaimResult, first: str, second: str) -> PairedComparison:
    """Test whether two candidates' errors really differ.

    Both are scored on the same team-seasons, so their squared errors are
    paired and a paired test uses that. Comparing two RMSEs and taking the
    smaller one as the winner ignores how much of the gap is sampling noise,
    which on a few hundred observations is usually most of it.

    Args:
        result: Output of :func:`compare_candidates`.
        first: A candidate name.
        second: Another candidate name.

    Returns:
        A :class:`PairedComparison`, with ``better`` set to whichever had the
        lower error.

    Raises:
        KeyError: If either candidate was not scored.
        ValueError: If fewer than three observations are shared.
    """
    from scipy import stats

    missing = [name for name in (first, second) if name not in result.squared_errors.columns]
    if missing:
        raise KeyError(f"not scored: {missing}")

    paired = result.squared_errors[[first, second]].dropna()
    if len(paired) < 3:
        raise ValueError(f"only {len(paired)} shared observations; a paired test needs three")

    left, right = paired[first], paired[second]
    if left.mean() <= right.mean():
        better, worse = first, second
    else:
        better, worse = second, first

    difference = paired[worse] - paired[better]
    statistic, p_value = stats.ttest_rel(paired[worse], paired[better])
    return PairedComparison(
        better=better,
        worse=worse,
        rmse_gap=float(np.sqrt(paired[worse].mean()) - np.sqrt(paired[better].mean())),
        mean_difference=float(difference.mean()),
        t_statistic=float(statistic),
        p_value=float(p_value),
        observations=len(paired),
    )
