"""Reliability-adjusted NBA player impact estimates with calibrated uncertainty.

What this package ships
-----------------------
Regularized Adjusted Plus-Minus computed from public play-by-play, for NBA
2016-17 through 2024-25, validated at Spearman 0.914 against an independently
built stint dataset. Alongside it, the measured split-half reliability of 15
box-score metrics across 25 seasons, and the possession coefficient measured per
season rather than assumed at 0.44.

Those tables are bundled, so an install is immediately useful without the hours
of rate-limited downloading the pipeline needs to rebuild them. The `pippen`
command-line tool rebuilds everything from source data for anyone who wants to.

What the name promises, and what the measurements found
-------------------------------------------------------
PIPPEN stands for Player Impact from Pooled Priors and Estimated Noise, and the
plan was to fuse public metrics by weighting each one by its reliability. The
measurements ruled that out. Reliability runs *against* validity across this
metric set, correlating -0.564 with correlation against RAPM, so weighting by
`r / (1 - r)` would have counted three-point rate 31 times more heavily than
three-season RAPM while three-point rate has no relationship with winning at
all.

Reliability therefore bounds how much of a metric the model may attribute to the
latent quantity and never becomes its weight. See
`docs/architecture/decisions/0004-reliability-bounds-never-weights.md`.

The fusion model exists, is calibrated, and does not beat RAPM alone. That
result is published rather than buried, in
`docs/methodology/claim-under-test.md`.

Public API
----------
Three functions read the bundled tables and need nothing beyond the core
dependencies:

- :func:`rapm_ratings` for player impact per three-season window
- :func:`metric_reliability` for the measured reliability of each metric
- :func:`possession_coefficient` for the measured share of free throws that
  consume a possession

Everything else is internal and may change without a major version bump.
"""

from __future__ import annotations

from pippen.published import (
    FIRST_RAPM_SEASON,
    LAST_RAPM_SEASON,
    metric_reliability,
    possession_coefficient,
    rapm_ratings,
)

__version__ = "1.0.0"

__all__ = [
    "FIRST_RAPM_SEASON",
    "LAST_RAPM_SEASON",
    "__version__",
    "metric_reliability",
    "possession_coefficient",
    "rapm_ratings",
]
