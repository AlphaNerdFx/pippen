"""Tests for the interval calibration check.

The check exists to catch over-confidence, so the tests that matter are the
ones proving it would actually notice. A calibration check that always passes
is worse than none, because it licenses a claim it never tested.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.model.calibration import (
    CalibrationResult,
    NotEnoughDataError,
    check_calibration,
)
from pippen.model.dataset import RAPM_COLUMN, FusionDataset

pytestmark = pytest.mark.slow


def _dataset(n_players: int = 90, seed: int = 12) -> tuple[FusionDataset, pd.Series]:
    rng = np.random.default_rng(seed)
    index = pd.Index(range(1, n_players + 1), name="nba_id")
    theta = rng.normal(0.0, 1.0, n_players)
    columns = {}
    for name, loading in {"a": 0.8, "b": 0.5, "c": 0.2}.items():
        residual = np.sqrt(1.0 - loading**2)
        columns[name] = loading * theta + residual * rng.normal(0.0, 1.0, n_players)
    columns[RAPM_COLUMN] = 0.85 * theta + np.sqrt(1 - 0.85**2) * rng.normal(0.0, 1.0, n_players)
    raw = pd.DataFrame(columns, index=index)
    centres, scales = raw.mean(), raw.std(ddof=0)
    dataset = FusionDataset(
        values=(raw - centres) / scales,
        raw=raw,
        centres=centres,
        scales=scales,
        minutes=pd.Series(2000.0, index=index),
        possessions=pd.Series(8000.0, index=index),
        nba_seasons=(2016, 2017, 2018),
        anchor=RAPM_COLUMN,
    )
    reliability = pd.Series(dict.fromkeys(raw.columns, 0.95))
    reliability[RAPM_COLUMN] = 0.80
    return dataset, reliability


# ------------------------------------------------------------------ the verdict


def test_coverage_near_nominal_counts_as_calibrated() -> None:
    result = CalibrationResult(
        nominal=0.90,
        observed=0.91,
        held_out=1000,
        tolerance=0.05,
        by_metric=pd.DataFrame(),
        median_width=2.6,
    )
    assert result.calibrated
    assert result.direction == "calibrated"


def test_too_narrow_intervals_are_named_over_confident() -> None:
    # This is the failure the check exists to catch: a model claiming more
    # precision than it has.
    result = CalibrationResult(
        nominal=0.90,
        observed=0.70,
        held_out=1000,
        tolerance=0.05,
        by_metric=pd.DataFrame(),
        median_width=1.0,
    )
    assert not result.calibrated
    assert result.direction == "over-confident"
    assert "over-confident" in result.describe()


def test_too_wide_intervals_are_named_under_confident() -> None:
    result = CalibrationResult(
        nominal=0.90,
        observed=0.99,
        held_out=1000,
        tolerance=0.05,
        by_metric=pd.DataFrame(),
        median_width=8.0,
    )
    assert result.direction == "under-confident"


def test_the_summary_reports_width_so_coverage_cannot_be_bought_with_vagueness() -> None:
    # An interval from minus infinity to infinity covers everything. Reporting
    # the width is what stops that reading as success.
    result = CalibrationResult(
        nominal=0.90,
        observed=0.90,
        held_out=100,
        tolerance=0.05,
        by_metric=pd.DataFrame(),
        median_width=2.65,
    )
    assert "2.65 sd" in result.describe()


# ------------------------------------------------------------------ the check


def test_a_correctly_specified_model_is_calibrated() -> None:
    dataset, reliability = _dataset()
    result = check_calibration(
        dataset, reliability, nominal=0.90, warmup=400, samples=400, chains=2
    )
    assert result.held_out > 10
    assert abs(result.observed - 0.90) < 0.10


def test_a_narrower_nominal_interval_covers_less() -> None:
    dataset, reliability = _dataset()
    wide = check_calibration(dataset, reliability, nominal=0.90, warmup=400, samples=400, chains=2)
    narrow = check_calibration(
        dataset, reliability, nominal=0.50, warmup=400, samples=400, chains=2
    )
    assert narrow.observed < wide.observed
    assert narrow.median_width < wide.median_width


def test_coverage_is_reported_per_metric() -> None:
    dataset, reliability = _dataset()
    result = check_calibration(dataset, reliability, warmup=400, samples=400, chains=2)
    assert set(result.by_metric["metric"]) <= set(dataset.values.columns)
    assert (result.by_metric["coverage"] <= 1.0).all()
    assert int(result.by_metric["held_out"].sum()) == result.held_out


def test_holding_out_too_little_is_refused() -> None:
    dataset, reliability = _dataset(n_players=20)
    with pytest.raises(NotEnoughDataError, match="at least ten"):
        check_calibration(dataset, reliability, hold_out=0.01)
