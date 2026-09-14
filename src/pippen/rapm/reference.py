"""Loading an externally built stint dataset, for validating this project's own.

Why an external stint file rather than a published rating
---------------------------------------------------------
Phase 2's gate asks for agreement with a published multi-season RAPM. Those
exist as web tables without a stated licence or a download, which makes them
awkward to depend on and impossible to reproduce from a clean checkout.

A stint dataset built by someone else is the better comparison anyway. Feeding
it through *this* project's solver holds the regression constant and varies only
the part that is actually risky: reconstructing who was on the floor. If two
independent walks of two different feeds agree on the ratings, the extraction is
sound. If a published rating disagreed instead, the cause could be their ridge
penalty, their possession definition, their minutes filter or their prior, and
there would be no way to tell which.

The reference used here is the SCORE Sports Data Repository's 2022-23 stint
file, built from hoopR, which is ESPN-sourced. This project's own stints come
from data.nba.com. Different organisations, different feeds, different
substitution walks, the same games.

Licence position
----------------
The reference states no licence, so it is treated exactly as
Basketball-Reference is: local validation only, never redistributed and never
part of a published artifact. It lives under ``data/external/``, which is
outside git like the rest of ``data/``.

Format differences
------------------
The reference records one row per stint with a home lineup, an away lineup and
both point totals. This project records one row per lineup matchup with an
offensive side. Converting means splitting each reference stint into two rows,
one per team on offence.

Its ``n_pos`` counts the stint's possessions once, shared by both teams, so each
converted row takes half. That is the usual approximation: over a stint the two
teams alternate, so their possession counts differ by at most one. The halves
are only used as regression weights, where what matters is that a long stint
outweighs a short one in proportion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from pippen.paths import stage_dir
from pippen.rapm.possessions import STINT_COLUMNS

#: Separator the reference uses between player ids inside a lineup.
REFERENCE_SEPARATOR: Final = "_"

#: Separator this project uses.
PROJECT_SEPARATOR: Final = "-"

#: Columns the reference file must carry.
REQUIRED_COLUMNS: Final = (
    "game_id",
    "home_lineup",
    "away_lineup",
    "n_pos",
    "home_points",
    "away_points",
)

#: Placeholder team ids. The reference does not record which franchise is which,
#: and RAPM does not use team identity, only the lineups. These keep the schema
#: aligned without inventing information.
HOME_TEAM_ID: Final = 1
AWAY_TEAM_ID: Final = 2


class ReferenceFormatError(ValueError):
    """The reference file does not have the columns this loader expects."""


def external_dir(*, create: bool = False) -> Path:
    """Return the directory holding validation-only third-party data."""
    root = stage_dir("raw", create=create).parent / "external"
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def default_reference_path() -> Path:
    """Return the expected location of the SCORE 2022-23 stint file."""
    return external_dir() / "nba_2223_season_stints.csv"


def _to_project_lineup(lineup: str) -> str:
    """Rewrite a reference lineup id into this project's separator."""
    return lineup.replace(REFERENCE_SEPARATOR, PROJECT_SEPARATOR)


def load_reference_stints(path: Path | None = None) -> pd.DataFrame:
    """Read an external stint file and convert it to this project's schema.

    Args:
        path: File to read. Defaults to :func:`default_reference_path`.

    Returns:
        A frame with the columns named by
        :data:`~pippen.rapm.possessions.STINT_COLUMNS`, two rows per reference
        stint. ``opponent_points`` is zero throughout: the reference does not
        separate technical free throws from the rest, so the column exists only
        to keep the schema aligned.

    Raises:
        FileNotFoundError: If the file is not present.
        ReferenceFormatError: If the file lacks an expected column.
    """
    path = path or default_reference_path()
    if not path.exists():
        raise FileNotFoundError(
            f"no reference stint file at {path}. Download it from the SCORE "
            f"Sports Data Repository; it is validation-only and never published."
        )

    raw = pd.read_csv(path, dtype={"game_id": str})
    missing = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        raise ReferenceFormatError(f"reference file {path.name} is missing columns: {missing}")

    home = _to_project_lineup_frame(raw, home_on_offense=True)
    away = _to_project_lineup_frame(raw, home_on_offense=False)
    return pd.concat([home, away], ignore_index=True)[list(STINT_COLUMNS)]


