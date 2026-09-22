# Model card

Following the structure proposed by Mitchell et al., *Model Cards for Model
Reporting*, FAT\* 2019. Every number here is measured in this repository and
reproducible from it. Where a figure is absent, the reason is stated rather than
the figure omitted.

## Model details

**What it is.** Regularized Adjusted Plus-Minus (RAPM) for NBA players,
estimated by ridge regression over possession-level stint data, pooled into
overlapping three-season windows.

**Version.** Tracks the package version. The shipped tables are regenerated only
when the pipeline changes, never silently.

**Owner.** AlphaNerdFx. Apache-2.0 for the code, and the shipped tables are
derived values computed in this repository rather than redistributed source
data.

**Estimator.** `sklearn.linear_model.Ridge` over a sparse design matrix built in
`src/pippen/rapm/design.py`. One column per player, `+1` when on offence, `-1`
when on defence, `0` when off the floor. The penalty `alpha` is selected by
cross-validation with folds cut on games rather than rows, so no possession from
a game appears in both the training and validation side of a split.

**What the model is not.** It is not the fusion model. A separate measurement
error model over box-score metrics exists in `src/pippen/model/fusion.py`, was
tested, and did not improve on RAPM. It is not shipped as a rating.

## Intended use

**Primary use.** Comparing player impact per 100 possessions within the covered
seasons, for research, analysis and teaching.

**Primary users.** Basketball researchers, students, and anyone who wants an
impact metric whose construction they can read end to end.

**Out of scope.** Contract valuation, betting, player evaluation for employment
decisions, and any use where a wrong answer about one player carries consequence
for that person. The metric has no per-player uncertainty published, which makes
it unsuited to decisions about individuals at the margin.

## Factors

**Covered seasons.** NBA 2016-17 through 2024-25, nine seasons, in NBA
labelling. The lower bound is where data.nba.com stops serving play-by-play. The
upper bound is where the feed stopped being populated.

**Windows.** Seven overlapping three-season windows, from 2016-18 to 2022-24.
Adjacent windows share two of their three seasons, so consecutive values are not
independent observations.

**Population.** 5,427 player-window rows. A player appears in a window if they
recorded any possessions in it, with no minutes floor applied to the shipped
table, so the low end includes players with under 20 possessions whose estimates
are almost entirely prior.

**Known population gap.** Three of 5,427 rows carry no player name, where the
ESPN to NBA identifier crosswalk failed for ids 2882 and 204058. All three sit
under 20 possessions. The rows ship rather than being dropped, so the gap is
visible rather than silently changing the row count.

## Metrics

**Reported.** `offensive`, `defensive` and `total`, all in points per 100
possessions relative to league average. `possessions` is reported alongside as
the per-player precision signal.

**Not reported, deliberately.** No standard error, no credible interval. The
only candidate was a bootstrap standard error on the ridge coefficients, and
measuring it showed the standard error **rises** with possessions, correlation
+0.79. A penalised coefficient with little data behind it is pinned near zero and
therefore varies little across resamples, so the tightest bars would have sat on
the least-supported players.
[ADR 0007](architecture/decisions/0007-the-api-serves-shipped-tables-and-no-interval.md)
records the decision, [ADR 0003](architecture/decisions/0003-phase-2-gate-changed.md)
the measurement that forced it.

**Population reliability.** Split-half reliability of RAPM is **0.796**,
measured rather than cited.

## Training data

**Source.** Play-by-play from data.nba.com, parsed into possessions and stints
with `pbpstats` (MIT). Box scores and schedules from the `hoopR-nba-data`
Parquet release, CC BY 4.0.

**Not used.** EPM is behind a $250/year paid tier and its values are not
redistributable. DARKO publishes a CSV with no stated licence. Neither enters
this project; both are compared by rank correlation only, from manually viewed
public leaderboards. Basketball-Reference values are used for local validation
and never enter a published artifact.

**Preprocessing.** Every table passes a pandera schema and four validation
families before use: completeness, consistency, accuracy and temporal integrity.
Possession counts reconcile against official box score totals.

**One correction worth naming.** The possession coefficient, the share of free
throw attempts that consume a possession, is **measured per season** rather than
hard-coded at the conventional 0.44. Every one of 25 measured seasons came out
below the convention, pooling at 0.4178.

## Evaluation

**Validation gate.** Spearman rank correlation **0.914** against an
independently constructed stint dataset, against a pre-registered threshold of
0.85. The threshold was declared before the measurement.

**Calibration.** The fusion model's intervals cover **90.9 percent** at a
nominal 90. That figure applies to the fusion model, which is not shipped as a
rating, and it is a floor on the true uncertainty because pinning the anchor
also pins its residual scale.

**The claim under test, and its answer.** The project asked whether fusing
public metrics weighted by measured reliability predicts next-season team net
rating better than RAPM alone. **It does not**, and the difference is not
statistically distinguishable (p = 0.171). Ridge and a tuned LightGBM over every
available metric land in the same place, so the ceiling belongs to these inputs
rather than to the method of combining them.

## Quantitative analyses

**Reliability runs against validity.** Across the 15 measured box-score metrics,
split-half reliability correlates **-0.564** with correlation against RAPM. The
most repeatable metrics are the least related to winning. Three-point rate is
the most reliable and among the least related to impact.

This is why nothing in this codebase turns reliability into a weight. It bounds
how much of a metric a measurement-error model may attribute to the latent
quantity, and is never a multiplier.
[ADR 0004](architecture/decisions/0004-reliability-bounds-never-weights.md).

**A one-factor model of box-score metrics recovers position.** Fit a single
latent factor and it comes back as player size, because rebounds and blocks load
together for tall players. That is why the fusion model pins an anchor rather
than letting the factor float.
[ADR 0005](architecture/decisions/0005-the-anchor-defines-the-latent-quantity.md).

## Ethical considerations

The subjects are professional athletes whose on-court performance is already
public. No personal data beyond name, league identifier and public box score
lines is processed.

The risk this metric carries is misuse against individuals. A number with no
published uncertainty, applied to a player near a roster or contract decision,
invites false precision. The out-of-scope list above is the mitigation, and the
absence of an interval is stated everywhere the number is served rather than
buried.

Defensive impact is captured badly by box-score inputs, which is a documented
property of the inputs rather than a flaw introduced here. Metrics that lean on
box-score defence, DBPM and PER among them, are excluded entirely.

## Caveats and recommendations

- Read `possessions` before reading the rating. A rating with 200 possessions
  behind it is mostly the prior.
- Do not read adjacent windows as year-on-year change. They overlap by two
  seasons.
- Do not weight by reliability. The measurement says it runs against validity.
- Do not use this for decisions about an individual's employment or pay.
- The fusion result is negative and published as such. If you are looking for
  the combined metric, it is not here, and
  [the claim under test](methodology/claim-under-test.md) explains why.
