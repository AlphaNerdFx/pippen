# ADR 0004: Reliability bounds a metric's loading and never becomes its weight

- Status: Accepted
- Date: 2026-09-15
- Deciders: AlphaNerdFx

## Context

The project exists to account for metric reliability, and the plan named the
mechanism. Classical measurement theory gives error variance proportional to
`1 - r`, so combining noisy estimates by inverse-variance weighting gives each
metric a weight of `r / (1 - r)`. That is the standard method in meta-analysis
and it is what the project was going to do.

Reliability was then measured rather than assigned, across all 25 hoopR seasons
at a 500-minute floor. Applying the intended weight to the measured values:

| Metric | Reliability | Weight `r / (1 - r)` |
|---|---|---|
| Three-point rate | 0.992 | 122.1 |
| Possessions ended per 36 | 0.984 | 60.4 |
| Assists per 36 | 0.982 | 56.1 |
| Points per 36 | 0.967 | 28.9 |
| RAPM, three seasons | 0.796 | 3.9 |
| True shooting | 0.746 | 2.9 |
| Effective field goal | 0.728 | 2.7 |

Three-point rate would count 31 times more than three-season RAPM. Three-point
rate describes shot selection and says nothing about whether a player helps his
team win.

That is not a quirk of one metric. Correlating each standardised metric against
three-season RAPM over 435 players in NBA 2016-17 to 2018-19, reliability
correlates with the absolute correlation against RAPM at **r = -0.564, p =
0.029** across fifteen metrics. True shooting has the strongest relationship
with impact in the set and the lowest reliability of any of them. Three-point
rate has the highest reliability and no relationship at all, -0.004.

The rank version is weaker, rho = -0.404 at p = 0.136, so the effect leans on
the extremes rather than holding evenly down the table.

The mechanism is not mysterious. The most repeatable box-score quantities
describe style: how often a player shoots, from where, how many rebounds his
position brings him. Style is stable by construction, because it is mostly role
and body type. Impact depends on efficiency and decision quality, which vary
more and matter more.

So a reliability-weighted average of these metrics would be worse than an
unweighted one, because it would systematically upweight the metrics with least
to say about winning.

## Decision

Reliability sets a ceiling on how much of a metric the model may attribute to
the latent quantity. It never sets the contribution.

Each column is standardised to unit variance, so with `Var(theta) = 1` the
residual scale is determined rather than free:

    sigma_m = sqrt(1 - sum_k beta_mk^2)

Classical test theory splits a standardised metric's variance into a reliable
share `r_m` and an unreliable share `1 - r_m`. Whatever tracks the latent
quantity has to come out of the reliable share, so:

    sum_k beta_mk^2 <= r_m

A metric that disagrees with itself cannot be strong evidence about anything. A
metric that agrees with itself perfectly is permitted to load fully, and whether
it does is estimated from the data. Three-point rate is allowed a loading up to
0.996 and the data gives it almost nothing.

The rule is enforced structurally rather than documented. No function in
`pippen.reliability.testretest` returns `r / (1 - r)`, and a test asserts that no
public name in the module contains "weight".

## Consequences

**Gained: a metric cannot be trusted beyond what its own measurement supports**,
and that bound comes from data rather than from judgement.

**Gained: the failure mode is unreachable rather than warned about.** The moment
a function named `weight_for_metric` exists, something calls it, and the
resulting model ranks scoring volume above impact with no test failing.

**Cost: the fusion model becomes harder to fit.** Loadings and residual scales
must be estimated jointly, which needs an anchor whose loading is fixed for
identifiability. That is ADR 0005.

**Cost: the project's name is now slightly misleading.** PIPPEN stands for
Player Impact from Pooled Priors and Estimated Noise, and the estimated noise no
longer becomes a weight. The name stays because it is published on PyPI.

**Noted: this decision is what the measurements forced, and the measurements
could change.** A metric set with better inputs, tracking-derived rather than
box-score-derived, might not show the same negative relationship. The bound
would still be correct; the argument against weighting would weaken.
