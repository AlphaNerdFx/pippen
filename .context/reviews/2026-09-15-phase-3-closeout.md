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
| S1 | `CLAUDE.md` > Writing Style > no contrast-reveal construction | Six places, listed below | Open |
| S2 | `CLAUDE.md` > Writing Style > bold sparingly | `docs/guides/licensing.md`, 11 bold spans in 58 lines | Open |
| S3 | `CLAUDE.md` > Writing Style > no filler openers | `claim-under-test.md`: "and it is worth being precise about what could move it" | Open |
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
| S5 | Duplicated Code | `tune_ridge` and `tune_lightgbm` repeat seven identical steps | Open |
| S6 | Duplicated Code | `MissingDependencyError` declared five times as five distinct types | Open |
| S7 | Shotgun Surgery | `DEFAULT_SEED = 20260910` in three new modules while `repro.py` already owns it, six files total | Open |
| S8 | Feature Envy | `check_calibration` rebuilds `FusionDataset` field by field | Open |
| S9 | Data Clumps | `(features, target, seasons)` plus `trials, seed` travel together through four functions | Open |
| S10 | Primitive Obsession | `CalibrationResult.direction` returns a bare `str` | Open |
| S11 | Loose signature | `**fit_kwargs: object` forces a `type: ignore[arg-type]` | Open |
| S12 | Test reaches into private | `tests/unit/test_baselines.py` imports `_season_folds` | Open |

---

## Spec axis

Spec source: `TODO.md` > Phase 3, including its "Done when" gate. No issue
tracker exists in this repo.

### Implemented but wrong

**P1. Optuna tunes on the folds it reports.** `objective` calls
`_cross_validated_error(..., folds)` over the same folds that produce the
returned `rmse`. The module docstring asserts the opposite: "Hyperparameters are
selected inside the training folds, never against the held-out season."
`claim-under-test.md` repeats the claim. Open.

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

**P2.** `filled = features.fillna(features.mean())` computes column means over
held-out rows. A leak, small, ridge only. Open.

**P3.** `_cross_validated_error` has no `target.notna()` guard, unlike
`claim.py`. The docstring's "The same folds as the claim" is false for rows with
an undefined next season. Open.

**P4.** `_season_folds` cannot leak a season, confirmed by test. But training
folds contain features measured during the held-out row's target season. Shared
by both modules so the comparison stays fair, yet "out of sample" is optimistic.
Open, documentation only.

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

**P5.** Nothing outside tests calls `run_baselines`, `tune_*` or `explain`, and
there is no CLI command. `BaselineResult` carries no fitted estimator, so the
documented SHAP table cannot be produced from `tune_lightgbm` at all.
`claim-under-test.md`'s "Reproduce with `pippen.model.claim`" is false for the
baseline and SHAP sections. **Worst finding on this axis.** Open.

**P6.** `calibration.md`'s 50/80/90 table names no seed, `hold_out`,
`n_factors` or sampler settings. Open.

**P7.** Phase 3's Done-when says the intervals are calibrated. The same commit's
documentation says RAPM covers 0.703, the intervals are "a floor rather than a
faithful estimate", and the fix is "not yet applied". The box was ticked over
the documentation's own caveat. Open, and it is a process finding rather than a
code one.

**P8.** Metric count drift: `claim-under-test.md` says 17, `calibration.md`'s
table totals 15. Open.

### Scope creep

**P9.** `docs/guides/licensing.md` and its nav entry are not Phase 3 items.
Minor and defensible. No action.

---

## Summary

Standards: four documented-standard breaches, eight judgement calls. Worst is a
contrast-reveal construction used as a section heading, in a rule the same
author wrote.

Spec: nine findings. Worst is P5, a published table no committed code path can
regenerate, which is the failure mode this project has been most careful about
everywhere else.
