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

## Multi-season windows

Single-season RAPM is noisy. Pooling three or more seasons reduces standard
errors substantially. The trade is responsiveness: a three-year window is slow to
notice a player who genuinely changed. Both are published, and the window is a
parameter.

## Validation

Before RAPM is used for anything, it must clear these:

| Check | Threshold |
|---|---|
| Possession counts against official box scores | within 1% |
| Computed Four Factors against NBA.com | within 0.001 |
| Spearman correlation with a published multi-season RAPM | above 0.85 |
| Bootstrap standard errors shrink as seasons are added | monotone |

If the correlation check fails and cannot be fixed, the project switches its
target to next-season team net rating, which needs no external reference, and
records why.
