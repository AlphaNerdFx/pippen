"""The sparse design matrix that turns stints into a regression problem.

The shape of the problem
------------------------
One row per stint, one column per player per side of the ball. A row says
"these five were on offense, those five on defense", and the target says how
many points per hundred possessions the offense scored. Fitting that gives each
player two coefficients: what they add on offense and what they prevent on
defense.

Why it has to be sparse
-----------------------
A season has roughly 30,000 stint rows and about 550 players, so 1,100 columns
once each player appears on both sides. Stored densely that is 33 million
floats, about 260 MB, and every one of them is zero except ten per row. The
matrix is 99.1 percent zeros by construction, because only ten of the league's
players are on the floor at a time.

Sparse storage keeps only the non-zeros and their positions, so the same matrix
costs a few megabytes. This matters more for the solve than for the memory: a
dense matrix multiply touches every zero, while a sparse one visits only the
ten real entries per row. The idea is older than the machines it runs on,
coming out of 1960s structural engineering and circuit simulation, where the
matrices describing which beams meet which joints had the same property. It is
the same reason recommender systems and finite-element solvers use it now.

``scipy.sparse`` builds the matrix in COO form, a plain list of
``(row, column, value)`` triples, because appending to that is cheap. It is
then converted to CSR, which groups entries by row so a matrix-vector product
can walk one row at a time. Building in COO and solving in CSR is the standard
pairing and the conversion is a single pass.

Sign convention
---------------
Offensive players enter as ``+1`` and defensive players as ``-1``. With the
target being points scored by the offense, a positive offensive coefficient
means a player raises his team's scoring and a positive defensive coefficient
means he lowers the opponent's. Both are therefore "higher is better", and a
player's total impact is the sum of the two rather than a difference, which
removes a sign error that is easy to make downstream and hard to notice.

Weighting
---------
Each row is weighted by its possession count. A stint of 40 possessions carries
forty times the evidence of a single-possession one, and an unweighted fit
would treat them alike. Weighted least squares is the correct handling because
the variance of a rate estimated over ``n`` possessions falls as ``1/n``, which
makes the weights inverse-variance weights, the same principle the fusion model
applies across metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, TypeAlias

import numpy as np
import pandas as pd
from scipy import sparse

from pippen.rapm.possessions import LINEUP_SEPARATOR, has_valid_lineups

#: A one-dimensional float array. Named so the dataclass fields below stay
#: readable under mypy's strict requirement that ndarray carry type arguments.
FloatArray: TypeAlias = np.ndarray[Any, np.dtype[np.float64]]

#: Points are quoted per this many possessions, the convention in every public
#: plus-minus metric, so the numbers are comparable with published RAPM.
POSSESSIONS_PER_RATING: Final = 100

#: Value placed in the matrix for an offensive and a defensive player.
OFFENSE_SIGN: Final = 1.0
DEFENSE_SIGN: Final = -1.0


class EmptyDesignError(ValueError):
    """No usable stints survived filtering, so there is nothing to fit."""


@dataclass(frozen=True)
class DesignMatrix:
    """A regression problem built from stints.

    Attributes:
        matrix: The CSR design matrix, one row per stint and two columns per
            player.
        target: Points per :data:`POSSESSIONS_PER_RATING` possessions for each
            row.
        weights: Possessions behind each row, used as regression weights.
        player_ids: Player ids in column order. Column ``i`` is the offensive
            term for ``player_ids[i]``; column ``len(player_ids) + i`` is that
            player's defensive term.
        groups: Game id behind each row. Stints from one game share opponents,
            officials and pace, so they are not independent observations.
            Cross-validation splits on this rather than on rows, and the
            bootstrap resamples games rather than stints, because treating
            correlated rows as independent understates the standard errors.
        dropped_rows: Stint rows discarded because a lineup did not name five
            players. Reported rather than silently ignored, because a rising
            count means the substitution walk is losing track.
    """

    matrix: sparse.csr_matrix
    target: FloatArray
    weights: FloatArray
    player_ids: tuple[int, ...]
    groups: np.ndarray[Any, np.dtype[Any]]
    dropped_rows: int

    @property
    def n_players(self) -> int:
        """Number of distinct players, which is half the column count."""
        return len(self.player_ids)

    @property
    def n_rows(self) -> int:
        """Number of stint rows in the problem."""
        return int(self.matrix.shape[0])

    def offense_column(self, player_id: int) -> int:
        """Return the column index holding ``player_id``'s offensive term."""
        return self.player_ids.index(player_id)

    def defense_column(self, player_id: int) -> int:
        """Return the column index holding ``player_id``'s defensive term."""
        return self.n_players + self.player_ids.index(player_id)

    def describe(self) -> str:
        """Return a one-line summary of the problem's size and sparsity."""
        rows, cols = self.matrix.shape
        density = self.matrix.nnz / (rows * cols) if rows and cols else 0.0
        return (
            f"{rows:,} stints x {cols:,} columns, {self.matrix.nnz:,} non-zeros "
            f"({density:.2%} dense), {int(self.weights.sum()):,} possessions"
        )


