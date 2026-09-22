"""Distribution drift between the shipped rating windows.

The roadmap named Evidently for this. Evidently is a good tool and it is not
installed here, because what this project needs from drift detection is two
statistics over a 5,427-row table that already sits in memory. The Population
Stability Index is a binned symmetric divergence and the Kolmogorov-Smirnov test
is in scipy, which is already a dependency. Adding a reporting framework with
its own UI stack to compute two numbers would not have earned its install.

What drifts here is the league, not a serving distribution. These ratings are
recomputed from scratch rather than predicted, so there is no training set to
grow stale against production traffic. The question this answers is narrower and
still worth asking: has the distribution of player impact moved enough between
the earliest and latest windows that a reader should be careful comparing them?
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from scipy import stats

#: Bins used for the Population Stability Index. Ten is the convention in credit
#: scoring, where PSI comes from, and it is enough resolution for 5,427 rows
#: without leaving bins so sparse that the log term explodes.
PSI_BINS: Final = 10

#: Added to every bin share so an empty bin contributes a finite term rather
#: than an infinite one. Small against a share, large against zero.
EPSILON: Final = 1e-6

#: The conventional PSI reading, from credit risk practice. Below 0.1 the
#: distributions are treated as the same population, 0.1 to 0.25 as a shift
#: worth watching, above 0.25 as a different population.
PSI_STABLE: Final = 0.10
PSI_SHIFTED: Final = 0.25


@dataclass(frozen=True)
class DriftResult:
    """How far one window's rating distribution sits from another's."""

    column: str
    reference_window: str
    comparison_window: str
    psi: float
    ks_statistic: float
    ks_p_value: float
    reference_n: int
    comparison_n: int

    @property
    def verdict(self) -> str:
        """Report the PSI band in words."""
        if self.psi < PSI_STABLE:
            return "stable"
        if self.psi < PSI_SHIFTED:
            return "watch"
        return "shifted"

    def describe(self) -> str:
        """Return one line a human can read without the class definition."""
        return (
            f"{self.column}: {self.reference_window} to {self.comparison_window}, "
            f"PSI {self.psi:.3f} ({self.verdict}), "
            f"KS {self.ks_statistic:.3f} at p={self.ks_p_value:.3g}"
        )


def population_stability_index(
    reference: pd.Series, comparison: pd.Series, *, bins: int = PSI_BINS
) -> float:
    """Return the PSI between two samples of the same quantity.

    PSI sums ``(a - b) * ln(a / b)`` over bins, where ``a`` and ``b`` are the
    share of each sample falling in a bin. It is symmetric, which is why it is
    preferred to a one-directional KL divergence when neither sample is
    privileged as the truth.

    Bin edges come from the reference sample's quantiles, so the reference is
    uniform across bins by construction and every departure is the comparison
    moving.

    Args:
        reference: The sample the bins are cut from.
        comparison: The sample measured against those bins.
        bins: Number of quantile bins.

    Returns:
        The index. Zero means identical binned distributions.

    Raises:
        ValueError: If either sample is empty.
    """
    if reference.empty or comparison.empty:
        raise ValueError("PSI needs a non-empty sample on both sides")

    edges = np.quantile(reference, np.linspace(0, 1, bins + 1))
    # Quantiles of a peaked distribution can repeat, which would give a
    # zero-width bin. Unique edges are fewer bins, which is the honest response.
    edges = np.unique(edges)
    edges[0], edges[-1] = -np.inf, np.inf

    reference_share = np.histogram(reference, bins=edges)[0] / len(reference)
    comparison_share = np.histogram(comparison, bins=edges)[0] / len(comparison)

    reference_share = reference_share + EPSILON
    comparison_share = comparison_share + EPSILON
    return float(
        np.sum((comparison_share - reference_share) * np.log(comparison_share / reference_share))
    )


def compare_windows(
    ratings: pd.DataFrame,
    *,
    column: str = "total",
    reference_end: int | None = None,
    comparison_end: int | None = None,
) -> DriftResult:
    """Compare two rating windows on one column.

    Args:
        ratings: The shipped ratings table.
        column: Which rating column to compare.
        reference_end: Window to treat as the reference. Earliest when omitted.
        comparison_end: Window to measure. Latest when omitted.

    Returns:
        The drift between them.

    Raises:
        ValueError: If a named window is not in the table.
    """
    # int() rather than the numpy scalars, so a ValueError reads
    # "available: [2018, 2024]" instead of leaking np.int64 into a user's face.
    available = [int(end) for end in sorted(ratings["window_end"].unique())]
    reference_end = available[0] if reference_end is None else reference_end
    comparison_end = available[-1] if comparison_end is None else comparison_end
    for end in (reference_end, comparison_end):
        if end not in available:
            raise ValueError(f"no window ends in {end}; available: {available}")

    reference = ratings.loc[ratings["window_end"] == reference_end, column].dropna()
    comparison = ratings.loc[ratings["window_end"] == comparison_end, column].dropna()
    ks = stats.ks_2samp(reference, comparison)

    return DriftResult(
        column=column,
        reference_window=str(reference_end),
        comparison_window=str(comparison_end),
        psi=population_stability_index(reference, comparison),
        ks_statistic=float(ks.statistic),
        ks_p_value=float(ks.pvalue),
        reference_n=len(reference),
        comparison_n=len(comparison),
    )


def report(ratings: pd.DataFrame) -> list[DriftResult]:
    """Compare the earliest window against the latest on every rating column."""
    return [compare_windows(ratings, column=name) for name in ("offensive", "defensive", "total")]


def render(results: list[DriftResult]) -> str:
    """Return the report as a Markdown page for the docs site."""
    first = results[0]
    lines = [
        "# Distribution drift",
        "",
        "Generated by `pippen drift`. Compares the earliest shipped rating window "
        f"against the latest, {first.reference_window} against {first.comparison_window}.",
        "",
        "These ratings are recomputed from scratch rather than predicted, so this "
        "is not model drift against production traffic. It answers a narrower "
        "question: has the league's impact distribution moved enough that "
        "comparing a player across these windows needs a caveat?",
        "",
        "| Column | PSI | Reading | KS | p | Reference n | Comparison n |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| `{result.column}` | {result.psi:.3f} | {result.verdict} | "
            f"{result.ks_statistic:.3f} | {result.ks_p_value:.3g} | "
            f"{result.reference_n} | {result.comparison_n} |"
        )
    lines += [
        "",
        f"PSI bands are the credit-scoring convention: below {PSI_STABLE} the same "
        f"population, {PSI_STABLE} to {PSI_SHIFTED} worth watching, above "
        f"{PSI_SHIFTED} a different population.",
        "",
        "A large KS statistic with a small p-value on a sample this size is easy "
        "to obtain and hard to interpret. Read the PSI first.",
    ]
    return "\n".join(lines) + "\n"
