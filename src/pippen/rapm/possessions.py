"""Possession and stint extraction, the input to the RAPM design matrix.

What a stint is, and why the unit matters
-----------------------------------------
RAPM regresses scoring margin on who was on the floor. The row unit is a
*stint*: a stretch of play with the same ten players. Everything a stint needs
is a pair of five-man lineups, how many possessions they faced each other for,
and how many points were scored. Individual possessions carry no extra
information once those are known, so this module aggregates to one row per
``(offensive lineup, defensive lineup)`` pair per game. For a typical game that
turns roughly 200 possessions into about 30 rows, and the aggregation is
lossless for the regression that consumes it.

Where the numbers come from
---------------------------
``pbpstats`` decides which possessions count and which lineup is credited, and
this module takes that decision rather than re-deriving it. Two of its
per-possession statistics carry everything needed:

``OffPoss``
    Present once per player on the offensive lineup when the possession counts
    as an offensive possession. Its absence marks the period-boundary
    artefacts that should not be counted; in the game checked below, 205 parsed
    possessions yielded 203 counted ones.

``OpponentPoints``
    Attached to the defending players, giving the points the offense scored on
    that possession. Absent when the possession scored nothing.

Both rows carry ``lineup_id`` and ``opponent_lineup_id``, so the lineup
attribution comes from ``pbpstats`` too, including its handling of
substitutions that land inside a possession.

Reconciliation
--------------
On game ``0022300001`` this produces 102 offensive possessions and 121 points
for Indiana against 101 and 116 for Cleveland. The official box score in the
same game's detail file records 121 and 116. Points reconciling exactly is the
check that the possession walk did not drop or double-count events;
:func:`reconcile_points` runs it for any game, and Phase 2's property tests run
it across a season.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import pandas as pd

from pippen.paths import stage_dir
from pippen.rapm.pbp_source import game_path, season_game_ids

#: Separator ``pbpstats`` uses between player ids inside a lineup id.
LINEUP_SEPARATOR: Final = "-"

#: Players a valid lineup must name.
PLAYERS_PER_LINEUP: Final = 5

_OFF_POSS_KEY: Final = "OffPoss"
_OPPONENT_POINTS_KEY: Final = "OpponentPoints"

STINT_COLUMNS: Final = (
    "game_id",
    "offense_team_id",
    "defense_team_id",
    "offense_lineup",
    "defense_lineup",
    "possessions",
    "points",
    "opponent_points",
)


class MissingPlayByPlayError(FileNotFoundError):
    """A game's play-by-play has not been downloaded yet."""


@dataclass(frozen=True)
class PointsReconciliation:
    """Comparison of possession-derived points against a reference score.

    Attributes:
        game_id: The game checked.
        derived: Points per team id, summed from possessions.
        reference: Points per team id from the reference source.
    """

    game_id: str
    derived: dict[int, int]
    reference: dict[int, int]

    @property
    def agrees(self) -> bool:
        """True when every team's derived total equals its reference total."""
        return self.derived == self.reference

    def describe(self) -> str:
        """Return a one-line description of the comparison."""
        if self.agrees:
            return f"{self.game_id}: points reconcile ({self.derived})"
        return f"{self.game_id}: derived {self.derived} != reference {self.reference}"


@lru_cache(maxsize=4)
def _client(cache_dir: str) -> Any:
    """Return a ``pbpstats`` client reading from ``cache_dir``.

    Cached because constructing a client scans the resource and loader
    packages, which is wasted work when extracting thousands of games. The
    cache key is the directory, so a test pointing at a different root gets its
    own client.

    Args:
        cache_dir: Directory holding the ``pbpstats`` file layout.

    Returns:
        A configured ``pbpstats.client.Client``.

    Raises:
        ImportError: If ``pbpstats`` is not installed.
    """
    from pbpstats.client import Client

    return Client(
        {
            "dir": cache_dir,
            "Possessions": {"source": "file", "data_provider": "data_nba"},
        }
    )