def _split_lineup(lineup: str) -> list[int]:
    """Return the player ids named by a ``pbpstats`` lineup id."""
    return [int(part) for part in lineup.split(LINEUP_SEPARATOR)]


def build_design(stints: pd.DataFrame, *, min_possessions: int = 1) -> DesignMatrix:
    """Build the RAPM regression problem from a stint frame.

    Args:
        stints: Frame with the columns
            :data:`~pippen.rapm.possessions.STINT_COLUMNS`. Rows from many
            games and seasons can be concatenated freely, which is how
            multi-season windows are fitted.
        min_possessions: Drop stints shorter than this. The default of 1 keeps
            everything, since the possession weighting already discounts short
            stints in proportion to their evidence. Raise it only to test how
            sensitive the fit is to the long tail of one-possession rows.

    Returns:
        A :class:`DesignMatrix` ready for a weighted ridge fit.

    Raises:
        EmptyDesignError: If no rows survive filtering. Raised rather than
            returning an empty matrix because every caller would otherwise have
            to check, and a silent empty fit produces coefficients of zero that
            look like a valid answer.
    """
    usable = stints[stints["possessions"] >= min_possessions]
    valid = has_valid_lineups(usable)
    dropped = int((~valid).sum())
    usable = usable[valid]

    if usable.empty:
        raise EmptyDesignError(
            f"no stints left after filtering: {len(stints):,} rows in, "
            f"{dropped:,} dropped for malformed lineups, "
            f"{len(stints) - dropped:,} below min_possessions={min_possessions}"
        )

    offense = [_split_lineup(value) for value in usable["offense_lineup"]]
    defense = [_split_lineup(value) for value in usable["defense_lineup"]]

    player_ids = tuple(sorted({pid for lineup in offense + defense for pid in lineup}))
    column_of = {pid: index for index, pid in enumerate(player_ids)}
    n_players = len(player_ids)

    n_rows = len(usable)
    per_row = len(offense[0]) + len(defense[0]) if n_rows else 0
    rows = np.empty(n_rows * per_row, dtype=np.int32)
    cols = np.empty(n_rows * per_row, dtype=np.int32)
    values = np.empty(n_rows * per_row, dtype=np.float64)

    cursor = 0
    for row_index, (off_lineup, def_lineup) in enumerate(zip(offense, defense, strict=True)):
        for pid in off_lineup:
            rows[cursor] = row_index
            cols[cursor] = column_of[pid]
            values[cursor] = OFFENSE_SIGN
            cursor += 1
        for pid in def_lineup:
            rows[cursor] = row_index
            cols[cursor] = n_players + column_of[pid]
            values[cursor] = DEFENSE_SIGN
            cursor += 1

    matrix = sparse.coo_matrix(
        (values[:cursor], (rows[:cursor], cols[:cursor])),
        shape=(n_rows, 2 * n_players),
    ).tocsr()

    possessions = usable["possessions"].to_numpy(dtype=np.float64)
    points = usable["points"].to_numpy(dtype=np.float64)
    target = POSSESSIONS_PER_RATING * points / possessions

    return DesignMatrix(
        matrix=matrix,
        target=target,
        weights=possessions,
        player_ids=player_ids,
        groups=usable["game_id"].to_numpy(),
        dropped_rows=dropped,
    )
