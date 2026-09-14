"""The box-score metrics whose reliability gets measured, and how to build them.

What a metric is here
---------------------
A metric is a function from a player's *summed counting stats over a set of
games* to a single number. That definition is what makes split-half reliability
possible: give the same function two disjoint halves of a season and it returns
two measurements of the same player, which is exactly what reliability needs.

It also rules out anything that cannot be recomputed from a subset of games.
A season-long rank, a percentile, or anything normalised against the league
average would change meaning when computed on half a season, so none appear
here.

Rates, not counts
-----------------
Every metric is a rate: per 36 minutes, per game, or per attempt. A counting
total would be twice as large on a full season as on a half, so the two halves
would not be measuring the same quantity and the correlation would be measuring
playing time.

Per 36 minutes is the convention for box-score rates and is used here rather
than per 100 possessions, because possessions need team context that a player
box score does not carry.

The possession coefficient
--------------------------
True shooting and the usage proxy both need the fraction of free throw attempts
that consume a possession. This project measured that per season rather than
taking the conventional 0.44, and found every one of 25 seasons below it. So
these use :func:`pippen.data.possession_coefficient.coefficient_for_season`, not
the constant. Using 0.44 here would contradict the project's own finding.

What is deliberately absent
---------------------------
Assist percentage and rebound percentage are Tier 3 metrics in the source
research and are not here. Both need team totals *while the player was on the
floor*, which a box score cannot supply: it records team totals for the whole
game. Computing them from game-level totals would silently measure something
else. They become available once lineup data is joined, which is a later step.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from pippen.data.possession_coefficient import coefficient_for_season

#: Minutes a rate is quoted per.
MINUTES_BASIS: Final = 36.0

#: Games a team must play in a season for its games to count as regular season.
#: Every real team plays at least 66 in the seasons on disk; the All-Star
#: pseudo-teams play at most 3. See docs/methodology/data-quirks.md for why a
#: season_type filter is not enough.
MINIMUM_TEAM_GAMES: Final = 40

#: hoopR's code for regular season games.
REGULAR_SEASON_TYPE: Final = 2

#: Counting columns summed per player per half before any metric is computed.
COUNTING_COLUMNS: Final = (
    "minutes",
    "field_goals_made",
    "field_goals_attempted",
    "three_point_field_goals_made",
    "three_point_field_goals_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "offensive_rebounds",
    "defensive_rebounds",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fouls",
    "points",
)


class MissingColumnsError(ValueError):
    """A box score is missing a column the metrics need."""


@dataclass(frozen=True)
class Metric:
    """One measurable quantity.

    Attributes:
        name: Identifier used in output tables.
        description: One line, for the published reliability table.
        compute: Takes summed counting stats and the season's possession
            coefficient, returns one value per row.
        denominator: Column whose total says how much evidence is behind the
            value. Used to drop rows where the metric is undefined or is
            resting on almost nothing, such as a shooting percentage from two
            attempts.
        minimum_denominator: How much of that is required.
    """

    name: str
    description: str
    compute: Callable[[pd.DataFrame, float], pd.Series]
    denominator: str
    minimum_denominator: float


def _per_36(column: str) -> Callable[[pd.DataFrame, float], pd.Series]:
    """Build a per-36-minute rate for one counting column."""

    def rate(totals: pd.DataFrame, coefficient: float) -> pd.Series:
        del coefficient
        return MINUTES_BASIS * totals[column] / totals["minutes"]

    return rate


def _true_shooting(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Points per shooting possession, counting free throws at the measured rate."""
    attempts = 2.0 * (
        totals["field_goals_attempted"] + coefficient * totals["free_throws_attempted"]
    )
    return totals["points"] / attempts


