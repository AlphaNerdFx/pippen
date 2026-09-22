# Limitations

Read this before quoting any number from this project.

## What has been validated, and what that does not cover

RAPM is computed for NBA 2016-17 through 2024-25 and clears its gate at Spearman
**0.914** against an independently constructed stint dataset, against a
threshold of 0.85 declared before the measurement. Metric reliability is
measured across 25 hoopR seasons rather than assigned.

The claim under test has been run and the answer is no. Fusing public metrics
weighted by reliability does not predict next-season team net rating better than
RAPM alone, and is not statistically distinguishable from it (p = 0.171). See
[the claim under test](claim-under-test.md).

None of that validates the metric for a season outside the covered range, for a
player with few possessions, or for any decision about an individual.

## There is no interval, and that is the largest limitation here

Ratings ship as point estimates with no standard error and no credible interval.

The project had one candidate and withdrew it. A bootstrap standard error on a
ridge coefficient measures how hard the penalty is pulling rather than how much
the data knows. Measured on this dataset the standard error **rises** with
possessions, correlation +0.79: a coefficient with little data behind it is
pinned near zero and barely moves across resamples, so the narrowest bars would
have sat on the least-supported players. That inverts what a reader expects an
error bar to mean.

Use `possessions` as the precision signal. It is the sample size behind the
estimate and it moves the right way.
[ADR 0007](../architecture/decisions/0007-the-api-serves-shipped-tables-and-no-interval.md)
records the decision;
[ADR 0003](../architecture/decisions/0003-phase-2-gate-changed.md) records the
measurement that forced it.

The fusion model does produce calibrated intervals, 90.9 percent coverage at a
nominal 90, and those are a floor on the true uncertainty rather than an
estimate of it, because pinning the anchor also pins its residual scale. See
[calibration](calibration.md). They are not shipped as ratings.

## Low-minute players

Every impact metric is noisy below roughly 500 minutes. Ridge shrinks such
players toward the league mean, which is the honest response to thin data, and
the shipped table applies no minutes floor, so the low end includes players with
under 20 possessions whose estimate is almost entirely prior.

There is no wide interval to signal that, for the reason above. Read
`possessions` first.

## Defence remains hard

Box-score defensive statistics capture a fraction of defensive impact. Steals
and blocks are visible; positioning, communication and deterrence are not.
Metrics built only on box-score defence are unreliable, which is why this
project excludes DBPM outright and leans on plus-minus estimation for the
defensive side.

This is a limitation of the available data, not something a better model fixes.

## Reliability is a bound, never a weight

An earlier version of this page described inverse-variance weighting and its
independence assumption. That method is not used and was rejected on evidence.

Across the 15 measured metrics, split-half reliability correlates **-0.564**
with correlation against RAPM. The most repeatable metrics are the least related
to winning, so weighting by reliability would systematically upweight the least
informative inputs. Reliability is used only as a bound on how much of a metric
a measurement-error model may attribute to the latent quantity.
[ADR 0004](../architecture/decisions/0004-reliability-bounds-never-weights.md).

The independence problem is real and survives the change of method. Public
metrics share inputs, so their errors are correlated, and the fusion model
estimates a correlation structure rather than assuming it away. The assumption
remains imperfect.

## A one-factor model of box-score metrics recovers position

Fit a single latent factor to these metrics and it returns player size rather
than impact, because rebounds and blocks load together for tall players. The
fusion model pins an anchor rather than letting the factor float, which makes
the latent quantity defined by that anchor rather than by the data alone.
[ADR 0005](../architecture/decisions/0005-the-anchor-defines-the-latent-quantity.md).

## Windows overlap

Ratings are pooled over three-season windows, so adjacent windows share two of
their three seasons. Consecutive values are not independent observations and
should not be read as year-on-year change.

## Era dependence

Reliabilities are measured on modern data. Applying them to the 1990s, before
three-point volume and tracking data, is unsupported. Play-by-play coverage in
the bulk sources used here reaches back to about 2002, and the RAPM computed in
this project starts at 2016-17 because that is where data.nba.com begins serving
play-by-play.

## RAPM does not establish causation

RAPM measures association between a player being on the floor and the score
moving. Coaches choose lineups for reasons, and those reasons correlate with
outcomes. A player who only plays against weak opposition will look better than
they are, beyond what opponent adjustment removes.

## Three rows have no player name

Three of 5,427 shipped rows carry a null name, where the ESPN to NBA identifier
crosswalk failed for ids 2882 and 204058. All three sit under 20 possessions.
They ship rather than being dropped, so the gap is visible rather than silently
changing the row count.

## What this project cannot tell you

- Whether a player will be good on a different team, in a different role.
- Whether a player's improvement is real or noise, within a single season.
- How confident to be about any single player's number.
- Anything about players outside the NBA.
- Anything useful about betting, which is out of scope by choice.
