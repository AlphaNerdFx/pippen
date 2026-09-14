"""Tests for the measurement-error fusion model.

Fitted on synthetic data where the latent quantity is known, because that is
the only way to tell "the sampler converged" from "the sampler converged on the
right thing". The first version of this model converged happily onto a position
axis with the anchor loading at 0.013, so the distinction is not academic.

Chains are short on purpose. These check the model's structure, not its
precision, and a full-length fit belongs in a script rather than a test suite.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from pippen.model.dataset import RAPM_COLUMN, FusionDataset
from pippen.model.fusion import fit_fusion

pytestmark = pytest.mark.slow


def _synthetic(
    n_players: int = 120,
    loadings: dict[str, float] | None = None,
    seed: int = 11,
) -> tuple[FusionDataset, pd.Series, pd.Series]:
    """Build a dataset from a known latent quantity.

    Returns the dataset, the reliability bounds, and the true latent values.
    """
    loadings = loadings or {"good": 0.8, "weak": 0.3, "useless": 0.0}
    rng = np.random.default_rng(seed)
    index = pd.Index(range(1, n_players + 1), name="nba_id")
    theta = rng.normal(0.0, 1.0, n_players)

    columns: dict[str, Any] = {}
    for name, loading in loadings.items():
        residual = np.sqrt(max(1.0 - loading**2, 1e-6))
        columns[name] = loading * theta + residual * rng.normal(0.0, 1.0, n_players)
    columns[RAPM_COLUMN] = 0.85 * theta + np.sqrt(1 - 0.85**2) * rng.normal(0.0, 1.0, n_players)

    raw = pd.DataFrame(columns, index=index)
    centres = raw.mean()
    scales = raw.std(ddof=0)
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
    return dataset, reliability, pd.Series(theta, index=index)


def _fit(**kwargs: object) -> tuple[object, pd.Series]:
    dataset, reliability, theta = _synthetic()
    fit = fit_fusion(dataset, reliability, warmup=300, samples=300, chains=1, **kwargs)  # type: ignore[arg-type]
    return fit, theta


# ------------------------------------------------------------------ recovery


def test_the_latent_quantity_is_recovered() -> None:
    fit, theta = _fit()
    recovered = fit.ratings.set_index("nba_id")["impact"]  # type: ignore[attr-defined]
    assert recovered.corr(theta.loc[recovered.index]) > 0.85


def test_loadings_order_the_metrics_correctly() -> None:
    fit, _ = _fit()
    loadings = fit.loadings.set_index("metric")["loading"]  # type: ignore[attr-defined]
    assert loadings["good"] > loadings["weak"] > loadings["useless"] - 0.15
    assert loadings["good"] > 0.6


def test_a_metric_unrelated_to_the_latent_quantity_gets_almost_no_loading() -> None:
    fit, _ = _fit()
    loadings = fit.loadings.set_index("metric")["loading"]  # type: ignore[attr-defined]
    assert abs(loadings["useless"]) < 0.2


# ------------------------------------------------------------------ the bound


def test_no_loading_exceeds_what_reliability_permits() -> None:
    # This is the model's central claim: reliability caps how much of a metric
    # can be attributed to the latent quantity.
    fit, _ = _fit()
    table = fit.loadings  # type: ignore[attr-defined]
    assert (table["loading"].abs() <= table["bound"] + 1e-6).all()


def test_a_low_reliability_bound_binds() -> None:
    dataset, reliability, _ = _synthetic(loadings={"good": 0.9})
    reliability["good"] = 0.09  # bound of 0.3, well below the true loading
    fit = fit_fusion(dataset, reliability, warmup=300, samples=300, chains=1)
    row = fit.loadings.set_index("metric").loc["good"].astype(float)
    assert abs(row["loading"]) <= np.sqrt(0.09) + 1e-6


# ------------------------------------------------------------------ the anchor


def test_the_fixed_anchor_sits_at_its_bound() -> None:
    fit, _ = _fit(anchor_loading="fixed")
    row = fit.loadings.set_index("metric").loc[RAPM_COLUMN]  # type: ignore[attr-defined]
    assert float(row["loading"]) == pytest.approx(float(row["bound"]), abs=1e-6)
    assert float(row["share_of_bound"]) == pytest.approx(1.0, abs=1e-6)


def test_a_free_anchor_is_only_held_positive() -> None:
    fit, _ = _fit(anchor_loading="positive")
    loading = fit.loadings.set_index("metric").loc[RAPM_COLUMN, "loading"]  # type: ignore[attr-defined]
    assert float(loading) >= 0.0


def test_an_unknown_anchor_mode_is_refused() -> None:
    dataset, reliability, _ = _synthetic()
    with pytest.raises(ValueError, match="anchor_loading must be"):
        fit_fusion(dataset, reliability, anchor_loading="whatever")


def test_an_absent_anchor_is_refused() -> None:
    dataset, reliability, _ = _synthetic()
    broken = FusionDataset(
        values=dataset.values.drop(columns=[RAPM_COLUMN]),
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=dataset.nba_seasons,
        anchor=RAPM_COLUMN,
    )
    with pytest.raises(ValueError, match="unidentified"):
        fit_fusion(broken, reliability)


# ------------------------------------------------------------------ missing data


def test_missing_values_do_not_break_the_fit() -> None:
    dataset, reliability, theta = _synthetic()
    holed = dataset.values.copy()
    rng = np.random.default_rng(2)
    mask = rng.random(holed.shape) < 0.2
    holed = holed.mask(pd.DataFrame(mask, index=holed.index, columns=holed.columns))
    punched = FusionDataset(
        values=holed,
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=dataset.nba_seasons,
        anchor=dataset.anchor,
    )
    fit = fit_fusion(punched, reliability, warmup=300, samples=300, chains=1)
    recovered = fit.ratings.set_index("nba_id")["impact"]
    assert np.isfinite(recovered).all()
    assert recovered.corr(theta.loc[recovered.index]) > 0.7


# ------------------------------------------------------------------ output shape


def test_every_player_gets_an_interval_that_contains_its_mean() -> None:
    fit, _ = _fit()
    ratings = fit.ratings  # type: ignore[attr-defined]
    assert (ratings["lower"] < ratings["impact"]).all()
    assert (ratings["impact"] < ratings["upper"]).all()
    assert (ratings["sd"] > 0).all()


def test_the_summary_names_the_anchor_and_its_mode() -> None:
    fit, _ = _fit(anchor_loading="fixed")
    text = fit.describe()  # type: ignore[attr-defined]
    assert "rapm" in text
    assert "fixed" in text
    assert "r-hat" in text
