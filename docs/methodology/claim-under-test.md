# The claim under test

The question this project committed to answering, stated before the model was
built and reported whichever way it came out.

> Does a reliability-aware fusion of public metrics predict a team's **next**
> season net rating better than any single one of its inputs does?

**The answer is no, and the more precise answer is that the fusion is
indistinguishable from RAPM alone.**

## The result

Six leave-one-season-out folds, 180 team-seasons, NBA 2018-19 through 2023-24.
Every candidate goes through the same aggregation, the same model class and the
same folds, so the only thing that differs is which player rating goes in.

| Candidate | RMSE | vs best |
|---|---|---|
| **RAPM, three-season** | **4.381** | 0.000 |
| Fusion, two factors | 4.482 | +0.101 |
| True shooting | 4.684 | +0.303 |
| Effective field goal | 4.710 | +0.329 |
| Points per 36 | 4.810 | +0.429 |
| Assists per 36 | 4.822 | +0.441 |
| Defensive rebounds per 36 | 4.902 | +0.522 |
| Possessions ended per 36 | 4.948 | +0.567 |
| Free throw percentage | 4.949 | +0.568 |
| Three-point rate | 4.951 | +0.570 |
| Turnovers per 36 | 4.981 | +0.600 |
| Offensive rebounds per 36 | 4.984 | +0.603 |
| Rebounds per 36 | 5.005 | +0.624 |
| Fouls per 36 | 5.006 | +0.626 |
| Free throw rate | 5.009 | +0.627 |
| Blocks per 36 | 5.024 | +0.643 |
| Steals per 36 | 5.029 | +0.647 |

## Is the gap real?

An RMSE table on its own invites crowning whichever number is smallest.
Every candidate is scored on the same team-seasons, so their squared errors are
paired and the difference can be tested rather than eyeballed.

| Comparison | RMSE gap | Paired t | p |
|---|---|---|---|
| RAPM vs fusion | +0.101 | 1.37 | 0.171 |
| RAPM vs true shooting | +0.303 | 2.34 | 0.021 |
| RAPM vs points per 36 | +0.429 | 3.38 | 0.001 |

So RAPM's margin over the best box-score metrics is real, and its margin over
the fusion is not. The fusion does not beat RAPM, and it is not detectably
worse either.

One of the six windows, 2021-22 to 2023-24, had a sampler that did not
converge, and it is also the window containing the season whose archive has a
[seven-week hole](data-quirks.md). Dropping it leaves 150 team-seasons and
strengthens the same conclusion rather than changing it: RMSE 4.262 for RAPM
against 4.286 for the fusion, a gap of 0.023 at p = 0.722.

## It is not the fusion that failed, it is the inputs

A negative result for one way of combining metrics is not a negative result for
every way of combining them, so two supervised baselines were fitted over every
metric at once: ridge, and gradient-boosted trees. Both tuned with Optuna over
forty trials each, on the same folds, with hyperparameters selected inside the
training folds and never against the held-out season.

| Model | Inputs | RMSE |
|---|---|---|
| **RAPM alone** | 1 | **4.381** |
| LightGBM | all 17 | 4.418 |
| Ridge | all 17 | 4.436 |
| Fusion, two factors | 17 | 4.482 |
| LightGBM | 15 box-score only | 4.492 |
| Ridge | 15 box-score only | 4.670 |
| Best single box-score metric | 1 | 4.684 |

LightGBM over everything against RAPM alone: paired t = −0.33, p = 0.742. Not
distinguishable, same as the fusion.

Two things follow, and the second is the more useful.

**Combining does work, within the box score.** LightGBM over the fifteen
box-score metrics scores 4.492 against 4.684 for the best single one. The
metrics genuinely carry complementary information about each other.

**It just does not get past RAPM.** A latent-variable model, a penalised linear
model and a tuned gradient booster all land within a tenth of a point of RAPM
alone, from three quite different directions. That is much stronger evidence
than the fusion result on its own: the ceiling is a property of these inputs,
not of the method used to combine them.

