# 0007: The API serves shipped tables, and publishes no per-player interval

Status: accepted
Date: 22 September 2026
Deciders: maintainer

## Context

Phase 5 says the serving layer is done when "a public URL returns a player's
estimate with its interval". The estimate exists. The interval does not, and
building one from what this project has would mean publishing a number the
project has already documented as misleading.

`rapm_ratings.parquet` carries `offensive`, `defensive`, `total`, `possessions`
and `alpha`. It carries no standard error and no credible interval, because
Phase 2 removed the only candidate.

### Why there is no interval to serve

`bootstrap_standard_errors` in `src/pippen/rapm/ridge.py` still exists and still
works. Phase 2 stopped using it as a gate after measuring what it actually
tracks: the standard error on a ridge coefficient **rises** with possessions,
correlation +0.79. Shrinkage, not information. A player with few possessions is
pulled hard toward zero, and a coefficient pinned near zero by the penalty has
little room to vary across bootstrap resamples, so it reports a small standard
error precisely where the data is thinnest. [ADR 0003](0003-phase-2-gate-changed.md)
records the replacement criterion.

Serving that as "the interval" would invert the meaning a reader expects: the
narrowest bars would sit on the least-supported players.

The fusion model does produce calibrated intervals, 90.9 percent coverage at a
nominal 90. Two reasons it cannot fill this gap. Its intervals are a floor on
the true uncertainty, because pinning the anchor also pins its residual scale,
which `docs/methodology/calibration.md` names as unfixed. And the fusion is
fitted from the `fit` extra at runtime over data that is not shipped, so a
service installed from the wheel cannot produce them.

## Alternatives

Ship bootstrap standard errors as an interval. Rejected. The project measured
them to be anti-correlated with information and changed a phase gate over it.
Publishing them anyway, in the one artifact a stranger will actually consume,
would contradict the finding this repository exists to report honestly.

Compute the fusion at request time. Rejected. It requires numpyro, jax and the
unshipped fusion dataset, which turns a static file server into a training job
and puts the `fit` extra on the critical path of every request.

Derive an interval from the measured reliability of 0.796. Rejected. Reliability
bounds how much of a metric is signal across a population. It does not give a
per-player standard error, and treating a population scalar as one would be
inventing statistics. [ADR 0004](0004-reliability-bounds-never-weights.md) draws
the same line for weighting.

Delay Phase 5 until an honest interval exists. Rejected for now. The serving
layer has value without it, and the work to produce a defensible per-player
interval is a research task rather than an engineering one.

## Decision

The API serves the shipped tables and nothing computed at request time.

Each rating response carries `total`, `offensive`, `defensive`, `possessions`,
and the measured split-half reliability of RAPM at 0.796. It carries no
interval field. The absence is documented in the response schema and in the
endpoint's own description rather than left for a reader to notice.

`possessions` is the honest per-player precision signal this project can stand
behind: it is the sample size behind the estimate, it moves the right way, and
it needs no modelling assumption.

Phase 5's done-when is amended in `TODO.md` to match, with a pointer here.

## Consequences

**Gained:** a service that installs from the core wheel with no `fit` extra, no
model loading, and no per-request computation. Responses are a filtered read of
a 228 KB table, so the free-tier cold start is dominated by process boot rather
than by numpyro importing jax. The claim the API makes is one the project can
defend line by line.

**Accepted:** the headline Phase 5 outcome is not met as originally written, and
a consumer who wants uncertainty gets a sample size and a population reliability
rather than a per-player band. That is a real reduction in what the endpoint
offers, and it is recorded here rather than smoothed over in the response
schema.

**Reopened by:** a per-player interval that survives the Phase 2 critique. The
most likely route is the hierarchical posterior over players, once the anchor
problem in `docs/methodology/calibration.md` is fixed and the fusion output is
shipped alongside the RAPM table.