def _to_project_lineup_frame(raw: pd.DataFrame, *, home_on_offense: bool) -> pd.DataFrame:
    """Build the rows for one team being on offence."""
    offense_lineup = "home_lineup" if home_on_offense else "away_lineup"
    defense_lineup = "away_lineup" if home_on_offense else "home_lineup"
    points = "home_points" if home_on_offense else "away_points"
    return pd.DataFrame(
        {
            "game_id": raw["game_id"],
            "offense_team_id": HOME_TEAM_ID if home_on_offense else AWAY_TEAM_ID,
            "defense_team_id": AWAY_TEAM_ID if home_on_offense else HOME_TEAM_ID,
            "offense_lineup": raw[offense_lineup].map(_to_project_lineup),
            "defense_lineup": raw[defense_lineup].map(_to_project_lineup),
            # Halved because n_pos counts the stint once for both teams.
            "possessions": raw["n_pos"] / 2.0,
            "points": raw[points],
            "opponent_points": 0,
        }
    )


@dataclass(frozen=True)
class GateResult:
    """Agreement between this project's ratings and an independent build.

    Attributes:
        spearman: Rank correlation across the players both sides rate.
        pearson: Linear correlation across the same players.
        players_compared: How many players cleared the possession floor and
            appear in both sets.
        possession_floor: The floor applied.
        threshold: The Spearman correlation the gate requires.
        mean_absolute_difference: Average gap in points per 100 possessions,
            which says whether the two agree on magnitude and not only on order.
    """

    spearman: float
    pearson: float
    players_compared: int
    possession_floor: float
    threshold: float
    mean_absolute_difference: float

    @property
    def passed(self) -> bool:
        """True when the rank correlation clears the threshold."""
        return self.spearman >= self.threshold

    def describe(self) -> str:
        """Return a one-line verdict suitable for a log or a CLI."""
        verdict = "PASS" if self.passed else "FAIL"
        return (
            f"{verdict}: Spearman {self.spearman:.3f} against a threshold of "
            f"{self.threshold:.2f}, Pearson {self.pearson:.3f}, "
            f"{self.players_compared} players above {self.possession_floor:,.0f} "
            f"possessions, mean absolute gap {self.mean_absolute_difference:.2f} per 100"
        )


def compare_ratings(
    project: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    project_possessions: pd.Series,
    reference_possessions: pd.Series,
    possession_floor: float = 1000.0,
    threshold: float = 0.85,
    column: str = "total",
) -> GateResult:
    """Correlate two sets of player ratings over the players both cover.

    Rank correlation is the headline because the two builds need not share a
    scale: a different ridge penalty shrinks every rating toward zero by a
    different amount without changing who is ahead of whom. The linear
    correlation and the mean absolute gap are reported alongside so a scale
    disagreement is visible rather than hidden.

    Args:
        project: Ratings from this project, with ``player_id`` and ``column``.
        reference: Ratings from the independent build, same shape.
        project_possessions: Possessions per player behind ``project``.
        reference_possessions: Possessions per player behind ``reference``.
        possession_floor: Players below this in either build are excluded. A
            ridge estimate for a player with few possessions is mostly the
            prior, so including them would measure agreement between two priors.
        threshold: Spearman correlation the gate requires.
        column: Which rating to compare.

    Returns:
        A :class:`GateResult`.

    Raises:
        ValueError: If fewer than two players survive, which makes a
            correlation undefined rather than merely unreliable.
    """
    left = project.set_index("player_id")[column]
    right = reference.set_index("player_id")[column]

    eligible = (
        set(project_possessions[project_possessions >= possession_floor].index)
        & set(reference_possessions[reference_possessions >= possession_floor].index)
        & set(left.index)
        & set(right.index)
    )
    if len(eligible) < 2:
        raise ValueError(
            f"only {len(eligible)} players cleared {possession_floor:,.0f} possessions in "
            f"both builds; a correlation needs at least two"
        )

    shared = sorted(eligible)
    ours = left.loc[shared]
    theirs = right.loc[shared]

    return GateResult(
        spearman=float(ours.corr(theirs, method="spearman")),
        pearson=float(ours.corr(theirs, method="pearson")),
        players_compared=len(shared),
        possession_floor=possession_floor,
        threshold=threshold,
        mean_absolute_difference=float((ours - theirs).abs().mean()),
    )
