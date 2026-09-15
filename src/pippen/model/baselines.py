"""Supervised baselines, and the question they answer that the claim did not.

What the claim left open
------------------------
The claim under test compared candidates one at a time: each player rating was
aggregated to team level and used on its own to predict next-season net rating.
RAPM won, and the fusion was indistinguishable from it.

That comparison has a gap. It never asked whether all the metrics together,
combined by a model fitted to the target rather than by a latent-variable model
fitted to their shared structure, would beat RAPM alone. A negative result for
one way of combining metrics is not a negative result for every way of combining
them.

So two supervised baselines take every metric at once:

Ridge
    Linear, with an L2 penalty. The multivariate extension of the single-metric
    comparison, and the honest first thing to try.

LightGBM
    Gradient-boosted trees, which can use interactions and non-linearity that
    ridge cannot. If team quality depends on a metric only in combination with
    another, this is what would find it.

Nested selection, and why it is worth the compute
-------------------------------------------------
Hyperparameters are chosen inside the training seasons of each outer fold, by a
second leave-one-season-out search that never sees the held-out season. The
outer season is then scored once, with parameters it played no part in
choosing.

The first version of this module tuned against the same folds it reported,
while its docstring claimed otherwise. The bias that introduces was measured on
a pure-noise control, 180 rows of informationless features, and came to between
0.00 and 0.03 RMSE, small because the selection statistic averages 180 held-out
observations and forty trials in a conservative space are highly correlated. The
published conclusions did not depend on it.

It is fixed anyway, for two reasons. A docstring that describes a methodology
the code does not implement is worse than the shortcut it conceals. And the bias
grows with the search space and the trial budget, so the shortcut is a trap for
whoever widens either.

Imputation sits inside the pipeline for the same reason. Filling missing values
with a column mean computed over the whole frame lets a held-out row influence
the value used to train against it. Inside a pipeline the fill is fitted on the
training split alone.

What makes the comparison fair
------------------------------
The same panel, the same folds, the same trial budget for both. Folds split by
season and never by team, because two teams in the same season played each other.

Tracking
--------
Runs go to MLflow so the trial history survives the process that produced it. A
number pasted into a document cannot be audited later or compared against a
rerun after the data changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
import pandas as pd

from pippen.errors import MissingDependencyError
from pippen.model.panel import Fold, TeamPanel
from pippen.repro import DEFAULT_SEED

#: Optuna trials per baseline unless a caller says otherwise.
DEFAULT_TRIALS: Final = 40

#: Where MLflow writes when no tracking server is configured.
DEFAULT_EXPERIMENT: Final = "pippen-baselines"

_MISSING_OPTUNA = "optuna is required; install the 'fit' extra"
_MISSING_LIGHTGBM = "optuna and lightgbm are required; install the 'fit' extra"


@dataclass(frozen=True)
class BaselineResult:
    """Out-of-sample accuracy of one tuned baseline.

    Attributes:
        name: Baseline name.
        rmse: Root mean squared error across held-out seasons, from the nested
            search, so no held-out season influenced the parameters used on it.
        squared_errors: Per-observation squared error, so a difference against
            another candidate can be tested rather than eyeballed.
        fitted: The estimator refitted on every row, with parameters selected
            by a search over all seasons. Not used for the reported error,
            which would be circular. It exists so attribution has a model to
            explain; the previous version discarded it, which is why the
            published SHAP table could not be regenerated from this package.
        best_params: Parameters of ``fitted``.
        fold_params: Parameters each outer fold selected. Wide disagreement
            between folds is a sign the search is fitting noise.
        trials: Trials run per search.
    """

    name: str
    rmse: float
    squared_errors: pd.Series
    fitted: Any = None
    best_params: dict[str, Any] = field(default_factory=dict)
    fold_params: list[dict[str, Any]] = field(default_factory=list)
    trials: int = 0

    def describe(self) -> str:
        """Return a one-line summary including the tuning budget."""
        return f"{self.name}: RMSE {self.rmse:.3f} over {self.trials} tuning trials per fold"


def _score(build: Callable[[], Any], panel: TeamPanel, folds: list[Fold]) -> pd.Series:
    """Fit on each fold's training rows and score its held-out rows.

    Args:
        build: Returns a fresh unfitted estimator. Called once per fold, so no
            state leaks between folds.
        panel: The table being scored.
        folds: Splits to use.

    Returns:
        Per-observation squared error, ``NaN`` where a fold was unusable.
    """
    errors = pd.Series(np.nan, index=panel.features.index, dtype="float64")
    for fold in folds:
        if not fold.usable:
            continue
        model = build()
        model.fit(panel.features[fold.train], panel.target[fold.train])
        predicted = model.predict(panel.features[fold.test])
        errors.loc[fold.test] = (predicted - panel.target[fold.test].to_numpy()) ** 2
    return errors


def _search(
    build: Callable[[dict[str, Any]], Any],
    suggest: Callable[[Any], dict[str, Any]],
    panel: TeamPanel,
    folds: list[Fold],
    *,
    trials: int,
    seed: int,
) -> dict[str, Any]:
    """Return the parameters minimising cross-validated error over ``folds``.

    Args:
        build: Turns a parameter dict into an unfitted estimator.
        suggest: Draws a parameter dict from an Optuna trial.
        panel: The table to search over.
        folds: Splits the search is scored on. These must exclude any season
            the caller intends to report on.
        trials: Trials to run.
        seed: Seed for the sampler.

    Returns:
        The best parameter dict.

    Raises:
        MissingDependencyError: If Optuna is not installed.
    """
    try:
        import optuna
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError(_MISSING_OPTUNA) from exc

    def objective(trial: Any) -> float:
        params = suggest(trial)
        return float(np.sqrt(_score(lambda: build(params), panel, folds).mean()))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, show_progress_bar=False)
    return dict(study.best_params)


def tune(
    name: str,
    build: Callable[[dict[str, Any]], Any],
    suggest: Callable[[Any], dict[str, Any]],
    panel: TeamPanel,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
) -> BaselineResult:
    """Score one estimator family by nested leave-one-season-out selection.

    For each outer fold, a search runs over the remaining seasons only and the
    held-out season is then scored once. The reported error therefore contains
    no season that helped choose the parameters used on it.

    Args:
        name: Baseline name, for reporting.
        build: Turns a parameter dict into an unfitted estimator.
        suggest: Draws a parameter dict from an Optuna trial.
        panel: The table to score.
        trials: Trials per search. The same budget runs once per outer fold and
            once more for the model kept for attribution.
        seed: Seed for the samplers.

    Returns:
        A :class:`BaselineResult`.
    """
    errors = pd.Series(np.nan, index=panel.features.index, dtype="float64")
    fold_params: list[dict[str, Any]] = []

    outer = panel.folds()
    seasons = sorted(panel.seasons.unique())
    for fold in outer:
        if not fold.usable:
            continue
        inner_seasons = [season for season in seasons if season != fold.held_out]
        inner = panel.folds(over=inner_seasons)
        params = _search(build, suggest, panel, inner, trials=trials, seed=seed)
        fold_params.append(params)

        model = build(params)
        model.fit(panel.features[fold.train], panel.target[fold.train])
        predicted = model.predict(panel.features[fold.test])
        errors.loc[fold.test] = (predicted - panel.target[fold.test].to_numpy()) ** 2

    # A model kept for attribution, tuned over every season. Its parameters saw
    # all the data, so it is never used for the reported error.
    final_params = _search(build, suggest, panel, outer, trials=trials, seed=seed)
    fitted = build(final_params)
    fitted.fit(panel.features, panel.target)

    return BaselineResult(
        name=name,
        rmse=float(np.sqrt(errors.mean())),
        squared_errors=errors,
        fitted=fitted,
        best_params=final_params,
        fold_params=fold_params,
        trials=trials,
    )


def ridge_baseline(
    panel: TeamPanel, *, trials: int = DEFAULT_TRIALS, seed: int = DEFAULT_SEED
) -> BaselineResult:
    """Tune and score a ridge regression over every candidate at once.

    Imputation and scaling sit inside the pipeline so both are fitted on the
    training split of each fold rather than on the whole panel.

    Args:
        panel: The table to score.
        trials: Trials per search.
        seed: Seed for the samplers.

    Returns:
        A :class:`BaselineResult`.
    """
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def build(params: dict[str, Any]) -> Any:
        return make_pipeline(
            SimpleImputer(strategy="mean"), StandardScaler(), Ridge(alpha=params["alpha"])
        )

    def suggest(trial: Any) -> dict[str, Any]:
        return {"alpha": trial.suggest_float("alpha", 1e-3, 1e4, log=True)}

    return tune("ridge", build, suggest, panel, trials=trials, seed=seed)


def lightgbm_baseline(
    panel: TeamPanel, *, trials: int = DEFAULT_TRIALS, seed: int = DEFAULT_SEED
) -> BaselineResult:
    """Tune and score gradient-boosted trees over every candidate at once.

    The search space is deliberately conservative. With a couple of hundred
    team-seasons, a deep forest would memorise the training folds and the
    comparison would measure tuning effort rather than signal. LightGBM splits
    on missing values natively, so no imputation is needed.

    Args:
        panel: The table to score.
        trials: Trials per search.
        seed: Seed for the samplers.

    Returns:
        A :class:`BaselineResult`.

    Raises:
        MissingDependencyError: If LightGBM is not installed.
    """
    try:
        import lightgbm as lgb
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError(_MISSING_LIGHTGBM) from exc

    def build(params: dict[str, Any]) -> Any:
        return lgb.LGBMRegressor(random_state=seed, verbose=-1, **params)

    def suggest(trial: Any) -> dict[str, Any]:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 3, 31),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 40),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }

    return tune("lightgbm", build, suggest, panel, trials=trials, seed=seed)


def run_baselines(
    panel: TeamPanel,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    experiment: str | None = DEFAULT_EXPERIMENT,
) -> list[BaselineResult]:
    """Tune and score both baselines, optionally recording the runs in MLflow.

    Args:
        panel: The table to score.
        trials: Trials per search, per baseline.
        seed: Seed for the samplers.
        experiment: MLflow experiment name, or ``None`` to skip tracking.
            Skipping is offered so a test does not write to a tracking store.

    Returns:
        One :class:`BaselineResult` per baseline, ordered best first.
    """
    results = [
        ridge_baseline(panel, trials=trials, seed=seed),
        lightgbm_baseline(panel, trials=trials, seed=seed),
    ]

    if experiment is not None:
        try:
            import mlflow
        except ImportError:  # pragma: no cover - tracking is optional
            pass
        else:
            mlflow.set_experiment(experiment)
            for result in results:
                with mlflow.start_run(run_name=result.name):
                    mlflow.log_params(result.best_params)
                    mlflow.log_param("trials", result.trials)
                    mlflow.log_param("selection", "nested leave-one-season-out")
                    mlflow.log_param("candidates", len(panel.candidates))
                    mlflow.log_param("observations", panel.n_observations)
                    mlflow.log_metric("rmse", result.rmse)

    return sorted(results, key=lambda item: item.rmse)
