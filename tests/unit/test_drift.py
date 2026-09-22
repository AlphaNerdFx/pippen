"""Tests for the distribution drift report.

PSI is the piece worth testing properly. It is a sum of signed log ratios over
bins, which means a sign error, a swapped argument or a missing epsilon all
produce a number rather than an exception, and a number that looks plausible.
The properties below pin the behaviour that makes the statistic meaningful:
zero on identical samples, symmetric in its arguments, monotone in how far the
comparison has moved, and finite when a bin empties.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.drift import (
    PSI_SHIFTED,
    PSI_STABLE,
    compare_windows,
    population_stability_index,
    render,
    report,
)


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(20260922)


def test_an_identical_sample_has_no_drift(rng: np.random.Generator) -> None:
    sample = pd.Series(rng.normal(size=2000))
    assert population_stability_index(sample, sample) == pytest.approx(0.0, abs=1e-9)


def test_psi_is_symmetric(rng: np.random.Generator) -> None:
    """Symmetry is why PSI is used here rather than a one-directional KL."""
    first = pd.Series(rng.normal(size=2000))
    second = pd.Series(rng.normal(loc=0.5, size=2000))
    forward = population_stability_index(first, second)
    backward = population_stability_index(second, first)
    # Bin edges come from whichever sample is the reference, so the two are
    # close rather than identical. A one-directional divergence would not be.
    assert forward == pytest.approx(backward, rel=0.35)


def test_psi_grows_as_the_distribution_moves(rng: np.random.Generator) -> None:
    reference = pd.Series(rng.normal(size=4000))
    shifts = [0.1, 0.5, 1.0, 2.0]
    scores = [
        population_stability_index(reference, pd.Series(rng.normal(loc=shift, size=4000)))
        for shift in shifts
    ]
    assert scores == sorted(scores), f"PSI should rise with the shift, got {scores}"


def test_a_small_shift_reads_stable_and_a_large_one_does_not(rng: np.random.Generator) -> None:
    reference = pd.Series(rng.normal(size=4000))
    nudged = pd.Series(rng.normal(loc=0.02, size=4000))
    moved = pd.Series(rng.normal(loc=2.0, size=4000))
    assert population_stability_index(reference, nudged) < PSI_STABLE
    assert population_stability_index(reference, moved) > PSI_SHIFTED


def test_an_empty_bin_stays_finite(rng: np.random.Generator) -> None:
    """Without the epsilon the log term is -inf and the report is unusable."""
    reference = pd.Series(rng.normal(size=1000))
    disjoint = pd.Series(rng.normal(loc=50.0, size=1000))
    score = population_stability_index(reference, disjoint)
    assert np.isfinite(score)
    assert score > PSI_SHIFTED


def test_an_empty_sample_is_refused() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        population_stability_index(pd.Series(dtype=float), pd.Series([1.0, 2.0]))


def _ratings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "window_end": [2018] * 5 + [2024] * 5,
            "offensive": [1.0, 2.0, 3.0, 4.0, 5.0, 1.1, 2.1, 3.1, 4.1, 5.1],
            "defensive": [0.5, 1.5, 2.5, 3.5, 4.5, 0.6, 1.6, 2.6, 3.6, 4.6],
            "total": [1.5, 3.5, 5.5, 7.5, 9.5, 1.7, 3.7, 5.7, 7.7, 9.7],
        }
    )


def test_a_window_that_does_not_exist_names_the_ones_that_do() -> None:
    with pytest.raises(ValueError, match=r"no window ends in 1999; available: \[2018, 2024\]"):
        compare_windows(_ratings(), reference_end=1999)


def test_the_report_covers_every_rating_column() -> None:
    results = report(_ratings())
    assert [result.column for result in results] == ["offensive", "defensive", "total"]
    assert all(result.reference_n == 5 and result.comparison_n == 5 for result in results)


def test_the_rendered_page_carries_the_numbers_and_the_caveat() -> None:
    page = render(report(_ratings()))
    assert page.startswith("# Distribution drift")
    for column in ("offensive", "defensive", "total"):
        assert f"`{column}`" in page
    # The KS caveat is the reason a reader does not over-read a small p-value.
    assert "Read the PSI first" in page
