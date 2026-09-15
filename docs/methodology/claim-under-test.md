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

## No way of combining these metrics beats RAPM alone

A negative result for one way of combining metrics is not a negative result for
every way, so two supervised baselines were fitted over every candidate at once:
ridge, and gradient-boosted trees. Both tuned with Optuna, both on the same
season folds, with hyperparameters selected by an inner search over the training
seasons only and the held-out season scored once.

| Model | Inputs | RMSE |
|---|---|---|
| **RAPM alone** | 1 | **4.381** |
| Fusion, two factors | 17 | 4.482 |
| Ridge | all 17 | 4.521 |
| LightGBM | all 17 | 4.633 |
| LightGBM | 15 box-score only | 4.633 |
| Best single box-score metric | 1 | 4.683 |
| Ridge | 15 box-score only | 4.685 |

A latent-variable model, a penalised linear model and a tuned gradient booster
all land at or behind RAPM alone, from three quite different directions. The
ceiling belongs to these inputs rather than to any one method of combining them.

### A correction to an earlier version of this page

An earlier version of this table reported 4.436 for ridge and 4.418 for
LightGBM, and claimed on that basis that "combining does work, within the box
score", 4.492 against 4.684.

Both numbers came from a search that selected hyperparameters on the same folds
it reported. The selection bias that introduces was measured on a pure-noise
control at 0.00 to 0.03 RMSE, which suggested the numbers would barely move. The
numbers moved by up to 0.215, because proper nesting removes the bias and also
leaves each fold less data to tune on. The old figures were optimistic and this
page previously presented them as out-of-sample.

**The claim that combining box-score metrics beats the best single one is
withdrawn.** Tested properly it does not hold: LightGBM over fifteen box-score
metrics scores 4.633 against true shooting's 4.683, a gap of 0.050 at paired
t = 0.32, p = 0.746. Combining fifteen box-score metrics is indistinguishable
from using true shooting on its own.

The headline conclusion is unaffected and slightly strengthened, since LightGBM
now loses to RAPM by 0.25 rather than by 0.04.

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

This result covers these inputs, this target and this window. Four things could
move it.

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

One limit of the folds is worth stating plainly. Splitting by season stops a
model seeing the rest of a season it is predicting, and it does not stop the
training folds containing seasons *later* than a held-out row's target. A model
predicting 2019 from 2018 may have trained on 2022. Every candidate faces the
same arrangement so the comparison stays fair, but "out of sample" here means
held-out rather than strictly forward-looking, and a genuine forecasting test
would be stricter.

## What this does not say

It does not say the fusion is useless. It says it does not beat its anchor at
this particular prediction, on this much data. The measured reliability table,
the RAPM itself, and the finding that reliability opposes validity all stand on
their own and none of them depended on this outcome.

It also does not say reliability weighting works. The project never tested that
version, because [the measurements ruled it out first](measured-reliability.md):
weighting by `r / (1 - r)` would have given three-point rate 122 and
three-season RAPM 3.9.

Reproduce with `pippen evaluate --seasons 2016-2024 --window 3`. Every table on
this page comes from that one command. An earlier version of this page said the
results reproduced from `pippen.model.claim`, which was false: the tables came
from scripts outside the package, and the model that produced the SHAP table was
discarded rather than returned.
