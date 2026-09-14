# Measured reliability of the box-score metrics

Reliability measured from data rather than assigned by judgment, across all 25
hoopR seasons, 2001-02 through 2025-26. Run with `pippen reliability`; the
numbers below are from 15 September 2026.

## Method in one paragraph

Each player's games are shuffled and dealt alternately into two halves, the
metric is computed on each half, and the two halves are correlated across
players. That is repeated 100 times and averaged. Spearman-Brown then converts
the half-length correlation to the reliability of a full-length measurement.
Players need 500 minutes in the season; the All-Star exhibition and the
playoffs are excluded. See [Measuring reliability](reliability.md) for why each
of those choices was made.

## Results

Pooled across 25 seasons, at a 500-minute floor, roughly 345 qualifying players
a season. `rho half` is the correlation between halves; `reliability` is that
corrected to an 82-game season.

| Metric | rho half | sd across seasons | Spearman | Reliability at 82 games |
|---|---|---|---|---|
| Three-point rate | 0.979 | 0.003 | 0.971 | 0.992 |
| Possessions ended per 36 | 0.959 | 0.004 | 0.951 | 0.984 |
| Assists per 36 | 0.956 | 0.007 | 0.932 | 0.982 |
| Rebounds per 36 | 0.955 | 0.004 | 0.945 | 0.982 |
| Offensive rebounds per 36 | 0.929 | 0.006 | 0.911 | 0.971 |
| Defensive rebounds per 36 | 0.925 | 0.008 | 0.913 | 0.969 |
| Points per 36 | 0.919 | 0.008 | 0.899 | 0.967 |
| Blocks per 36 | 0.906 | 0.018 | 0.856 | 0.961 |
| Fouls per 36 | 0.848 | 0.030 | 0.841 | 0.935 |
| Free throw rate | 0.823 | 0.017 | 0.808 | 0.922 |
| Turnovers per 36 | 0.799 | 0.033 | 0.782 | 0.910 |
| Free throw percentage | 0.733 | 0.033 | 0.691 | 0.871 |
| Steals per 36 | 0.692 | 0.030 | 0.668 | 0.852 |
| True shooting | 0.536 | 0.027 | 0.523 | 0.746 |
| Effective field goal | 0.513 | 0.032 | 0.490 | 0.728 |

For comparison, RAPM measured the same way in
[the validation report](rapm-validation.md): 0.601 over one season, 0.796 over
three.

## The result that matters

Shooting efficiency is the least repeatable thing in the box score. True
shooting and effective field goal percentage sit at the bottom of the table,
below every counting rate. Shot *selection* sits at the top: how often a player
shoots from three reproduces almost perfectly.

That inverts a natural reading of the box score. "How well does he shoot" is
far noisier, season to season, than "how much does he shoot and from where".

It is not an era effect. True shooting's reliability runs between 0.708 and
0.781 across all 25 seasons, with no trend.

The mechanism is the same one that puts free throw percentage below points per
36 despite free throws being the most controlled shot in basketball. A
split-half correlation measures how well a metric *tells players apart*, and
that depends on the spread of true values as much as on measurement precision.
Points per 36 runs from about 5 to 35 across the league, so even a noisy
estimate separates players easily. True shooting spans roughly .48 to .65, and
the shot-to-shot variance inside a half-season eats an appreciable share of
that range.

Read the table as a statement about a metric *in this population*, not about
the measurement alone. A low figure can mean players are alike, not that the
number is badly measured.

## Why this table must not become the fusion weights

Classical measurement theory gives error variance proportional to `1 - r`, so
inverse-variance weighting would give each metric a weight of `r / (1 - r)`.
Applied to the column above:

| Metric | Reliability | Naive weight |
|---|---|---|
| Three-point rate | 0.992 | 122.1 |
| Possessions ended per 36 | 0.984 | 60.4 |
| Assists per 36 | 0.982 | 56.1 |
| Points per 36 | 0.967 | 28.9 |
| **RAPM, three seasons** | **0.796** | **3.9** |
| True shooting | 0.746 | 2.9 |
| Effective field goal | 0.728 | 2.7 |
| **RAPM, one season** | **0.601** | **1.5** |

Three-point rate would count 31 times more than three-season RAPM, and 81 times
more than one-season RAPM. Three-point rate is a description of shot selection.
It says nothing about whether a player helps his team win.

Reliability sets a ceiling on how much a metric can contribute. It does not set
the contribution. What is missing is how much of each metric's own quantity is
the latent quantity of interest, which is the loading the fusion model has to
estimate from data. The two have to be estimated together.

For that reason `pippen.reliability.testretest` exposes no function returning
`r / (1 - r)`, and a test asserts that no public name in the module contains
"weight". The table above is an input to a measurement-error model, not a set
of weights.

## Where this disagrees with the source research

The source research assigns TS%, AST% and REB% together to Tier 3, 60 to 75
percent reliability.

True shooting measures 0.746, at the top of that band, so the tier is about
right for it.

The other two cannot be compared directly and the reason is worth stating.
Assist percentage and rebound percentage need team totals *while the player was
on the floor*, which a box score does not carry, so this project measures
assists and rebounds per 36 minutes instead. Those are different quantities.
What can be said is that the per-36 versions measure 0.982 each, far above the
60 to 75 band, so a tier that places rebounding alongside shooting efficiency is
grouping metrics whose reproducibility differs by a factor of twenty in
odds terms.

That is the same pattern the errata already records: the tiers were assigned by
impression and numbered afterwards.

## Odd-even versus repeated random splits

The project uses 100 random splits. Odd-even, the convention in the
sports-analytics literature, is computed alongside.

The two agree closely. Across all 15 metrics the mean absolute difference in
`rho half` is 0.0025 and the largest is 0.0068, so the choice of rule does not
change any conclusion here.

Averaging still earns its place, for a different reason. The standard deviation
of a single split's correlation is 0.027 for true shooting and 0.033 for
turnovers per 36. A single split, odd-even included, is one draw from that
spread, and averaging a hundred removes the dependence of a published figure on
which draw happened to be taken.

## Known limitations

- **Reliability is not validity.** A metric can be perfectly consistent and
  consistently measure the wrong thing. Three-point rate is the demonstration.
- **One floor, one length.** Every figure here is at 500 minutes and corrected
  to 82 games. Both are stated in the column names rather than left implicit,
  because the same measurement implies very different weights at different
  lengths.
- **Correlated errors.** Inverse-variance weighting assumes metrics' errors are
  independent. These all share a box score, so they do not. The fusion model
  estimates a correlation structure rather than assuming independence.
- **Range restriction.** Reliability measured on a high-minute subset is
  affected by those players being more alike, not only by being better
  measured. The reliability curve reports nested floors rather than disjoint
  bands for this reason, and the effect is not fully removed.
