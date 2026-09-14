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

from pippen.rapm.possessions import read_season_stints

#: Points are quoted per this many possessions.
POSSESSIONS_PER_RATING: Final = 100

#: Minutes a player needs in a team-season to contribute to its aggregate.
DEFAULT_MINUTES_FLOOR: Final = 200.0


class NotEnoughSeasonsError(ValueError):
    """Fewer than two seasons, so no season can predict the next."""


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
        observations: Team-seasons used.
        folds: How many leave-one-season-out folds were run.
    """

    table: pd.DataFrame
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


def compare_candidates(
    features: pd.DataFrame,
    target: pd.Series,
    seasons: pd.Series,
) -> ClaimResult:
    """Score every candidate at predicting the target, out of sample.

    Each candidate is a single column of ``features``. Every one is fitted with
    the same one-variable linear model over the same leave-one-season-out
    folds, so the comparison isolates the rating rather than the modelling.

    Args:
        features: One column per candidate, indexed by team-season.
        target: Next season's net rating for the same index.
        seasons: Season each row belongs to, used to form the folds.

    Returns:
        A :class:`ClaimResult`, ordered best first.

    Raises:
        NotEnoughSeasonsError: If fewer than two seasons are present, leaving
            no fold that holds one out.
    """
    distinct = sorted(seasons.unique())
    if len(distinct) < 2:
        raise NotEnoughSeasonsError(
            f"only {len(distinct)} season(s) available; a leave-one-season-out "
            f"comparison needs at least two"
        )

    records = []
    for candidate in features.columns:
        column = features[candidate]
        usable = column.notna() & target.notna()
        errors: list[float] = []
        for held_out in distinct:
            test = usable & (seasons == held_out)
            train = usable & (seasons != held_out)
            if train.sum() < 3 or test.sum() == 0:
                continue
            slope, intercept = np.polyfit(column[train], target[train], 1)
            predicted = slope * column[test] + intercept
            errors.extend(((predicted - target[test]) ** 2).tolist())
        if errors:
            records.append({"candidate": candidate, "rmse": float(np.sqrt(np.mean(errors)))})

    table = pd.DataFrame(records).sort_values("rmse").reset_index(drop=True)
    if not table.empty:
        table["vs_best"] = (table["rmse"] - table["rmse"].iloc[0]).round(4)
    return ClaimResult(
        table=table,
        observations=int((features.notna().any(axis=1) & target.notna()).sum()),
        folds=len(distinct),
    )
