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

## Other checks

| Check | Threshold | Result |
|---|---|---|
| Points reconcile against an independent box score | exact | Pass, 40 games of 2016-17 |
| Every design row names five players a side | always | Pass, property test |
| Ratings invariant to row order | exact | Pass, property test |
| Ratings invariant to player numbering | exact | Pass, property test |
| Possessions neither created nor lost by aggregation | exact | Pass, property test |
| Spearman against an independent build | above 0.85 | Pass, 0.914 to 0.920 |

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
