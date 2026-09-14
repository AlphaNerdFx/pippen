# RAPM validation report

What was checked, against what, and what came out. Run with
`pippen gate`; the numbers below are from 15 September 2026.

## The check

Phase 2's gate asked for a Spearman correlation above 0.85 against a published
multi-season RAPM. That was changed, and the reason matters.

Published RAPM ratings exist as interactive web tables with no stated licence
and no download. Depending on one would make the check unreproducible from a
clean checkout. Worse, a disagreement would be unattributable: their ridge
penalty, their possession definition, their minutes filter and their prior all
differ from ours, and a low correlation would not say which caused it.

So the comparison is against an independently built **stint dataset** instead,
run through this project's own solver at the same penalty. That holds the
regression constant and varies only the part that is actually risky:
reconstructing who was on the floor from a play-by-play feed.

| | This project | Reference |
|---|---|---|
| Feed | data.nba.com | ESPN, via hoopR |
| Built by | this codebase | SCORE Sports Data Repository |
| Season | 2022-23 | 2022-23 |
| Solver | `pippen.rapm.ridge` | `pippen.rapm.ridge` |
| Penalty | 3,000, cross-validated | 3,000, taken from ours |

The reference states no licence, so it is local validation only and is never
redistributed or published, the same treatment Basketball-Reference gets.

## Result

| Possession floor | Players compared | Spearman | Pearson | Mean absolute gap |
|---|---|---|---|---|
| 500 | 460 | 0.914 | 0.922 | 0.55 |
| 1,000 | 419 | 0.915 | 0.921 | 0.58 |
| 2,000 | 370 | 0.920 | 0.924 | 0.58 |

The gate passes at every floor. Stability across floors matters: a correlation
that held only for high-minute players would mean the two builds agreed about
stars and disagreed about everyone else.

Rank correlation is the headline because the two builds need not share a scale.
Pearson is reported alongside so that a scale disagreement would be visible
rather than hidden, and here the two agree, so the builds are close in
magnitude as well as in order.

## Where the two disagree, and which is right

The two fits produce different intercepts: 112.85 here against 106.30 for the
reference. That is a 6.5-point gap in league-average offensive rating, and it
is not noise.

It comes from the possession count. This project counts 243,929 possessions
across 1,222 games, which is 99.8 per team per game. The reference counts
253,963 across 1,225 games, which is 103.6. The NBA's official pace for 2022-23
was 99.2.

So the denominators differ by about four percent and ours is the one that
matches the official figure. Points per 100 possessions is a rate, so a larger
denominator lowers the rate, which is exactly the direction of the intercept
gap. The reference appears to count some events as possessions that the NBA's
own definition does not.

This does not weaken the check. Rank correlation is unaffected by a constant
scale factor, and the agreement at 0.92 says the two walks put the same players
in the same order despite disagreeing about what a possession is.

## Individual ratings, 2022-23

Top twelve by this project's rating, restricted to players with at least 2,000
possessions:

| Player | Ours | Reference | Gap |
|---|---|---|---|
| Nikola Jokić | 5.61 | 5.90 | −0.29 |
| Joel Embiid | 5.43 | 5.36 | 0.07 |
| Jrue Holiday | 4.78 | 5.57 | −0.79 |
| Derrick White | 4.72 | 3.86 | 0.86 |
| Josh Hart | 4.51 | 4.50 | 0.01 |
| Jaren Jackson Jr. | 4.28 | 2.60 | 1.67 |
| Draymond Green | 4.18 | 5.88 | −1.70 |
| Kawhi Leonard | 4.12 | 5.05 | −0.92 |
| LeBron James | 3.94 | 3.13 | 0.81 |
| Franz Wagner | 3.92 | 3.04 | 0.87 |
| Aaron Gordon | 3.87 | 4.57 | −0.71 |
| Anthony Davis | 3.84 | 4.79 | −0.94 |

Embiid was the 2022-23 MVP and Jackson the Defensive Player of the Year, so the
list is recognisable rather than merely internally consistent. That is a weak
check and is offered as one.

