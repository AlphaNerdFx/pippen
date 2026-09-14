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

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from pippen.rapm.pbp_source import game_path

if TYPE_CHECKING:  # pragma: no cover - import used for typing only
    from pathlib import Path

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
    return list(game.possessions.items)


def _possession_row(possession: Any) -> dict[str, Any] | None:
    """Reduce one possession to the fields a stint needs, or None if it does not count.

    Args:
        possession: A ``pbpstats`` possession.

    Returns:
        A mapping with the offensive and defensive team ids, both lineup ids
        and the points scored, or ``None`` when the possession carries no
        ``OffPoss`` statistic and therefore is not a counted possession.
    """
    stats = possession.possession_stats
    offensive = next((row for row in stats if row["stat_key"] == _OFF_POSS_KEY), None)
    if offensive is None:
        return None

    scored = next((row for row in stats if row["stat_key"] == _OPPONENT_POINTS_KEY), None)
    return {
        "offense_team_id": int(offensive["team_id"]),
        "defense_team_id": int(offensive["opponent_team_id"]),
        "offense_lineup": str(offensive["lineup_id"]),
        "defense_lineup": str(offensive["opponent_lineup_id"]),
        "points": int(scored["stat_value"]) if scored is not None else 0,
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
        )[["possessions", "points"]]
        .sum()
        .assign(game_id=game_id)
    )
    return grouped[list(STINT_COLUMNS)]


def reconcile_points(game_id: str, reference: dict[int, int]) -> PointsReconciliation:
    """Compare points summed from possessions against a reference score.

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
    totals = stints.groupby("offense_team_id")["points"].sum()
    derived = {int(team): int(total) for team, total in zip(totals.index, totals, strict=True)}
    return PointsReconciliation(game_id=game_id, derived=derived, reference=dict(reference))


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
