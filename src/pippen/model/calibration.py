"""Are the model's credible intervals the width they claim to be?

Why this check exists
---------------------
The project's output is a rating with an interval, and an interval is a claim:
a 90 percent interval says the truth falls inside it 90 percent of the time. A
model can rank players perfectly and still make that claim falsely, by being
systematically over- or under-confident. Nothing in the fit itself checks it,
because the fit is what makes the claim.

Phase 3 requires roughly 90 percent of held-out values inside the 90 percent
interval before the model is considered done.

What is held out, and why it is not the rating
----------------------------------------------
The obvious test cannot be run. The latent quantity has no observed value to
compare an interval against, ever, which is what makes it latent. Checking
coverage of the rating's interval against the truth is not merely hard here, it
is undefined.

What is observable is the metrics. So a fraction of the *observed metric
values* is hidden, the model is fitted to the rest, and each hidden value is
compared against the interval the fitted model predicts for it. That is a
posterior predictive check, and it tests the same machinery: if the loadings,
the residual scales or the latent values were over-confident, the predictive
intervals built from them would be too narrow and coverage would fall below
nominal.

This is weaker than checking the rating directly, and it is the strongest check
available. Saying so is better than reporting a number that sounds stronger
than it is.

Reading the result
------------------
Coverage below nominal means over-confidence: intervals are too narrow and the
model claims more precision than it has. Coverage above nominal means the
opposite, which is safer but wasteful, since a needlessly wide interval hides
real differences between players.

Coverage is also reported per metric, because a model can be well calibrated on
average while being badly wrong on one column, and an average would hide it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from pippen.model.dataset import FusionDataset
from pippen.model.fusion import fit_fusion

#: Share of observed values hidden from the fit.
DEFAULT_HOLD_OUT: Final = 0.15

#: Interval width whose coverage is checked.
DEFAULT_NOMINAL: Final = 0.90

#: How far from nominal coverage may drift and still count as calibrated.
DEFAULT_TOLERANCE: Final = 0.05

#: Seed, matching the project-wide default.
DEFAULT_SEED: Final = 20260910


class NotEnoughDataError(ValueError):
    """Too few observed values to hold any out."""


@dataclass(frozen=True)
class CalibrationResult:
    """Observed coverage against the width the intervals claim.

    Attributes:
        nominal: Interval width checked, such as 0.90.
        observed: Share of held-out values that fell inside.
        held_out: How many values were hidden and checked.
        tolerance: How far coverage may drift and still pass.
        by_metric: Coverage per metric, so a single badly calibrated column is
            visible rather than averaged away.
        median_width: Median width of the predictive intervals, in standard
            deviations, which says whether coverage was bought with vagueness.
    """

    nominal: float
    observed: float
    held_out: int
    tolerance: float
    by_metric: pd.DataFrame
    median_width: float

    @property
    def calibrated(self) -> bool:
        """True when observed coverage is within tolerance of nominal."""
        return abs(self.observed - self.nominal) <= self.tolerance

    @property
    def direction(self) -> str:
        """Whether the intervals are too narrow, too wide, or about right."""
        if self.calibrated:
            return "calibrated"
        return "over-confident" if self.observed < self.nominal else "under-confident"

    def describe(self) -> str:
        """Return a one-line verdict naming the direction of any miss."""
        return (
            f"{self.direction}: {self.observed:.1%} of {self.held_out} held-out values "
            f"inside the {self.nominal:.0%} interval, median width "
            f"{self.median_width:.2f} sd"
        )


def check_calibration(
    dataset: FusionDataset,
    reliability: pd.Series,
    *,
    hold_out: float = DEFAULT_HOLD_OUT,
    nominal: float = DEFAULT_NOMINAL,
    tolerance: float = DEFAULT_TOLERANCE,
    seed: int = DEFAULT_SEED,
    **fit_kwargs: object,
) -> CalibrationResult:
    """Hide some observed values, refit, and see how often the intervals contain them.

    Args:
        dataset: The assembled player-by-metric table.
        reliability: Measured reliability per metric.
        hold_out: Share of observed values to hide.
        nominal: Interval width to check, such as 0.90.
        tolerance: How far observed coverage may drift and still pass.
        seed: Seed for choosing which values to hide.
        **fit_kwargs: Passed through to :func:`~pippen.model.fusion.fit_fusion`.

    Returns:
        A :class:`CalibrationResult`.

    Raises:
        NotEnoughDataError: If hiding that share would leave fewer than ten
            values to check, which makes a coverage rate meaningless.
    """
    values = dataset.values
    observed = values.notna().to_numpy()
    rng = np.random.default_rng(seed)
    hidden = observed & (rng.random(values.shape) < hold_out)

    if hidden.sum() < 10:
        raise NotEnoughDataError(
            f"hiding {hold_out:.0%} leaves only {int(hidden.sum())} values to check; "
            f"a coverage rate needs at least ten"
        )

    masked = values.mask(pd.DataFrame(hidden, index=values.index, columns=values.columns))
    reduced = FusionDataset(
        values=masked,
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=dataset.nba_seasons,
        anchor=dataset.anchor,
    )

    fit = fit_fusion(reduced, reliability, seed=seed, keep_draws=True, **fit_kwargs)  # type: ignore[arg-type]
    if fit.draws is None:  # pragma: no cover - keep_draws is passed above
        raise RuntimeError("the fit returned no draws")

    intercept = fit.draws["intercept"]
    loadings = fit.draws["loading_matrix"]
    factors = fit.draws["factors_by_player"]
    scale = fit.draws["scale"]

    # Posterior predictive mean for every draw, player and metric. The
    # predictive spread is the parameter uncertainty and the residual scale
    # together, so a draw of the residual is added rather than only the mean
    # being used; an interval on the mean alone would be far too narrow.
    means = intercept[:, None, :] + np.einsum("dpk,dmk->dpm", factors, loadings)
    noise = rng.normal(0.0, 1.0, means.shape) * scale[:, None, :]
    predictive = means + noise

    tail = (1.0 - nominal) / 2.0
    lower = np.quantile(predictive, tail, axis=0)
    upper = np.quantile(predictive, 1.0 - tail, axis=0)

    truth = values.to_numpy()
    inside = (truth >= lower) & (truth <= upper)
    widths = upper - lower

    rows = []
    for index, metric in enumerate(values.columns):
        column = hidden[:, index]
        if column.sum() == 0:
            continue
        rows.append(
            {
                "metric": metric,
                "held_out": int(column.sum()),
                "coverage": float(inside[column, index].mean()),
                "median_width": float(np.median(widths[column, index])),
            }
        )

    return CalibrationResult(
        nominal=nominal,
        observed=float(inside[hidden].mean()),
        held_out=int(hidden.sum()),
        tolerance=tolerance,
        by_metric=pd.DataFrame(rows).sort_values("coverage").reset_index(drop=True),
        median_width=float(np.median(widths[hidden])),
    )