def _assign_event_order(possessions: list[Any]) -> int:
    """Give every event an ``order`` when the upstream feed omitted it.

    ``pbpstats`` sorts simultaneous events by an ``order`` attribute, which its
    data.nba.com event class populates from the raw ``ord`` key. That key
    appears from the 2023-24 season onward and is absent before it: the 2016-17
    feed carries none at all. Without it, any rebound reaching
    ``is_turnover_placeholder`` raises ``AttributeError: 'DataRebound' object
    has no attribute 'order'``, which takes down every game of every affected
    season.

    The attribute is reconstructible exactly. In ``pbpstats``' other provider
    ``order`` is the index at which the event occurs in the feed, so numbering
    the events in feed order reproduces the same quantity. Feed order is
    ``(period, event_num)``, and ``event_num`` comes from the ``evt`` key,
    which every season supplies.

    Collecting the events takes a little care: ``previous_event`` and
    ``next_event`` link events only within a period, so walking one chain from
    the first possession reaches period one and stops. On the game checked that
    is 134 events out of 485. This walks the chain attached to every possession
    and unions the results, which also picks up events belonging to no
    possession, such as period boundaries, since those still appear in the
    chain and can still be compared against.

    Args:
        possessions: Parsed possessions for one game.

    Returns:
        How many events were given an order. Zero means the feed supplied
        ``ord`` and nothing was changed.
    """
    if not possessions:
        return 0

    events: dict[int, Any] = {}
    for possession in possessions:
        for event in possession.events:
            if id(event) in events:
                continue
            head = event
            while head.previous_event is not None:
                head = head.previous_event
            walker = head
            while walker is not None:
                events[id(walker)] = walker
                walker = walker.next_event

    if any(hasattr(event, "order") for event in events.values()):
        return 0

    ordered = sorted(events.values(), key=lambda event: (event.period, event.event_num))
    for index, event in enumerate(ordered):
        event.order = index
    return len(ordered)


def load_possessions(game_id: str) -> list[Any]:
    """Return the parsed possessions for one game.

    Args:
        game_id: NBA game id, such as ``0022300001``.

    Returns:
        The ``pbpstats`` possession objects, in game order.

    Raises:
        MissingPlayByPlayError: If the game has not been downloaded. Raised in
            preference to letting ``pbpstats`` fail later with a less specific
            error, since a missing download is the expected cause.
    """
    path: Path = game_path(game_id)
    if not path.exists():
        raise MissingPlayByPlayError(
            f"no play-by-play cached for game {game_id}; expected {path}. "
            f"Run the fetch for its season first."
        )
    client = _client(str(path.parent.parent))
    game = client.Game(game_id)
    possessions = list(game.possessions.items)
    _assign_event_order(possessions)
    return possessions


def _possession_row(possession: Any) -> dict[str, Any] | None:
    """Reduce one possession to the fields a stint needs, or None if it does not count.

    Points need care for two separate reasons.

    Substitutions inside a possession
        ``pbpstats`` groups its per-possession statistics by lineup, so a
        substitution during a possession splits the scoring into two groups. It
        happens on the dead ball after a foul: a free throw is taken, both
        teams substitute, and play resumes on the same possession. In game
        ``0021600001`` possession 31 is exactly that, with ``OpponentPoints``
        of 2 and 1 in separate groups, and reading only the first loses a
        point. Summing one value per group recovers the total.

    The defence can score during the offence's possession
        A technical or away-from-play free throw is shot by whichever team was
        fouled, which may be the team on defence, and the possession does not
        change hands. Crediting every point in the possession to the offence
        therefore moves a point onto the wrong team. Across the first forty
        games of 2016-17 that showed up as scores whose total was right and
        whose split was off by one.

    So points are attributed by which team actually scored, read from each
    row's ``opponent_team_id``, and returned as two figures. ``points`` is what
    the offence scored, which is the RAPM target. ``opponent_points`` is what
    the defence scored during the same possession, which is almost always zero
    and exists so the totals can be checked against an official score.

    The possession itself is not split. ``pbpstats`` credits a single
    ``OffPoss`` however many substitutions happen inside it, so a possession is
    attributed whole to the lineups that started it. Splitting it would mean
    fractional possessions, and the regression weight would stop being a count.

    Args:
        possession: A ``pbpstats`` possession.

    Returns:
        A mapping with both team ids, both lineup ids and both point totals, or
        ``None`` when the possession carries no ``OffPoss`` statistic and
        therefore is not a counted possession.
    """
    stats = possession.possession_stats
    offensive = next((row for row in stats if row["stat_key"] == _OFF_POSS_KEY), None)
    if offensive is None:
        return None

    offense_team = int(offensive["team_id"])

    # Key on the scoring team and the lineup grouping. Every player in a group
    # carries the same figure, so the dict collapses those duplicates, while
    # distinct groups from a mid-possession substitution are kept apart.
    scored: dict[tuple[int, str, str], int] = {}
    for row in stats:
        if row["stat_key"] == _OPPONENT_POINTS_KEY:
            key = (
                int(row["opponent_team_id"]),
                str(row["lineup_id"]),
                str(row["opponent_lineup_id"]),
            )
            scored[key] = int(row["stat_value"])

    return {
        "offense_team_id": offense_team,
        "defense_team_id": int(offensive["opponent_team_id"]),
        "offense_lineup": str(offensive["lineup_id"]),
        "defense_lineup": str(offensive["opponent_lineup_id"]),
        "points": sum(value for (team, _, _), value in scored.items() if team == offense_team),
        "opponent_points": sum(
            value for (team, _, _), value in scored.items() if team != offense_team
        ),
    }


