# Code review, Phase 3 closeout

Two-axis review of `git diff f6f4e27...HEAD`, run 15 September 2026.

Scope: `src/pippen/model/attribution.py`, `baselines.py`, `calibration.py` (all
new), an 18-line addition to `fusion.py` exposing posterior draws, their tests,
and the accompanying methodology docs. 1,500 diff lines.

Written down because both axes ran as sub-agents whose reports existed only in
one conversation. The correction in the Spec axis below reversed one of its own
conclusions, and that reversal is the single most useful thing here, so losing
it to a compaction would have been expensive.

Not an issue tracker. This is the record of what was found and what was decided
about it. Items marked open are real work.

---

## Standards axis

### Documented-standard breaches

| # | Standard | Where | Status |
|---|---|---|---|
| S1 | `CLAUDE.md` > Writing Style > no contrast-reveal construction | Six places, listed below | Closed, plus five more found outside the diff |
| S2 | `CLAUDE.md` > Writing Style > bold sparingly | `docs/guides/licensing.md`, 11 bold spans in 58 lines | Closed, reduced to 1 |
| S3 | `CLAUDE.md` > Writing Style > no filler openers | `claim-under-test.md`: "and it is worth being precise about what could move it" | Closed |
| S4 | `CLAUDE.md` > Development Workflow > record significant decisions as ADRs | Only 0001 and 0002 exist | Closed, ADRs 0003-0005 |

S1 in full, all of it written by the model that also wrote the rule:

- `docs/methodology/claim-under-test.md` heading: `## It is not the fusion that failed, it is the inputs`
- same file: `the ceiling is a property of these inputs, not of the method used to combine them`
- `docs/methodology/calibration.md` heading: `## The anchor is the exception, and it is not an accident`
- same file: `Checking the rating's interval against the truth is not hard here, it is undefined`
- `src/pippen/model/calibration.py` docstring, the same sentence reworded
- `tests/unit/test_baselines.py` docstring: `The risk here is not that a model fails to fit. It is that the comparison is unfair...`
- `CLAUDE.md` status block: `so the ceiling belongs to the inputs rather than to the method`, and `Box-score metrics are dominated by position, not impact`

No em dashes anywhere in the diff.

### Judgement calls

| # | Smell | Where | Status |
|---|---|---|---|
| S5 | Duplicated Code | `tune_ridge` and `tune_lightgbm` repeat seven identical steps | Closed, one `tune` helper |
| S6 | Duplicated Code | `MissingDependencyError` declared five times as five distinct types | Closed, `pippen/errors.py` |
| S7 | Shotgun Surgery | `DEFAULT_SEED = 20260910` in three new modules while `repro.py` already owns it, six files total | Closed, imported from `repro` |
| S8 | Feature Envy | `check_calibration` rebuilds `FusionDataset` field by field | Closed, `FusionDataset.with_values` |
| S9 | Data Clumps | `(features, target, seasons)` plus `trials, seed` travel together through four functions | Closed, `TeamPanel` |
| S10 | Primitive Obsession | `CalibrationResult.direction` returns a bare `str` | Closed, `Verdict` literal |
| S11 | Loose signature | `**fit_kwargs: object` forces a `type: ignore[arg-type]` | Closed, explicit parameters |
| S12 | Test reaches into private | `tests/unit/test_baselines.py` imports `_season_folds` | Closed, `TeamPanel.folds` is public |

---

## Spec axis

Spec source: `TODO.md` > Phase 3, including its "Done when" gate. No issue
tracker exists in this repo.

### Implemented but wrong

**P1. Optuna tunes on the folds it reports.** Closed by making the code true
rather than the docstring. Selection is now nested: an inner leave-one-season
search over the training seasons only, with the outer season scored once.

**The reviewer's correction was itself too optimistic, and the rerun shows why.**
The pure-noise control measured 0.00 to 0.03 RMSE of selection bias and
concluded the published numbers would stand. They moved by up to 0.215, because
nesting removes the bias and also leaves each fold less data to tune on. The
control isolated the first effect and not the second.

| Figure | Reported | Nested |
|---|---|---|
| Ridge, all candidates | 4.436 | 4.521 |
| LightGBM, all candidates | 4.418 | 4.633 |
| LightGBM, box score only | 4.492 | 4.633 |
| Ridge, box score only | 4.670 | 4.685 |

Consequence: the claim "combining does work, within the box score" is
**withdrawn**. Tested with a paired test it does not hold, 4.633 against
4.683 at p = 0.746. The headline conclusion is unaffected and strengthened.

