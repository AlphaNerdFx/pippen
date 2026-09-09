# Limitations

Read this before quoting any number from this project.

## Nothing is validated yet

The project is pre-release. No results have been published. The claim under test
has not been run.

## Defence remains hard

Box-score defensive statistics capture a fraction of defensive impact. Steals and
blocks are visible; positioning, communication, and deterrence are not. Metrics
built only on box-score defence are unreliable, which is why this project
excludes DBPM outright and leans on plus-minus based estimation for the defensive
side.

This is a limitation of the available data, not something a better model fixes.

## Low-minute players

Every impact metric is noisy below roughly 500 minutes. This project does not
solve that. It does two honest things instead: it shrinks such players toward the
league mean, and it reports an interval wide enough to show that the estimate is
weak.

A wide interval is not a defect. It is the answer.

## Era dependence

Reliabilities are measured on modern data. Applying them to the 1990s, before
three-point volume and tracking data, is unsupported. Play-by-play coverage
itself only reaches back to about 2002 in the bulk sources used here.

## Correlated errors between metrics

Inverse-variance weighting assumes independent errors. Public metrics share
inputs, so they are not independent. The model estimates a correlation structure
rather than assuming it away, but the assumption is imperfect and the residual
effect is to make intervals slightly too narrow.

## RAPM does not establish causation

RAPM measures association between a player being on the floor and the score
moving. Coaches choose lineups for reasons, and those reasons correlate with
outcomes. A player who only plays against weak opposition will look better than
they are, beyond what opponent adjustment removes.

## What this project cannot tell you

- Whether a player will be good on a different team, in a different role.
- Whether a player's improvement is real or noise, within a single season.
- Anything about players outside the NBA.
- Anything useful about betting, which is out of scope by choice.
