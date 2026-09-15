"""Which metrics a fitted model actually uses, and whether two models agree.

What this is for
----------------
The fusion model reports a loading per metric, which is its claim about how
much of each metric is the latent quantity. The supervised baselines make no
such claim; they just predict. SHAP recovers an equivalent claim from them: how
much each metric moved each prediction.

Putting the two side by side is the point. The fusion's loadings come from the
metrics' shared structure, fitted without ever seeing the target. The SHAP
importances come from fitting the target directly. Two routes to the same
question, and agreement between them is evidence that neither is an artefact of
its own machinery.

What SHAP is
------------
A Shapley value, from 1953 cooperative game theory, divides a group's payoff
among its members by averaging each member's marginal contribution over every
order in which the group could have formed. It is the unique division satisfying
a short list of fairness properties, which is why it survived from economics
into model explanation.

SHAP applies that to one prediction: the players are the input features, the
payoff is the prediction minus the average prediction, and each feature's share
is its attribution. Averaging the magnitude over many predictions gives an
importance ranking that, unlike a tree's split counts, is comparable across
models and does not inflate features with many possible split points.

The caveat that matters here
----------------------------
SHAP explains the model, not the world. A feature can carry a large attribution
because it genuinely drives the outcome or because it stands in for something
the model was not given. With metrics that correlate as strongly as these do,
attribution spreads across a correlated group somewhat arbitrarily, and a
metric's share can move between runs without anything real changing. The
importances are read as a ranking of groups rather than as a precise split
between members of one group.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import pandas as pd

from pippen.errors import MissingDependencyError
from pippen.repro import DEFAULT_SEED

#: Rows sampled when explaining a large table. SHAP cost grows with rows, and
#: an importance ranking stabilises long before every row is used.
DEFAULT_SAMPLE: Final = 500


@dataclass(frozen=True)
class AttributionResult:
    """How much each metric moved the model's predictions.

    Attributes:
        importance: One row per metric with ``mean_abs_shap``, the average
            magnitude of its attribution, and ``mean_shap``, the signed
            average, which says whether the metric usually pushes predictions
            up or down.
        rows_explained: Observations the attributions were computed over.
        base_value: The model's average prediction, which every attribution is
            measured relative to.
    """

    importance: pd.DataFrame
    rows_explained: int
    base_value: float

    def describe(self) -> str:
        """Return a one-line summary naming the three strongest metrics."""
        top = ", ".join(self.importance.head(3)["metric"])
        return (
            f"{self.rows_explained} rows explained, base value {self.base_value:+.2f}, "
            f"strongest: {top}"
        )

    def agreement_with(self, loadings: pd.DataFrame) -> float:
        """Return the rank correlation with a fusion model's loadings.

        Compares this model's importance ranking against the magnitude of the
        fusion's loadings over the metrics both cover. A high value says the
        two routes picked out the same metrics despite one never seeing the
        target.

        Args:
            loadings: A fusion fit's loadings table, with ``metric`` and
                ``loading``.

        Returns:
            Spearman correlation between mean absolute SHAP and absolute
            loading, or ``nan`` when fewer than three metrics overlap.
        """
        mine = self.importance.set_index("metric")["mean_abs_shap"]
        theirs = loadings.set_index("metric")["loading"].abs()
        shared = sorted(set(mine.index) & set(theirs.index))
        if len(shared) < 3:
            return float("nan")
        return float(mine.loc[shared].corr(theirs.loc[shared], method="spearman"))


def explain(
    model: Any,
    features: pd.DataFrame,
    *,
    sample: int = DEFAULT_SAMPLE,
    seed: int = DEFAULT_SEED,
) -> AttributionResult:
    """Attribute a fitted model's predictions across its inputs.

    Args:
        model: A fitted tree model, such as the LightGBM baseline.
        features: The table it was fitted on.
        sample: Maximum rows to explain. Sampled without replacement when the
            table is larger.
        seed: Seed for that sample.

    Returns:
        An :class:`AttributionResult`.

    Raises:
        MissingDependencyError: If SHAP is not installed.
        ValueError: If ``features`` is empty.
    """
    try:
        import shap
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError("shap is required; install the 'fit' extra") from exc

    if features.empty:
        raise ValueError("no rows to explain")

    if len(features) > sample:
        rng = np.random.default_rng(seed)
        chosen = rng.choice(len(features), size=sample, replace=False)
        explained = features.iloc[np.sort(chosen)]
    else:
        explained = features

    explainer = shap.TreeExplainer(model)
    values = np.asarray(explainer.shap_values(explained))

    importance = (
        pd.DataFrame(
            {
                "metric": list(features.columns),
                "mean_abs_shap": np.abs(values).mean(axis=0),
                "mean_shap": values.mean(axis=0),
            }
        )
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )

    base = explainer.expected_value
    return AttributionResult(
        importance=importance,
        rows_explained=len(explained),
        base_value=float(np.ravel(base)[0]),
    )
