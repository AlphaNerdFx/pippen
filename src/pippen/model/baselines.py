"""Supervised baselines, and the question they answer that the claim did not.

What the claim left open
------------------------
The claim under test compared candidates one at a time: each player rating was
aggregated to team level and used on its own to predict next-season net rating.
RAPM won, and the fusion was indistinguishable from it.

That comparison has a gap. It never asked whether *all* the metrics together,
combined by a model fitted to the target rather than by a latent-variable
model fitted to their shared structure, would beat RAPM alone. A negative
result for one way of combining metrics is not a negative result for every way
of combining them, and saying otherwise would be the sort of overreach this
project exists to avoid.

So two supervised baselines take every metric at once:

Ridge
    Linear, with an L2 penalty. The natural multivariate extension of the
    single-metric comparison, and the honest first thing to try.

LightGBM
    Gradient-boosted trees, which can use interactions and non-linearity that
    ridge cannot. If team quality depends on a metric only in combination with
    another, this is what would find it.

What makes the comparison fair
------------------------------
The same folds as the claim, split by season and never by team. The same
aggregation. The same target. Optuna tunes both, with the same trial budget
each, because a baseline that loses only because nobody tuned it proves
nothing.

Hyperparameters are selected inside the training folds, never against the
held-out season. Selecting against the held-out season is the most common way a
comparison like this quietly becomes a lie: the reported error is then the best
of many attempts rather than an estimate of out-of-sample error.

Tracking
--------
Runs go to MLflow so the trial history survives the process that produced it.
The alternative, a number pasted into a document, cannot be audited later and
cannot be compared against a rerun after the data changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
import pandas as pd

#: Optuna trials per baseline unless a caller says otherwise.
DEFAULT_TRIALS: Final = 40

#: Seed, matching the project-wide default.
DEFAULT_SEED: Final = 20260910

#: Where MLflow writes when no tracking server is configured.
DEFAULT_EXPERIMENT: Final = "pippen-baselines"


class MissingDependencyError(ImportError):
    """A baseline's library is not installed."""


@dataclass(frozen=True)
class BaselineResult:
    """Out-of-sample accuracy of one fitted baseline.

    Attributes:
        name: Baseline name.
        rmse: Root mean squared error across held-out seasons.
        squared_errors: Per-observation squared error, so the difference
            against another candidate can be tested rather than eyeballed.
        best_params: Hyperparameters Optuna selected.
        trials: Trials run.
    """

    name: str
    rmse: float
    squared_errors: pd.Series
    best_params: dict[str, Any] = field(default_factory=dict)
    trials: int = 0

    def describe(self) -> str:
        """Return a one-line summary including the tuning budget."""
        return f"{self.name}: RMSE {self.rmse:.3f} over {self.trials} tuning trials"


def _season_folds(seasons: pd.Series) -> list[tuple[pd.Series, pd.Series]]:
    """Return one train/test mask pair per season.

    Splitting by season rather than by row is what keeps a model from
    predicting the rest of a season it has already seen.
    """
    return [(seasons != held_out, seasons == held_out) for held_out in sorted(seasons.unique())]


def _cross_validated_error(
    build: Callable[[], Any],
    features: pd.DataFrame,
    target: pd.Series,
    folds: list[tuple[pd.Series, pd.Series]],
) -> tuple[float, pd.Series]:
    """Fit on each fold's training rows and score its held-out rows.

    Args:
        build: Returns a fresh unfitted estimator. Called once per fold, so no
            state leaks between folds.
        features: All candidate columns.
        target: What to predict.
        folds: Train/test mask pairs.

    Returns:
        The root mean squared error and the per-observation squared errors.
    """
    errors = pd.Series(np.nan, index=features.index, dtype="float64")
    for train, test in folds:
        if train.sum() < 5 or test.sum() == 0:
            continue
        model = build()
        model.fit(features[train], target[train])
        predicted = model.predict(features[test])
        errors.loc[test] = (predicted - target[test].to_numpy()) ** 2
    return float(np.sqrt(errors.mean())), errors


