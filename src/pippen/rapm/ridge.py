"""The regularised solve that turns the design matrix into player ratings.

Why regularisation is not optional here
---------------------------------------
Teammates share the floor almost constantly. Two starters on the same team may
appear together in nine tenths of their possessions, and from the scoreboard
alone there is no way to tell which of them caused the margin. In regression
terms their columns are nearly collinear, and ordinary least squares responds
by producing enormous coefficients of opposite sign that cancel. The fit looks
fine and the individual numbers are nonsense, swinging wildly between samples.
That unregularised version is APM, which this project's own research rates at
50 to 60 percent reliability.

Ridge regression adds a penalty on the sum of squared coefficients, which
shrinks every rating toward zero unless the data insists otherwise. Read as
statistics rather than as optimisation, the penalty is a prior: every player is
league-average until his possessions prove he is not. The trade is a little
bias for a large reduction in variance, and it is what turns APM into RAPM.

The penalty descends from Tikhonov regularisation, published in 1943 for
ill-posed inverse problems, and arrived in statistics as ridge regression in
Hoerl and Kennard's 1970 paper. The same idea now appears as weight decay in
neural network training, which is why an L2 penalty is the first thing reached
for whenever a model has more parameters than the data can separate.

Choosing the penalty
--------------------
Lambda is chosen by cross-validation rather than by hand, and the folds split
on games rather than on stint rows. Stints from one game share opponents,
officials, pace and rest, so scattering them across folds lets the model see
part of a game it is being tested on. That leaks, and the leak biases toward a
smaller penalty, which is exactly the direction that makes the multicollinearity
problem worse.

Uncertainty
-----------
Standard errors come from a cluster bootstrap that resamples whole games. The
same correlation that forces grouped folds also means a bootstrap over
individual stints would treat correlated rows as independent evidence and
report intervals that are too narrow. Resampling games keeps each game's
internal correlation intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, TypeAlias

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from pippen.rapm.design import DesignMatrix

FloatArray: TypeAlias = np.ndarray[Any, np.dtype[np.float64]]
BoolArray: TypeAlias = np.ndarray[Any, np.dtype[np.bool_]]
IntArray: TypeAlias = np.ndarray[Any, np.dtype[np.intp]]

#: Penalties searched by default. Spread over four orders of magnitude on a log
#: scale, because the useful value depends on how many possessions are in the
#: window and a linear grid would waste most of its points in the wrong region.
DEFAULT_ALPHAS: Final = (100.0, 300.0, 1000.0, 3000.0, 10000.0, 30000.0, 100000.0)

#: Folds used when selecting the penalty.
DEFAULT_FOLDS: Final = 5

#: Resamples drawn for the cluster bootstrap.
DEFAULT_RESAMPLES: Final = 200


@dataclass(frozen=True)
class RidgeFit:
    """A fitted ridge model and the penalty that produced it.

    Attributes:
        alpha: The ridge penalty used.
        intercept: Fitted league-average points per 100 possessions.
        coefficients: Raw coefficient vector, offensive terms first.
        player_ids: Player ids in column order.
    """

    alpha: float
    intercept: float
    coefficients: FloatArray
    player_ids: tuple[int, ...]

    def ratings(self) -> pd.DataFrame:
        """Return one row per player with offensive, defensive and total impact.

        Returns:
            A frame indexed by position with columns ``player_id``,
            ``offensive``, ``defensive`` and ``total``, sorted by total impact
            descending. Both components are signed so that higher is better,
            so ``total`` is their sum. See
            :mod:`pippen.rapm.design` for why the defensive column carries
            that sign.
        """
        n = len(self.player_ids)
        offensive = self.coefficients[:n]
        defensive = self.coefficients[n:]
        return (
            pd.DataFrame(
                {
                    "player_id": self.player_ids,
                    "offensive": offensive,
                    "defensive": defensive,
                    "total": offensive + defensive,
                }
            )
            .sort_values("total", ascending=False)
            .reset_index(drop=True)
        )


def fit_ridge(design: DesignMatrix, alpha: float) -> RidgeFit:
    """Fit a possession-weighted ridge regression at one penalty.

    Args:
        design: The regression problem.
        alpha: Ridge penalty. Larger shrinks ratings harder toward zero.

    Returns:
        The fitted model.

    Raises:
        ValueError: If ``alpha`` is not positive. A zero penalty is ordinary
            least squares, which this module exists to avoid, so it is refused
            rather than silently allowed.
    """
    if alpha <= 0:
        raise ValueError(
            f"alpha must be positive, got {alpha!r}; a zero penalty is unregularised "
            f"APM, whose coefficients are unstable under multicollinearity"
        )
    model = Ridge(alpha=alpha, fit_intercept=True, solver="sparse_cg")
    model.fit(design.matrix, design.target, sample_weight=design.weights)
    return RidgeFit(
        alpha=float(alpha),
        intercept=float(model.intercept_),
        coefficients=np.asarray(model.coef_, dtype=np.float64),
        player_ids=design.player_ids,
    )


def _weighted_mse(actual: FloatArray, predicted: FloatArray, weights: FloatArray) -> float:
    """Return the possession-weighted mean squared error."""
    return float(np.average((actual - predicted) ** 2, weights=weights))


def _game_folds(groups: np.ndarray[Any, np.dtype[Any]], folds: int, seed: int) -> list[BoolArray]:
    """Split distinct games into ``folds`` roughly equal held-out sets.

    Args:
        groups: Game id per row.
        folds: Number of folds.
        seed: Seed for the shuffle, so a run is reproducible.

    Returns:
        A list of boolean masks, one per fold, each marking the rows held out.
    """
    games = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(games)
    chunks = np.array_split(games, folds)
    return [np.isin(groups, chunk) for chunk in chunks]


def select_alpha(
    design: DesignMatrix,
    *,
    alphas: tuple[float, ...] = DEFAULT_ALPHAS,
    folds: int = DEFAULT_FOLDS,
    seed: int = 20260910,
) -> tuple[float, pd.DataFrame]:
    """Choose the ridge penalty by cross-validation over held-out games.

    Args:
        design: The regression problem.
        alphas: Penalties to try.
        folds: Number of cross-validation folds. Games, not rows, are split.
        seed: Seed for the fold shuffle.

    Returns:
        A pair of the best penalty and a frame recording the weighted mean
        squared error for every penalty, so the choice can be inspected rather
        than trusted.

    Raises:
        ValueError: If fewer distinct games are present than folds requested.
    """
    n_games = len(np.unique(design.groups))
    if n_games < folds:
        raise ValueError(
            f"cannot build {folds} folds from {n_games} distinct games; "
            f"pass a smaller folds= or fit a longer window"
        )

    masks = _game_folds(design.groups, folds, seed)
    records: list[dict[str, float]] = []
    for alpha in alphas:
        errors: list[float] = []
        for held_out in masks:
            train = ~held_out
            model = Ridge(alpha=alpha, fit_intercept=True, solver="sparse_cg")
            model.fit(
                design.matrix[train],
                design.target[train],
                sample_weight=design.weights[train],
            )
            predicted = np.asarray(model.predict(design.matrix[held_out]), dtype=np.float64)
            errors.append(
                _weighted_mse(design.target[held_out], predicted, design.weights[held_out])
            )
        records.append({"alpha": float(alpha), "weighted_mse": float(np.mean(errors))})

    table = pd.DataFrame(records)
    best = float(table["alpha"].to_numpy()[int(table["weighted_mse"].to_numpy().argmin())])
    return best, table


def bootstrap_standard_errors(
    design: DesignMatrix,
    alpha: float,
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 20260910,
) -> pd.DataFrame:
    """Estimate standard errors by resampling whole games.

    Draws ``resamples`` bootstrap samples, each drawing games with replacement
    until the original game count is reached, refits at the given penalty, and
    takes the standard deviation of each coefficient across the samples.

    Args:
        design: The regression problem.
        alpha: Penalty to hold fixed across resamples. Held fixed rather than
            reselected per resample, because reselecting would fold the
            penalty's own sampling variation into the standard error and cost
            a full cross-validation per resample.
        resamples: Number of bootstrap samples.
        seed: Seed for the resampling.

    Returns:
        A frame with ``player_id``, ``offensive_se``, ``defensive_se`` and
        ``total_se``.
    """
    games = np.unique(design.groups)
    index_of_game = {game: np.flatnonzero(design.groups == game) for game in games}
    rng = np.random.default_rng(seed)

    n = len(design.player_ids)
    offensive = np.empty((resamples, n), dtype=np.float64)
    defensive = np.empty((resamples, n), dtype=np.float64)
    totals = np.empty((resamples, n), dtype=np.float64)

    for draw in range(resamples):
        drawn = rng.choice(games, size=len(games), replace=True)
        rows = np.concatenate([index_of_game[game] for game in drawn])
        model = Ridge(alpha=alpha, fit_intercept=True, solver="sparse_cg")
        model.fit(
            design.matrix[rows],
            design.target[rows],
            sample_weight=design.weights[rows],
        )
        coefficients = np.asarray(model.coef_, dtype=np.float64)
        offensive[draw] = coefficients[:n]
        defensive[draw] = coefficients[n:]
        totals[draw] = coefficients[:n] + coefficients[n:]

    return pd.DataFrame(
        {
            "player_id": design.player_ids,
            "offensive_se": offensive.std(axis=0, ddof=1),
            "defensive_se": defensive.std(axis=0, ddof=1),
            "total_se": totals.std(axis=0, ddof=1),
        }
    )


def solve(
    design: DesignMatrix,
    *,
    alphas: tuple[float, ...] = DEFAULT_ALPHAS,
    folds: int = DEFAULT_FOLDS,
    seed: int = 20260910,
) -> tuple[RidgeFit, pd.DataFrame]:
    """Select a penalty, then fit at it.

    Args:
        design: The regression problem.
        alphas: Penalties to search.
        folds: Cross-validation folds.
        seed: Seed for the fold shuffle.

    Returns:
        The fitted model and the cross-validation table behind the choice.
    """
    alpha, table = select_alpha(design, alphas=alphas, folds=folds, seed=seed)
    return fit_ridge(design, alpha), table
