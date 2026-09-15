# ADR 0003: Phase 2's gate was changed in two ways

- Status: Accepted
- Date: 2026-09-15
- Deciders: AlphaNerdFx

## Context

Phase 2 was written with this exit condition:

> computed multi-season RAPM reaches Spearman correlation above 0.85 against a
> published multi-season RAPM, possession counts reconcile to official box
> scores within one percent, and bootstrap standard errors shrink as seasons are
> added.

Two of those three could not be used as written. Both problems were found by
running the checks rather than by reasoning about them, and both were found
after the phase had started.

### The comparison target does not exist on usable terms

Published multi-season RAPM exists as interactive web tables with no stated
licence and no download. Depending on one makes the check unreproducible from a
clean checkout, which is the property the gate was supposed to establish.

The deeper problem is attribution. A low correlation against someone's published
ratings could come from their ridge penalty, their possession definition, their
minutes filter, their prior, or from a genuine defect in this project's lineup
reconstruction. There is no way to tell which, so a failure would carry no
information about what to fix.

### Bootstrap standard errors measure shrinkage, not information

The criterion asks whether uncertainty falls as seasons are pooled. Measured on
228 players present with at least 2,000 possessions in every one of 2016-17 to
2018-19, it does not:

| Window | Possessions | Median bootstrap SE |
|---|---|---|
| 1 season | 232,897 | 1.217 |
| 2 seasons | 440,492 | 1.303 |
| 3 seasons | 683,356 | 1.253 |

Two explanations were tested and rejected: players leaving the league, and a
coding error. The cause is that a bootstrap standard error on a ridge
coefficient does not measure information. Within a single window it rises with
a player's possessions, correlating +0.79 with their logarithm:

| Median possessions | Players | Median SE |
|---|---|---|
| 388 | 98 | 0.56 |
| 2,174 | 97 | 1.10 |
| 9,393 | 97 | 1.19 |

A player with two hundred possessions is shrunk almost to zero, so his
coefficient barely moves between resamples and his standard error is small.
That is the prior rather than precision. The statistic conflates "estimated
precisely" with "shrunk to nothing", which makes it useless for comparing
players or window lengths.

The same mechanism explains the flat cross-window result. Holding the penalty
fixed while tripling the data weakens the shrinkage in relative terms, and the
variance that releases roughly cancels the information gained.

The criterion came from the same source research this project already corrected
elsewhere, in `docs/methodology/errata.md`.

## Decision

Change both, and record the change rather than quietly editing `TODO.md`.

**The comparison target becomes an independently built stint dataset, run
through this project's own solver at the same penalty.** That holds the
regression constant and varies only the lineup reconstruction, which is the
part that is actually risky. The reference used is the SCORE Sports Data
Repository's 2022-23 stint file, built from hoopR and so ESPN-sourced, against
this project's data.nba.com walk of the same games. It states no licence, so it
is treated as Basketball-Reference is: local validation only, never
redistributed.

**The shrinkage criterion becomes split-half reliability of the ratings
themselves**, the instrument this project applies to every other metric, applied
to its own ground truth. Split the window's games in two, fit RAPM on each half,
correlate across a fixed cohort, and apply Spearman-Brown.

## Consequences

**Gained: the gate now isolates what it was meant to test.** Spearman 0.914 to
0.920 across possession floors from 500 to 2,000, against a threshold of 0.85.

**Gained: the replacement criterion answers the question the original was
reaching for**, and monotonically:

| Window | Reliability |
|---|---|
| 1 season | 0.601 |
| 2 seasons | 0.732 |
| 3 seasons | 0.796 |

Three-season RAPM at 0.796 sits inside the 80 to 85 percent band the source
research assigns to RAPM. A single season at 0.601 does not, which is the
concrete reason this project publishes pooled windows.

**Accepted: changing an acceptance criterion mid-phase looks like moving the
goalposts, and the only defence is the evidence.** The measurements above are
recorded in `docs/methodology/rapm-validation.md` and reproducible with
`pippen.rapm.stability.split_half_stability`. A reader who thinks the change was
self-serving can rerun both.

**Accepted: the comparison covers one season.** Both builds could share a
systematic error in a season neither was checked on.

**Noted:** the bootstrap standard errors are still computed and still reported.
They remain the right tool for questions about a single fit. They are no longer
a gate.