def _effective_field_goal(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Field goal percentage with a three counted as one and a half twos."""
    del coefficient
    made = totals["field_goals_made"] + 0.5 * totals["three_point_field_goals_made"]
    return made / totals["field_goals_attempted"]


def _free_throw_rate(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Free throw attempts per field goal attempt."""
    del coefficient
    return totals["free_throws_attempted"] / totals["field_goals_attempted"]


def _three_point_rate(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Share of field goal attempts taken from three."""
    del coefficient
    return totals["three_point_field_goals_attempted"] / totals["field_goals_attempted"]


def _free_throw_percentage(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Free throws made per attempt.

    Included as a reference point. Free throw shooting is about the most
    repeatable thing a player does, so a naive reading expects it at the top of
    any reliability table. Measured on 2024 it is not: 0.80 against 0.96 for
    points per 36 minutes.

    That is not a defect, and understanding why matters for reading the whole
    table. A split-half correlation measures how well a metric *tells players
    apart*, which depends on the spread of true values as much as on
    measurement precision. Points per 36 ranges from about 5 to 35 across the
    league, so even a noisy estimate separates players easily. Free throw
    percentage spans roughly .65 to .90, and at a hundred attempts per half the
    binomial noise is an appreciable share of that range.

    So reliability is a property of a metric in a population, not of the
    measurement alone, and a low figure can mean "players are alike here"
    rather than "this is measured badly".
    """
    del coefficient
    return totals["free_throws_made"] / totals["free_throws_attempted"]


def _usage_proxy(totals: pd.DataFrame, coefficient: float) -> pd.Series:
    """Possessions a player ended, per 36 minutes.

    Not usage percentage, which needs team possessions while the player was on
    the floor. This counts the numerator only, which is a player-level quantity
    a box score can supply honestly.
    """
    ended = (
        totals["field_goals_attempted"]
        + coefficient * totals["free_throws_attempted"]
        + totals["turnovers"]
    )
    return MINUTES_BASIS * ended / totals["minutes"]


METRICS: Final[tuple[Metric, ...]] = (
    Metric("points_per_36", "Points per 36 minutes", _per_36("points"), "minutes", 100.0),
    Metric("rebounds_per_36", "Rebounds per 36 minutes", _per_36("rebounds"), "minutes", 100.0),
    Metric("assists_per_36", "Assists per 36 minutes", _per_36("assists"), "minutes", 100.0),
    Metric("steals_per_36", "Steals per 36 minutes", _per_36("steals"), "minutes", 100.0),
    Metric("blocks_per_36", "Blocks per 36 minutes", _per_36("blocks"), "minutes", 100.0),
    Metric("turnovers_per_36", "Turnovers per 36 minutes", _per_36("turnovers"), "minutes", 100.0),
    Metric("fouls_per_36", "Fouls per 36 minutes", _per_36("fouls"), "minutes", 100.0),
    Metric(
        "offensive_rebounds_per_36",
        "Offensive rebounds per 36 minutes",
        _per_36("offensive_rebounds"),
        "minutes",
        100.0,
    ),
    Metric(
        "defensive_rebounds_per_36",
        "Defensive rebounds per 36 minutes",
        _per_36("defensive_rebounds"),
        "minutes",
        100.0,
    ),
    Metric(
        "usage_proxy_per_36", "Possessions ended per 36 minutes", _usage_proxy, "minutes", 100.0
    ),
    Metric(
        "true_shooting",
        "Points per shooting possession, free throws at the measured coefficient",
        _true_shooting,
        "field_goals_attempted",
        50.0,
    ),
    Metric(
        "effective_field_goal",
        "Field goal percentage counting a three as one and a half twos",
        _effective_field_goal,
        "field_goals_attempted",
        50.0,
    ),
    Metric(
        "free_throw_rate",
        "Free throw attempts per field goal attempt",
        _free_throw_rate,
        "field_goals_attempted",
        50.0,
    ),
    Metric(
        "three_point_rate",
        "Share of field goal attempts taken from three",
        _three_point_rate,
        "field_goals_attempted",
        50.0,
    ),
    Metric(
        "free_throw_percentage",
        "Free throws made per attempt, included as a sanity reference",
        _free_throw_percentage,
        "free_throws_attempted",
        25.0,
    ),
)

#: Metrics keyed by name.
BY_NAME: Final[Mapping[str, Metric]] = {metric.name: metric for metric in METRICS}


def eligible_rows(player_box: pd.DataFrame) -> pd.DataFrame:
    """Return the regular-season rows a player actually played in.

    Applies three filters, in order:

    1. hoopR's regular-season code, which is necessary and not sufficient.
    2. The team-games rule, which removes the All-Star exhibition. hoopR labels
       it as regular season under pseudo-teams whose abbreviations change
       format almost every year, so a name list would need maintaining; a team
       that appears in fewer than :data:`MINIMUM_TEAM_GAMES` games cannot be a
       real one.
    3. Rows where the player did not appear, since a did-not-play contributes
       nothing and a zero-minute row would divide by zero.

    Args:
        player_box: A hoopR player box score for one season.

    Returns:
        The eligible subset, with the original columns.

    Raises:
        MissingColumnsError: If a required column is absent.
    """
    required = {"season_type", "game_id", "team_id", "athlete_id", "minutes", "did_not_play"}
    missing = sorted(required - set(player_box.columns))
    if missing:
        raise MissingColumnsError(f"player box is missing columns: {missing}")

    regular = player_box[player_box["season_type"] == REGULAR_SEASON_TYPE]
    team_games = (
        regular.drop_duplicates(["game_id", "team_id"]).groupby("team_id")["game_id"].nunique()
    )
    real_teams = set(team_games[team_games >= MINIMUM_TEAM_GAMES].index)
    regular = regular[regular["team_id"].isin(real_teams)]

    played = regular[~regular["did_not_play"].astype(bool)]
    return played[played["minutes"].fillna(0) > 0]


def summarise_totals(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum counting stats per player over whatever rows are given.

    Args:
        rows: Eligible box score rows, typically one half of a season.

    Returns:
        One row per ``athlete_id`` carrying every column in
        :data:`COUNTING_COLUMNS` plus ``games`` and ``teams``. ``teams`` counts
        distinct franchises, which is how a mid-season trade is detected.
    """
    available = [column for column in COUNTING_COLUMNS if column in rows.columns]
    grouped = rows.groupby("athlete_id")
    totals = grouped[available].sum()
    totals["games"] = grouped["game_id"].nunique()
    totals["teams"] = grouped["team_id"].nunique()
    return totals


def compute(metric: Metric, totals: pd.DataFrame, season: int) -> pd.Series:
    """Evaluate one metric over summed totals, masking rows with too little evidence.

    Args:
        metric: The metric to evaluate.
        totals: Output of :func:`summarise_totals`.
        season: hoopR season label, used to pick the measured possession
            coefficient.

    Returns:
        One value per player, with ``NaN`` where the denominator falls below
        the metric's minimum or the value is not finite. A percentage computed
        from two attempts is not a weak measurement, it is a different quantity,
        so it is removed rather than down-weighted.
    """
    coefficient = coefficient_for_season(season)
    values = metric.compute(totals, coefficient)
    enough = totals[metric.denominator] >= metric.minimum_denominator
    return values.where(enough & np.isfinite(values))
