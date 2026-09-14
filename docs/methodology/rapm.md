# RAPM

Regularized Adjusted Plus-Minus is the ground truth this project computes for
itself.

## Why not just use plus-minus

Raw plus-minus asks: while this player was on the floor, what happened to the
score? The problem is obvious once stated. A weak player alongside four stars
looks excellent. A strong player carrying a poor bench looks mediocre. Raw
plus-minus measures the team, not the player.

## Adjusting for who else was there

Split each game into **stints**: stretches during which the same ten players are
on the floor. For each stint, record point margin per 100 possessions. Then build
a matrix with one row per stint and one column per player:

| | Player A | Player B | Player C | … | margin per 100 |
|---|---|---|---|---|---|
| stint 1 | +1 | +1 | −1 | … | +8.3 |
| stint 2 | 0 | +1 | −1 | … | −4.1 |

The entry is $+1$ if the player was on the home side, $-1$ if on the away side,
and $0$ if on the bench. Regress margin on that matrix. Each player's
coefficient estimates their impact per 100 possessions, with teammates and
opponents controlled for automatically, because they are columns in the same
regression.

That is **APM**, Adjusted Plus-Minus.

## Why APM fails, and what fixes it

Teammates share the floor almost all the time. Statistically the model cannot
separate two players who are rarely apart. This is **multicollinearity**, and it
makes least-squares estimates swing wildly between samples. APM needs thousands
of games to settle down.

**Ridge regression** adds a penalty on the size of the coefficients:

$$
\hat{\beta} = \arg\min_\beta \; \lVert y - X\beta \rVert^2 + \lambda \lVert \beta \rVert^2
$$

Read statistically, the $\lambda$ term is a prior belief that players are
league-average until the data insists otherwise. It trades a little bias for a
large reduction in variance. $\lambda$ is chosen by cross-validation, never by
hand.

APM plus that penalty is **RAPM**.

## The hard part is not the regression

It is knowing who was on the floor. Play-by-play feeds record substitutions, but
they miss them at period boundaries and around ejections, and the errors are not
random.

This project does not write that parser. It uses
[pbpstats](https://github.com/dblackrun/pbpstats), MIT licensed, which is the
library behind pbpstats.com and already handles the known edge cases. Reusing it
removes the highest-risk code in the project.

!!! note "Why hoopR data cannot do this alone"
    The bulk historical Parquet from hoopR is sourced from ESPN and carries event
    participants but no on-court lineup column. It is excellent for box scores
    and shot data, and insufficient for stints. Both sources are used, each for
    what it is good at.

Reusing `pbpstats` turned out to mean reusing its parser and not its downloader.
The endpoint it fetches from, `playbyplayv2`, now answers HTTP 200 with the body
`{}` for every game of every season. This project downloads from data.nba.com
itself, through the rate limiter and atomic writes the rest of the pipeline
uses, and runs `pbpstats` against those files with `source=file`. The seam is
deliberate: the network side is ours, the substitution walk is theirs.

That route covers NBA seasons 2016-17 through 2024-25, nine seasons rather than
the ten originally planned. `docs/methodology/data-quirks.md` records why, along
with the event-ordering shim that pre-2023 seasons need.

## What a stint row actually holds

Rows aggregate to one per lineup matchup per game, which turns roughly 200
possessions into about 30 rows and loses nothing the regression uses. Each
carries both lineups, the possessions they faced each other for, and two point
totals.

The second total exists because the defence can score during the offence's
possession. A technical or away-from-play free throw is shot by whichever side
was fouled, and the possession does not change hands. Crediting those points to
the offence leaves a game's total correct and its per-team split wrong, which is
the kind of error that survives every check that compares the pipeline only
against itself. It was caught by reconciling against hoopR's box scores, a
different organisation's record of the same games.

The RAPM target is the offence's points. The other column exists so the
reconciliation can be run.

## Multi-season windows

Single-season RAPM is noisy. Pooling three or more seasons reduces standard
errors substantially. The trade is responsiveness: a three-year window is slow to
notice a player who genuinely changed. Both are published, and the window is a
parameter.

## Validation

Before RAPM is used for anything, it must clear these:

| Check | Threshold | Status |
|---|---|---|
| Points reconcile against an independent box score | exact | Passing, 40 games of 2016-17 |
| Every design row names five players a side | always | Passing, property test |
| Ratings invariant to row order and player numbering | exact | Passing, property test |
| Computed Four Factors against NBA.com | within 0.001 | Not yet run |
| Spearman correlation with a published multi-season RAPM | above 0.85 | Not yet run, needs a reference downloaded by hand |
| Bootstrap standard errors shrink as seasons are added | monotone | Not yet run |

The reconciliation threshold is exact rather than the one percent originally
planned. Once points are attributed to the team that scored them, they agree
exactly, and a tolerance would only hide a regression.

If the correlation check fails and cannot be fixed, the project switches its
target to next-season team net rating, which needs no external reference, and
records why.