def game_stints(game_id: str) -> pd.DataFrame:
    """Return one row per lineup matchup for a single game.

    Args:
        game_id: NBA game id.

    Returns:
        A frame with the columns named by :data:`STINT_COLUMNS`. Empty with
        those columns when no possession in the game counted, which keeps
        callers from having to special-case the empty result.

    Raises:
        MissingPlayByPlayError: If the game has not been downloaded.
    """
    rows = [row for row in map(_possession_row, load_possessions(game_id)) if row is not None]
    if not rows:
        return pd.DataFrame(columns=list(STINT_COLUMNS))

    frame = pd.DataFrame(rows)
    frame["possessions"] = 1
    grouped = (
        frame.groupby(
            ["offense_team_id", "defense_team_id", "offense_lineup", "defense_lineup"],
            as_index=False,
        )[["possessions", "points", "opponent_points"]]
        .sum()
        .assign(game_id=game_id)
    )
    return grouped[list(STINT_COLUMNS)]


def reconcile_points(game_id: str, reference: dict[int, int]) -> PointsReconciliation:
    """Compare points summed from possessions against a reference score.

    A team's total is what it scored on its own possessions plus what it scored
    during the opponent's, the second being technical and away-from-play free
    throws. Leaving the second term out produces totals that are right in
    aggregate and wrong per team.

    Args:
        game_id: NBA game id.
        reference: Final score per team id, from an independent source such as
            the game detail file or a box score table.

    Returns:
        A :class:`PointsReconciliation` recording both totals.

    Raises:
        MissingPlayByPlayError: If the game has not been downloaded.
    """
    stints = game_stints(game_id)
    return PointsReconciliation(
        game_id=game_id,
        derived=points_by_team(stints),
        reference=dict(reference),
    )


def points_by_team(stints: pd.DataFrame) -> dict[int, int]:
    """Return each team's total points from a stint frame.

    Args:
        stints: A stint frame carrying both point columns.

    Returns:
        Points per team id, counting both what a team scored on offence and
        what it scored while defending.
    """
    if stints.empty:
        return {}
    on_offense = stints.groupby("offense_team_id")["points"].sum()
    while_defending = stints.groupby("defense_team_id")["opponent_points"].sum()
    totals = on_offense.add(while_defending, fill_value=0)
    return {int(team): int(total) for team, total in zip(totals.index, totals, strict=True)}


def has_valid_lineups(frame: pd.DataFrame) -> pd.Series:
    """Return a mask marking rows whose two lineups each name five players.

    A lineup with the wrong count means the substitution walk lost track, and
    such a row cannot go into the design matrix: the ridge solver would place
    a player on the floor who was not, or omit one who was.

    Args:
        frame: A stint frame carrying ``offense_lineup`` and ``defense_lineup``.

    Returns:
        A boolean Series aligned to ``frame``.
    """

    def five(column: str) -> pd.Series:
        counts = frame[column].str.count(LINEUP_SEPARATOR) + 1
        return counts.eq(PLAYERS_PER_LINEUP)

    return five("offense_lineup") & five("defense_lineup")


