# Are the intervals the width they claim?

The project's output is a rating with an interval, and an interval is a claim.
A 90 percent interval says the truth falls inside it nine times in ten. A model
can rank players perfectly and still make that claim falsely.

Phase 3 required roughly 90 percent coverage before the model counted as done.

## What is actually testable

The obvious test cannot be run. The latent quantity has no observed value to
compare against, ever, which is what makes it latent. Checking the rating's
interval against the truth is undefined here rather than merely difficult.

What is observable is the metrics. So 15 percent of the observed metric values
are hidden, the model is fitted to the rest, and each hidden value is checked
against the interval the fitted model predicts for it. If the loadings, the
residual scales or the latent values were over-confident, those predictive
intervals would be too narrow and coverage would fall short.

This is weaker than checking the rating directly. It is the strongest check
available, and saying so is better than reporting a number that sounds stronger
than it is.

## Result

NBA 2016-17 to 2018-19, 435 players over 16 columns, 15 percent of the observed
values hidden, giving 1,067 held-out values. Two factors, the anchor pinned,
800 warmup iterations and 800 draws across 2 chains, seed 20260910.

| Nominal | Observed | Median width |
|---|---|---|
| 50% | 54.1% | 1.07 sd |
| 80% | 82.3% | 2.05 sd |
| 90% | **90.9%** | 2.65 sd |

The per-metric table below sums to 15 rather than 16 because one column had no
value hidden in this draw. The claim report counts 17 candidates, which is the
same 15 box-score metrics plus RAPM plus the fused rating; the fused rating is
an output of this model rather than an input to it, so it does not appear
here.

Calibrated at all three widths, and the widths are reported alongside because
coverage can always be bought with vagueness. An interval from minus infinity
to infinity covers everything.

## The anchor is badly calibrated, and the pin is why

Coverage per metric at the 90 percent level:

| Metric | Coverage |
|---|---|
| **RAPM** | **0.703** |
| Possessions ended per 36 | 0.869 |
| Effective field goal | 0.877 |
| ...eleven metrics between | 0.895 and 0.963 |
| Rebounds per 36 | 1.000 |

RAPM is the worst-calibrated column by a wide margin, and every other metric
sits between 0.87 and 1.00. That is a direct consequence of pinning the anchor.

Holding the anchor's loading at its reliability bound is what gives the latent
quantity its meaning; without it the model finds position instead of impact.
But pinning the loading also determines the residual scale, since standardised
columns force `σ = √(1 − β²)`. At β = 0.892 that is 0.452, the narrowest
residual in the model. The model is therefore told, rather than allowed to
infer, that RAPM is measured tightly, and the held-out RAPM values say
otherwise.

This matters beyond the anchor's own column. The latent quantity is *defined*
by RAPM, so understating RAPM's noise understates the uncertainty in every
published rating. The 90 percent intervals on player ratings should be read as
a floor on the true uncertainty rather than a faithful estimate of it.

**The fix, not yet applied:** replace the hard pin with a tight prior centred on
the bound, so the anchor's loading can move a little if the data insists. That
keeps the identification while letting the residual scale be estimated. It is a
small change to `pippen.model.fusion` and it needs a rerun of the calibration
and the claim, so it is recorded here rather than made quietly.

## What the reliability figure assumes

RAPM's bound comes from its measured split-half reliability at three seasons,
0.796, from [the validation report](rapm-validation.md). If that figure is
itself optimistic, the bound is too high and the under-coverage above is partly
explained by it. The two are worth revisiting together.

Reproduce with `pippen.model.calibration.check_calibration`, passing the
settings named above. They are listed because a coverage figure without its
hold-out fraction and sampler settings cannot be checked against a rerun.