The largest disagreements run to about 2.4 points per 100, on Jaylen Brown, Nic
Claxton, Paolo Banchero and Davion Mitchell. Against a median bootstrap standard
error near 1.1 per 100, gaps of that size are roughly two standard errors: large
enough to notice, small enough to be sampling rather than a defect.

## Does pooling seasons help, and the criterion that had to be replaced

Phase 2 asked for bootstrap standard errors that shrink as seasons are added.
Measured, they do not. On a fixed cohort of 228 players present with at least
2,000 possessions in every one of 2016-17 to 2018-19:

| Window | Possessions | Median bootstrap SE |
|---|---|---|
| 1 season | 232,897 | 1.217 |
| 2 seasons | 440,492 | 1.303 |
| 3 seasons | 683,356 | 1.253 |

Flat. Two explanations were tested and rejected before the real one. It is not
players leaving the league: the cohort above is present throughout. It is not a
coding error either.

A bootstrap standard error on a ridge coefficient does not measure information.
Within a single window it **rises** with a player's possessions, correlating
+0.79 with their logarithm:

| Median possessions | Players | Median SE |
|---|---|---|
| 388 | 98 | 0.56 |
| 2,174 | 97 | 1.10 |
| 4,764 | 97 | 1.24 |
| 6,919 | 97 | 1.23 |
| 9,393 | 97 | 1.19 |

A player with two hundred possessions is shrunk almost entirely to zero, so his
coefficient barely moves between resamples and his standard error is small.
That is the prior, not precision. The statistic conflates "estimated precisely"
with "shrunk to nothing".

The same mechanism explains the flat cross-window result. Holding the penalty
fixed while tripling the data weakens the shrinkage in relative terms, and the
variance that releases roughly cancels the information gained. Scaling the
penalty with the data does make the number fall, 1.210 to 0.901 to 0.727, but
that buys variance reduction with bias rather than with information, so it
would be a misleading thing to report as evidence that pooling helps.

The criterion came from the same source research this project has already
found unreliable elsewhere, and it is the wrong instrument.

### What replaced it

Split-half reliability, the instrument this project applies to every other
metric, now applied to its own ground truth. Split the window's games in two,
fit RAPM on each half, correlate the ratings across the fixed cohort, and apply
Spearman-Brown to get the reliability of a rating fitted on the whole window.

| Window | rho across halves | Reliability of the window |
|---|---|---|
| 1 season | 0.429 | 0.601 |
| 2 seasons | 0.578 | 0.732 |
| 3 seasons | 0.661 | 0.796 |

Monotone, and it answers the question the original criterion was reaching for.

Two things follow. Three-season RAPM at 0.796 lands inside the 80 to 85 percent
band the source research assigns to RAPM, so that figure is roughly right for
multi-year RAPM. Single-season RAPM at 0.601 does not, which is the concrete
reason this project publishes multi-season windows rather than single seasons.

Run it with `pippen.rapm.stability.split_half_stability`.

## Other checks

| Check | Threshold | Result |
|---|---|---|
| Points reconcile against an independent box score | exact | Pass, 40 games of 2016-17 |
| Every design row names five players a side | always | Pass, property test |
| Ratings invariant to row order | exact | Pass, property test |
| Ratings invariant to player numbering | exact | Pass, property test |
| Possessions neither created nor lost by aggregation | exact | Pass, property test |
| Spearman against an independent build | above 0.85 | Pass, 0.914 to 0.920 |
| RAPM split-half reliability rises with window length | monotone | Pass, 0.601 to 0.796 |

## What this does not establish

Reliability, not validity. The check says two independent reconstructions of
who was on the floor agree. It does not say that RAPM measures player impact
well, that the ridge penalty is the right one, or that a single season is enough
to act on. Those are separate questions, and the first of them is what Phase 3
exists to answer.

The comparison also covers one season. Both builds could share a systematic
error in a season neither was checked on, and the 2021-22 archive gap recorded
in [data quirks](data-quirks.md) is a reminder that the feed's problems are not
uniform across years.