@dataclass(frozen=True)
class SeasonStints:
    """Stints for a whole season, with the games that could not be parsed.

    Attributes:
        season: Season start year.
        stints: Concatenated stint rows across every game that parsed.
        games_parsed: How many games contributed rows.
        failures: ``(game_id, reason)`` for each game that raised. Kept rather
            than dropped because a parse failure removes real possessions from
            the fit, and a rate that climbs between seasons is a signal about
            the upstream feed rather than noise to be ignored.
    """

    season: int
    stints: pd.DataFrame
    games_parsed: int
    failures: tuple[tuple[str, str], ...]

    @property
    def possessions(self) -> int:
        """Total possessions across every parsed game."""
        if self.stints.empty:
            return 0
        return int(self.stints["possessions"].sum())

    def summary(self) -> str:
        """Return a one-line description suitable for a log or a CLI."""
        line = (
            f"season {self.season}: {self.games_parsed:,} games, "
            f"{len(self.stints):,} stints, {self.possessions:,} possessions"
        )
        if self.failures:
            line += f", {len(self.failures)} games failed to parse"
        return line


def stints_path(season: int) -> Path:
    """Return the cache path for one season's extracted stints."""
    return stage_dir("interim", create=True) / f"stints_{season}.parquet"


def season_stints(
    season: int,
    *,
    game_ids: Sequence[str] | None = None,
    on_progress: Callable[[str, str | None], None] | None = None,
) -> SeasonStints:
    """Extract stints for every downloaded game of a season.

    A game that raises is recorded and skipped rather than aborting the run.
    Parsing a season takes minutes and a single malformed game should not cost
    the other twelve hundred.

    Args:
        season: Season start year.
        game_ids: Games to parse. Defaults to the season's full regular-season
            schedule, skipping any not yet downloaded.
        on_progress: Called with ``(game_id, error)`` after each game, where
            ``error`` is ``None`` on success.

    Returns:
        A :class:`SeasonStints` holding the rows and the failures.
    """
    if game_ids is None:
        game_ids = [gid for gid in season_game_ids(season) if game_path(gid).exists()]

    frames: list[pd.DataFrame] = []
    failures: list[tuple[str, str]] = []
    for game_id in game_ids:
        try:
            frame = game_stints(game_id)
        except Exception as exc:  # any parse failure is recorded, not raised
            reason = f"{type(exc).__name__}: {exc}"
            failures.append((game_id, reason))
            if on_progress is not None:
                on_progress(game_id, reason)
            continue
        if not frame.empty:
            frames.append(frame)
        if on_progress is not None:
            on_progress(game_id, None)

    stints = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=list(STINT_COLUMNS))
    )
    return SeasonStints(
        season=season,
        stints=stints,
        games_parsed=len(frames),
        failures=tuple(failures),
    )


def write_season_stints(result: SeasonStints) -> Path:
    """Write a season's stints to the interim stage as Parquet.

    Args:
        result: The extraction to persist.

    Returns:
        Path written.
    """
    target = stints_path(result.season)
    result.stints.to_parquet(target, index=False)
    return target


def read_season_stints(season: int) -> pd.DataFrame:
    """Read a season's cached stints.

    Args:
        season: Season start year.

    Returns:
        The stint frame.

    Raises:
        FileNotFoundError: If the season has not been extracted yet.
    """
    target = stints_path(season)
    if not target.exists():
        raise FileNotFoundError(
            f"no extracted stints for {season}; expected {target}. Run the extraction first."
        )
    return pd.read_parquet(target)


def possessions_by_player(stints: pd.DataFrame) -> pd.Series:
    """Return how many possessions each player was on the floor for.

    Counts a possession once for every player in either lineup, so the total
    across players is ten times the possession count. Used to restrict
    comparisons and reports to players with enough evidence behind their
    rating, since a ridge estimate for a player with two hundred possessions is
    mostly the prior.

    Args:
        stints: A stint frame.

    Returns:
        A Series indexed by player id, sorted descending, named
        ``possessions``.
    """
    if stints.empty:
        return pd.Series(dtype="float64", name="possessions")

    counts: dict[int, float] = {}
    for column in ("offense_lineup", "defense_lineup"):
        for lineup, possessions in zip(stints[column], stints["possessions"], strict=True):
            for part in str(lineup).split(LINEUP_SEPARATOR):
                counts[int(part)] = counts.get(int(part), 0.0) + float(possessions)

    series = pd.Series(counts, name="possessions").sort_values(ascending=False)
    series.index.name = "player_id"
    return series