def tune_ridge(
    features: pd.DataFrame,
    target: pd.Series,
    seasons: pd.Series,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
) -> BaselineResult:
    """Tune and score a ridge regression over every metric at once.

    Args:
        features: One column per metric, indexed by team-season.
        target: Next season's net rating.
        seasons: Season each row belongs to.
        trials: Optuna trials.
        seed: Seed for the sampler.

    Returns:
        A :class:`BaselineResult`.

    Raises:
        MissingDependencyError: If Optuna is not installed.
    """
    try:
        import optuna
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError("optuna is required; install the 'fit' extra") from exc
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    folds = _season_folds(seasons)
    filled = features.fillna(features.mean())

    def objective(trial: Any) -> float:
        alpha = trial.suggest_float("alpha", 1e-3, 1e4, log=True)
        score, _ = _cross_validated_error(
            lambda: make_pipeline(StandardScaler(), Ridge(alpha=alpha)), filled, target, folds
        )
        return score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, show_progress_bar=False)

    best = study.best_params
    rmse, errors = _cross_validated_error(
        lambda: make_pipeline(StandardScaler(), Ridge(alpha=best["alpha"])), filled, target, folds
    )
    return BaselineResult(
        name="ridge", rmse=rmse, squared_errors=errors, best_params=best, trials=trials
    )


def tune_lightgbm(
    features: pd.DataFrame,
    target: pd.Series,
    seasons: pd.Series,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
) -> BaselineResult:
    """Tune and score gradient-boosted trees over every metric at once.

    The search space is deliberately conservative. With a couple of hundred
    team-seasons, a deep forest would memorise the training folds and the
    comparison would measure tuning effort rather than signal.

    Args:
        features: One column per metric, indexed by team-season.
        target: Next season's net rating.
        seasons: Season each row belongs to.
        trials: Optuna trials.
        seed: Seed for the sampler.

    Returns:
        A :class:`BaselineResult`.

    Raises:
        MissingDependencyError: If Optuna or LightGBM is not installed.
    """
    try:
        import lightgbm as lgb
        import optuna
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError(
            "optuna and lightgbm are required; install the 'fit' extra"
        ) from exc

    folds = _season_folds(seasons)

    def build(params: dict[str, Any]) -> Any:
        return lgb.LGBMRegressor(random_state=seed, verbose=-1, **params)

    def objective(trial: Any) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 3, 31),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 40),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        score, _ = _cross_validated_error(lambda: build(params), features, target, folds)
        return score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials, show_progress_bar=False)

    best = study.best_params
    rmse, errors = _cross_validated_error(lambda: build(best), features, target, folds)
    return BaselineResult(
        name="lightgbm", rmse=rmse, squared_errors=errors, best_params=best, trials=trials
    )


def run_baselines(
    features: pd.DataFrame,
    target: pd.Series,
    seasons: pd.Series,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    experiment: str | None = DEFAULT_EXPERIMENT,
) -> list[BaselineResult]:
    """Tune and score both baselines, optionally recording the runs in MLflow.

    Args:
        features: One column per metric, indexed by team-season.
        target: Next season's net rating.
        seasons: Season each row belongs to.
        trials: Optuna trials per baseline.
        seed: Seed for the samplers.
        experiment: MLflow experiment name, or ``None`` to skip tracking.
            Skipping is offered so a test does not write to a tracking store.

    Returns:
        One :class:`BaselineResult` per baseline, ordered best first.
    """
    results = [
        tune_ridge(features, target, seasons, trials=trials, seed=seed),
        tune_lightgbm(features, target, seasons, trials=trials, seed=seed),
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
                    mlflow.log_param("features", len(features.columns))
                    mlflow.log_param("observations", int(target.notna().sum()))
                    mlflow.log_metric("rmse", result.rmse)

    return sorted(results, key=lambda item: item.rmse)
