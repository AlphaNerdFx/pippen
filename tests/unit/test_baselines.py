"""Tests for the supervised baselines and SHAP attribution.

The risk is not a model failing to fit. It is a comparison that is unfair in a
way that flatters one side, which produces a number looking like out-of-sample
error that is not one. The first version of this module tuned against the folds
it reported while its docstring claimed otherwise, so the nested-selection tests
below are the ones that matter.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from pippen.model.attribution import AttributionResult, explain
from pippen.model.baselines import (
    BaselineResult,
    lightgbm_baseline,
    ridge_baseline,
    run_baselines,
    tune,
)
from pippen.model.panel import TeamPanel

pytestmark = pytest.mark.slow


def _panel(seasons: int = 5, teams: int = 30, seed: int = 6) -> TeamPanel:
    """A panel where two of four candidates carry the signal."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2016 + seasons):
        for team in range(teams):
            a = rng.normal(0.0, 1.0)
            b = rng.normal(0.0, 1.0)
            rows.append(
                {
                    "season": season,
                    "team_id": team,
                    "useful_a": a,
                    "useful_b": b,
                    "noise_a": rng.normal(0.0, 1.0),
                    "noise_b": rng.normal(0.0, 1.0),
                    "target": 3.0 * a - 2.0 * b + rng.normal(0.0, 1.0),
                }
            )
    frame = pd.DataFrame(rows).set_index(["season", "team_id"])
    return TeamPanel.build(frame[["useful_a", "useful_b", "noise_a", "noise_b"]], frame["target"])


# ------------------------------------------------------------------ nested selection


def test_the_search_never_sees_the_season_it_is_scored_on() -> None:
    """The property the whole module rests on, checked by recording the splits."""
    panel = _panel(seasons=4, teams=15)
    seen: list[set[int]] = []

    def build(params: dict[str, Any]) -> Any:
        from sklearn.linear_model import Ridge

        return Ridge(alpha=params["alpha"])

    def suggest(trial: Any) -> dict[str, Any]:
        return {"alpha": trial.suggest_float("alpha", 0.1, 10.0, log=True)}

    original = TeamPanel.folds

    def recording(self: TeamPanel, *, over: Any = None) -> Any:
        folds = original(self, over=over)
        if over is not None:
            seen.append({fold.held_out for fold in folds})
        return folds

    TeamPanel.folds = recording  # type: ignore[method-assign]
    try:
        tune("ridge", build, suggest, panel, trials=3)
    finally:
        TeamPanel.folds = original  # type: ignore[method-assign]

    all_seasons = set(panel.seasons.unique())
    assert len(seen) == len(all_seasons)
    # Each inner search covers every season but the one its outer fold holds out.
    assert sorted(len(s) for s in seen) == [len(all_seasons) - 1] * len(all_seasons)
    for inner in seen:
        assert len(all_seasons - inner) == 1


def test_each_outer_fold_records_the_parameters_it_chose() -> None:
    # Wide disagreement between folds is a sign the search is fitting noise, so
    # the per-fold choices are kept rather than only the final ones.
    result = ridge_baseline(_panel(seasons=4, teams=15), trials=3)
    assert len(result.fold_params) == 4
    assert all("alpha" in params for params in result.fold_params)


# ------------------------------------------------------------------ fitting


def test_ridge_recovers_the_signal() -> None:
    result = ridge_baseline(_panel(), trials=5)
    assert result.name == "ridge"
    assert np.isfinite(result.rmse)
    # Target sd is about 3.9; a model that found the signal beats that.
    assert result.rmse < 2.0
    assert "alpha" in result.best_params


def test_lightgbm_fits_and_reports_its_parameters() -> None:
    result = lightgbm_baseline(_panel(seasons=4, teams=20), trials=3)
    assert result.name == "lightgbm"
    assert np.isfinite(result.rmse)
    assert "learning_rate" in result.best_params


def test_a_fitted_model_is_carried_for_attribution() -> None:
    # Discarding it is why the published SHAP table could not be regenerated.
    result = lightgbm_baseline(_panel(seasons=4, teams=20), trials=3)
    assert result.fitted is not None
    assert hasattr(result.fitted, "predict")


def test_missing_values_do_not_break_ridge() -> None:
    # Imputation sits inside the pipeline so it is fitted per fold. A column
    # mean taken over the whole panel would let a held-out row influence the
    # value used to train against it.
    panel = _panel(seasons=4, teams=20)
    holed = panel.features.copy()
    holed.iloc[0, 0] = np.nan
    holed.iloc[5, 2] = np.nan
    result = ridge_baseline(TeamPanel.build(holed, panel.target), trials=3)
    assert np.isfinite(result.rmse)


def test_per_observation_errors_are_kept_for_paired_testing() -> None:
    result = ridge_baseline(_panel(seasons=3, teams=20), trials=3)
    assert int(result.squared_errors.notna().sum()) == 60
    assert bool((result.squared_errors.dropna() >= 0).all())


def test_both_baselines_run_and_are_ordered_best_first() -> None:
    results = run_baselines(_panel(seasons=3, teams=20), trials=3, experiment=None)
    assert len(results) == 2
    assert {r.name for r in results} == {"ridge", "lightgbm"}
    assert results[0].rmse <= results[1].rmse


def test_a_result_describes_its_tuning_budget() -> None:
    described = BaselineResult(
        name="ridge", rmse=4.2, squared_errors=pd.Series([1.0]), trials=40
    ).describe()
    assert "40 tuning trials per fold" in described


# ------------------------------------------------------------------ attribution


def test_shap_finds_the_candidates_that_carry_the_signal() -> None:
    import lightgbm as lgb

    panel = _panel()
    model = lgb.LGBMRegressor(n_estimators=120, verbose=-1, random_state=1)
    model.fit(panel.features, panel.target)

    result = explain(model, panel.features)
    ranked = list(result.importance["metric"])
    assert set(ranked[:2]) == {"useful_a", "useful_b"}
    assert result.rows_explained == panel.n_observations


def test_attribution_ranks_signal_above_noise() -> None:
    import lightgbm as lgb

    panel = _panel()
    model = lgb.LGBMRegressor(n_estimators=120, verbose=-1, random_state=1)
    model.fit(panel.features, panel.target)
    importance = explain(model, panel.features).importance.set_index("metric")["mean_abs_shap"]
    assert float(importance.loc["useful_a"]) > float(importance.loc["noise_a"])


def test_a_large_table_is_sampled() -> None:
    import lightgbm as lgb

    panel = _panel(seasons=20, teams=40)
    model = lgb.LGBMRegressor(n_estimators=60, verbose=-1, random_state=1)
    model.fit(panel.features, panel.target)
    assert explain(model, panel.features, sample=100).rows_explained == 100


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

    panel = _panel(seasons=2, teams=10)
    model = lgb.LGBMRegressor(n_estimators=10, verbose=-1, random_state=1)
    model.fit(panel.features, panel.target)
    with pytest.raises(ValueError, match="no rows to explain"):
        explain(model, panel.features.iloc[:0])
