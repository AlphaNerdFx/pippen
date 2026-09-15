"""Tests for the supervised baselines and SHAP attribution.

The risk here is not that a model fails to fit. It is that the comparison is
unfair in a way that flatters one side: folds that leak a season across the
split, or hyperparameters chosen against the held-out data. Both produce a
number that looks like out-of-sample error and is not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.model.attribution import AttributionResult, explain
from pippen.model.baselines import (
    BaselineResult,
    _season_folds,
    run_baselines,
    tune_lightgbm,
    tune_ridge,
)

pytestmark = pytest.mark.slow


def _panel(
    seasons: int = 5, teams: int = 30, seed: int = 6
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """A panel where two of four features carry the signal."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2016 + seasons):
        for team in range(teams):
            a = rng.normal(0.0, 1.0)
            b = rng.normal(0.0, 1.0)
            rows.append(
                {
                    "season": season,
                    "team": team,
                    "useful_a": a,
                    "useful_b": b,
                    "noise_a": rng.normal(0.0, 1.0),
                    "noise_b": rng.normal(0.0, 1.0),
                    "target": 3.0 * a - 2.0 * b + rng.normal(0.0, 1.0),
                }
            )
    frame = pd.DataFrame(rows).set_index(["season", "team"])
    features = frame[["useful_a", "useful_b", "noise_a", "noise_b"]]
    return features, frame["target"], pd.Series([i[0] for i in frame.index], index=frame.index)


# ------------------------------------------------------------------ folds


def test_folds_hold_out_one_whole_season_each() -> None:
    _, _, seasons = _panel(seasons=4)
    folds = _season_folds(seasons)
    assert len(folds) == 4
    for train, test in folds:
        assert not bool((train & test).any())
        assert len(set(seasons[test])) == 1


def test_every_row_is_held_out_exactly_once() -> None:
    _, _, seasons = _panel(seasons=4)
    folds = _season_folds(seasons)
    counts = pd.concat([test.astype(int) for _, test in folds], axis=1).sum(axis=1)
    assert bool((counts == 1).all())


# ------------------------------------------------------------------ fitting


def test_ridge_recovers_the_signal() -> None:
    features, target, seasons = _panel()
    result = tune_ridge(features, target, seasons, trials=8)
    assert result.name == "ridge"
    assert np.isfinite(result.rmse)
    # Target sd is about 3.9; a model that found the signal beats that.
    assert result.rmse < 2.0
    assert "alpha" in result.best_params


def test_lightgbm_fits_and_reports_its_parameters() -> None:
    features, target, seasons = _panel()
    result = tune_lightgbm(features, target, seasons, trials=6)
    assert result.name == "lightgbm"
    assert np.isfinite(result.rmse)
    assert "learning_rate" in result.best_params


def test_per_observation_errors_are_kept_for_paired_testing() -> None:
    features, target, seasons = _panel(seasons=3, teams=20)
    result = tune_ridge(features, target, seasons, trials=4)
    assert int(result.squared_errors.notna().sum()) == 60
    assert bool((result.squared_errors.dropna() >= 0).all())


def test_both_baselines_run_and_are_ordered_best_first() -> None:
    features, target, seasons = _panel(seasons=3, teams=20)
    results = run_baselines(features, target, seasons, trials=4, experiment=None)
    assert len(results) == 2
    assert {r.name for r in results} == {"ridge", "lightgbm"}
    assert results[0].rmse <= results[1].rmse


def test_a_result_describes_its_tuning_budget() -> None:
    described = BaselineResult(
        name="ridge", rmse=4.2, squared_errors=pd.Series([1.0]), best_params={}, trials=40
    ).describe()
    assert "40 tuning trials" in described


# ------------------------------------------------------------------ attribution


def test_shap_finds_the_features_that_carry_the_signal() -> None:
    import lightgbm as lgb

    features, target, _ = _panel()
    model = lgb.LGBMRegressor(n_estimators=120, verbose=-1, random_state=1)
    model.fit(features, target)

    result = explain(model, features)
    ranked = list(result.importance["metric"])
    assert set(ranked[:2]) == {"useful_a", "useful_b"}
    assert result.rows_explained == len(features)


def test_attribution_reports_the_direction_of_each_feature() -> None:
    import lightgbm as lgb

    features, target, _ = _panel()
    model = lgb.LGBMRegressor(n_estimators=120, verbose=-1, random_state=1)
    model.fit(features, target)
    importance = explain(model, features).importance.set_index("metric")["mean_abs_shap"]
    assert float(importance.loc["useful_a"]) > float(importance.loc["noise_a"])


def test_a_large_table_is_sampled() -> None:
    import lightgbm as lgb

    features, target, _ = _panel(seasons=20, teams=40)
    model = lgb.LGBMRegressor(n_estimators=60, verbose=-1, random_state=1)
    model.fit(features, target)
    result = explain(model, features, sample=100)
    assert result.rows_explained == 100


def test_agreement_compares_against_fusion_loadings() -> None:
    importance = pd.DataFrame(
        {
            "metric": ["a", "b", "c", "d"],
            "mean_abs_shap": [4.0, 3.0, 2.0, 1.0],
            "mean_shap": [0.0, 0.0, 0.0, 0.0],
        }
    )
    result = AttributionResult(importance=importance, rows_explained=10, base_value=0.0)

    same = pd.DataFrame({"metric": ["a", "b", "c", "d"], "loading": [0.8, 0.6, 0.4, 0.2]})
    assert result.agreement_with(same) == pytest.approx(1.0)

    reversed_order = pd.DataFrame({"metric": ["a", "b", "c", "d"], "loading": [0.2, 0.4, 0.6, 0.8]})
    assert result.agreement_with(reversed_order) == pytest.approx(-1.0)


def test_agreement_needs_three_shared_metrics() -> None:
    importance = pd.DataFrame(
        {"metric": ["a", "b"], "mean_abs_shap": [1.0, 2.0], "mean_shap": [0.0, 0.0]}
    )
    result = AttributionResult(importance=importance, rows_explained=5, base_value=0.0)
    assert np.isnan(result.agreement_with(pd.DataFrame({"metric": ["a"], "loading": [0.5]})))


def test_an_empty_table_cannot_be_explained() -> None:
    import lightgbm as lgb

    features, target, _ = _panel(seasons=2, teams=10)
    model = lgb.LGBMRegressor(n_estimators=10, verbose=-1, random_state=1)
    model.fit(features, target)
    with pytest.raises(ValueError, match="no rows to explain"):
        explain(model, features.iloc[:0])