**Corrected by the reviewer, and this is the important part.** The bias was
measured rather than assumed: 180 rows, 17 informationless features, 6 folds,
40 trials, through the committed `tune_*`. On pure noise any RMSE below the
target sd is selection bias and nothing else.

| seed | target sd | lgbm tuned | ridge tuned |
|---|---|---|---|
| 0 | 4.595 | 4.594 | 4.617 |
| 1 | 4.305 | 4.319 | 4.296 |
| 2 | 4.503 | 4.479 | 4.473 |

Optimism is 0.00 to 0.03 RMSE. The selection statistic averages 180 held-out
observations across six folds, and 40 trials in a conservative space are highly
correlated, so the minimum over trials barely moves.

Consequences:

- RAPM 4.381 against LightGBM 4.418: the bias favours LightGBM and it still
  lost, so `p = 0.742` is more robust than was claimed, not less.
- "Combining does work, within the box score", 4.492 against 4.684: a 0.03 bias
  cannot explain a 0.192 gap. The reviewer withdrew "unsupported".

What survives is narrower: the docstring is false, which is a latent hazard
because widening the search space or trial budget would grow the bias. Reviewer's
own caveat: pure noise maximises the variance of the selection statistic, so it
is the right stress case, but it is one configuration at n=180.

**P2.** Closed. Imputation moved inside the ridge pipeline, so it is fitted on the
training split of each fold rather than over the whole panel.

**P3.** Closed. `TeamPanel.build` drops rows with no target once, so both
modules score identical rows by construction rather than by comment.

**P4.** Closed, documentation only. `claim-under-test.md` now states that
"out of sample" here means held-out rather than strictly forward-looking, since
a model predicting 2019 may have trained on 2022.

### Verified correct, do not revisit without new evidence

- `einsum("dpk,dmk->dpm")` contracts the factor axis correctly.
- `scale[:, None, :]` matches the likelihood `dist.Normal(expected, scale[None, :])`
  exactly, so the posterior predictive counts parameter and residual uncertainty
  once each. Neither double-counted nor under-counted.
- `fit_fusion` never re-standardises, so checking `values.to_numpy()` at `hidden`
  is valid, and `observed_mask = np.isfinite` keeps masked cells out of the fit.
- `expected_value` is correct for `LGBMRegressor`; row sampling is unbiased and
  never triggered at 180 rows.
- `keep_draws` is purely additive after `mcmc.run`. No fitted result changes.

Residual, second order: `centres` and `scales` are computed before masking, so
standardisation saw held-out values.

### Spec gaps

**P5.** Closed. `pippen.model.study` owns the pipeline and `pippen evaluate`
runs it, so every table on the page comes from one command. `BaselineResult`
carries the fitted estimator, and attribution falls back to the best baseline
SHAP can explain rather than producing nothing when a linear model wins.

**P6.** Closed. The table now names the hold-out fraction, factor count,
sampler settings and seed.

**P7.** Closed by recording rather than by unticking. Read literally the
criterion asks for aggregate coverage, which passes at 90.9 percent, so the box
is correctly ticked. The criterion was weaker than it should have been: it says
nothing per metric, and per metric the anchor covers at 0.703. `TODO.md` now
records that a future version of this gate should require per-metric coverage.

**P8.** Closed. `calibration.md` now explains both counts: 15 box-score metrics
plus RAPM plus the fused rating makes 17 candidates in the claim, while the
calibration table covers the 16 model columns minus one that had no value hidden
in that draw.

### Scope creep

**P9.** `docs/guides/licensing.md` and its nav entry are not Phase 3 items.
Minor and defensible. No action.

---

## Summary

Standards: four documented-standard breaches, eight judgement calls. All closed.
Worst was a contrast-reveal construction used as a section heading, in a rule
the same author wrote. Fixing it surfaced five more instances in files outside
the diff, also fixed. ADR 0001 was left alone; the index says records are never
edited once accepted.

Spec: nine findings, all closed or recorded. Worst was P5, a published table no
committed code path could regenerate. Closing P1 then changed a published
result: with nested selection the claim that combining box-score metrics beats
the best single one does not hold, and it is withdrawn in
`docs/methodology/claim-under-test.md` with the old figures kept beside the new
ones.

The review paid for itself on P1 alone. The finding was raised, measured,
partly withdrawn by its own author, and then found to be larger than either the
original claim or the withdrawal. No single pass got it right.