## Which metrics the models actually use

SHAP attributions on the tuned LightGBM, over the same team-seasons. A Shapley
value divides a prediction among its inputs by averaging each input's marginal
contribution over every order the inputs could have been added in.

| Metric | Mean absolute SHAP |
|---|---|
| RAPM | 0.965 |
| Effective field goal | 0.867 |
| Turnovers per 36 | 0.384 |
| Fouls per 36 | 0.267 |
| Offensive rebounds per 36 | 0.248 |
| Points per 36 | 0.193 |
| ...the remaining ten | 0.025 to 0.177 |

RAPM dominates, which is expected. The second row is the interesting one:
effective field goal percentage is the single box-score metric that carries
material information *beyond* RAPM. That agrees with everything else here,
since shooting efficiency is the box-score quantity most related to impact.

The attributions agree with the fusion's loadings only weakly, Spearman 0.259,
and the disagreement is not a contradiction. The two are answering different
questions. A loading says how much of a metric is the latent quantity, fitted
without ever seeing the target. A SHAP value says how much a metric moved a
prediction *given the other metrics were also available*, so a metric whose
information RAPM already carries gets little credit no matter how strongly it
correlates with impact. Points per 36 has a loading of 0.739 and a SHAP of
0.193 for exactly that reason.

## Why this is the expected answer in hindsight

Nothing about this contradicts the rest of the project. It is what the earlier
measurements were already saying.

The box-score metrics are dominated by position. A one-factor model of them
recovers size, not impact, which is recorded in
`pippen.model.fusion`. Their shared structure is mostly a fact about how tall a
player is and what he is asked to do.

The part of the box score that does relate to impact is the part that is
measured worst. True shooting has the strongest correlation with RAPM of any
box-score metric here and the lowest reliability of any of them, and across all
fifteen [reliability runs against validity](measured-reliability.md) at
r = −0.564.

And RAPM already measures impact directly, from the scoreboard, with the
players controlled for. Asking what fifteen noisy, position-laden proxies can
add to that is a fair question, and the answer on this data is: nothing
detectable.

## What would change the answer

This is a result about these inputs, this target and this window, and it is
worth being precise about what could move it.

- **Better inputs.** The box score contains no tracking data, no shot quality,
  no defensive matchups. Metrics built from those might carry impact signal the
  box score cannot. A location-only shot-quality model was built and rejected;
  [licensing](../guides/licensing.md) records why, and names defender-distance
  tracking as the version worth doing.
- **More seasons.** Six folds and 180 team-seasons is a small sample for
  detecting a difference of a tenth of a point. A gap this size would need
  roughly four times the data to resolve. The nine seasons of possession data
  available are the binding constraint, and
  [data quirks](data-quirks.md) records why there are not more.
- **A different target.** Next-season team net rating is coarse: it folds in
  roster turnover, injury and coaching, none of which any player rating knows
  about. A player-level target would be sharper, and there is no unlicensed one.
- **Low-minute players.** The fusion's value should be largest where RAPM is
  weakest, which is players with few possessions. Aggregating to team level by
  minutes is precisely the operation that hides that, because those players
  carry little weight. A test aimed at them specifically has not been run.

## What this does not say

It does not say the fusion is useless. It says it does not beat its anchor at
this particular prediction, on this much data. The measured reliability table,
the RAPM itself, and the finding that reliability opposes validity all stand on
their own and none of them depended on this outcome.

It also does not say reliability weighting works. The project never tested that
version, because [the measurements ruled it out first](measured-reliability.md):
weighting by `r / (1 - r)` would have given three-point rate 122 and
three-season RAPM 3.9.

Reproduce with `pippen.model.claim`. The per-observation squared errors are
written to `data/processed/claim_squared_errors.parquet` so the paired tests
can be rerun without refitting.
