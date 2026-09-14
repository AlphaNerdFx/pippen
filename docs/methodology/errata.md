# Errata in the source research

## Why this page exists

This project began from a literature survey produced with AI assistance and
reviewed by a human. Both stages let errors through, which is normal and is the
reason a correction record exists rather than an apology.

The survey lives in `docs/research/` and is **never edited**. It is a record of
what was believed at the start, and rewriting it would destroy the evidence that
these corrections were needed. Everything wrong with it is listed here instead.

Each entry states what the research says, what is actually true, how that was
verified, and what it changes.

---

## 1. RAPM was placed in the wrong tier

**The research says**, in `CLAUDE.md`'s summary tables, that RAPM is Tier 1 at
85-95%.

**Actually true:** RAPM scores 80-85%. The methodology defines Tier 1 as 85-95%
and Tier 2 as 75-85%, so 80-85% is Tier 2. Both
`nba_metrics_reliability_report.md` and the ranking table in
`nba_metrics_detailed_report.md` file it under Tier 2 correctly. Only the summary
promoted it.

**Verified by** reading which tier heading each report files RAPM under, and
comparing against the boundaries in `nba_metrics_reliability_methodology.md`.

**What it changes:** RAPM is this project's ground truth. Overstating its
reliability by a tier would have propagated into every downstream claim.
Corrected in the project instructions.

---

## 2. Tier labels are applied inconsistently at the same score

**The research says** D-EPM is Tier 1 and D-RAPM is Tier 2.

**Actually true:** both are given the identical reliability of 80-85%. That band
is Tier 2 by the methodology's own definition, so D-EPM's Tier 1 label is wrong.

| Metric | Reliability given | Tier given | Tier the boundaries require |
|---|---|---|---|
| O-EPM | 85-90% | Tier 1 | Tier 1 |
| D-EPM | 80-85% | Tier 1 | **Tier 2** |
| O-RAPM | 80-85% | Tier 2 | Tier 2 |
| D-RAPM | 80-85% | Tier 2 | Tier 2 |

**What it changes:** it shows the tiers were assigned by impression and then
given numbers, rather than derived from numbers. That is the strongest single
argument for measuring reliability rather than citing it.

---

## 3. The 0.44 constant is mischaracterised

**The research says** PER is unreliable partly because "constants like 0.44 (for
possession estimation) are outdated and may not reflect modern NBA realities".

**Actually true:** 0.44 is an empirical estimate of **the fraction of free throw
attempts that consume a possession**. Not every free throw ends a possession. On
a two-shot foul only the second does. On an and-one the field goal already ended
it. On a three-shot foul only the third does. Technical free throws end nothing.
The measured fraction lands near 0.44.

**Verified** against two archived sources in this project's own bibliography:

> "The 0.44 estimates how many possessions free throws actually cost (most trips
> are two shots, but and-ones and technicals skew it)." (SRC-6)

> "The 0.44 coefficient in the TS% formula estimates the portion of free throw
> attempts that represent actual possessions" (SRC-55)

**Three things follow.**

**It is not arbitrary.** It estimates a specific, measurable quantity.

**It is not specific to PER.** The same constant, for the same purpose, appears
in Pace, turnover rate, true shooting and usage rate, which the research places
in Tier 1 and Tier 2. PER's version is not a different or worse constant. The
Wikipedia formula for `uPER`, archived here as SRC-16, contains
`0.44 × lgFTA / lgPF`, identical in purpose.

**It is not the two-versus-three adjustment.** That logic, where three
two-pointers equal two three-pointers, lives in **effective field goal
percentage**, whose `0.5 × 3PM` term counts a three as 1.5 field goals because
3 ÷ 2 = 1.5. The separate `2 ×` in the true shooting denominator is a scaling
that puts the result on the same footing as field goal percentage. Neither is
0.44.

**What survives of the criticism of PER.** Removing this leaves the real
objections, which are enough on their own:

- Defence is captured only through steals and blocks, which the author concedes.
- No adjustment for teammates, opponents or role.
- The event weights themselves are fitted values, not derivable quantities.
- The league is renormalised to exactly 15 every season, forcing a fixed
  distribution regardless of how good the league actually was.

The measured value does not replace 0.44 in the pipeline yet. One season is not
evidence of a constant. The coefficient is measured for every season ingested
first, and only then does the question of replacing the conventional value get
answered. If it sits near 0.41 across twenty years, the constant is simply wrong
and should be replaced. If it drifts with rule changes, the drift is the more
interesting finding and argues for a per-season value rather than a new constant.
Switching on one season's evidence would repeat the error this page documents.

**What it changes for this project.** There is a legitimate version of the
complaint, and it applies to every metric rather than to PER. The true fraction
drifts with rule changes, and hard-coding 0.44 across a 25-season span bakes in
an assumption nobody checks. This project has the play-by-play data to
**measure the coefficient per season** instead. That is now the intended
approach, and the fixed 0.44 becomes the baseline it is compared against.

### The measured coefficient

**Measured for the 2023-24 season:** 0.410, against the conventional 0.44.
That season's free throws ended a possession about 0.030 less often than the
fixed constant assumes, roughly 7% lower in relative terms.

Of 57,076 free throw attempts, 57,071 could be classified from the columns
hoopR provides, giving 23,421 possession-ending trips. And-one, technical,
flagrant and clear-path free throws are excluded from that count by rule, not
by matching specific foul-name strings: an and-one's field goal already ended
the possession, a technical changes nothing, and a flagrant or clear-path foul
lets the fouled team keep the ball regardless of whether the last shot goes
in. Ruling them out this way, rather than pattern-matching foul names, is what
lets the same logic hold across rule eras without being rewritten for each
one, including the "transition take foul" and "away from play foul" rules the
NBA added for 2023-24 itself.

The remaining 5 attempts (0.009% of the season) are a missed final free throw
followed immediately by another shot, with no rebound row logged between them.
The shooting team plainly kept the ball, but no label says so, and inferring
it from the shooter's team would be a guess rather than a reading. Those
attempts are excluded from both the numerator and the denominator.

An earlier version of this estimate excluded 29 attempts rather than 5. Its
lookahead stepped over substitutions only, and latched shut the moment any
other event appeared, so a foul call or a replay review sitting one event
before a perfectly clear rebound label made the whole trip unresolvable. The
excluded set was not random: six were coach's challenges and seven were runs
of three substitutions. Code review caught it. The lookahead now steps over
anything that is not a shot attempt, using hoopR's own `shooting_play` flag,
and stops at a shot because a rebound after a new shot belongs to that shot.
Correcting it moved the coefficient from 0.4102 to 0.4104, so the bias was
real but small. It is recorded here because a number whose error bar comes
from an undocumented bug is not a measurement.

**Verified** by running `estimate_season_coefficient` (see
`src/pippen/data/possession_coefficient.py`) against hoopR's real 2023-24
play-by-play file (`play_by_play_2024.parquet`, 614,447 rows) and checking
every intermediate count by hand: 32,268 free throw trips, of which 6,622 are
one-shot and-one or take-foul trips, 1,544 are technical, 169 are flagrant or
clear-path, 19,393 end on a made last shot, 4,005 end on a missed last shot
with a defensive rebound, and 506 continue on a missed last shot with an
offensive rebound.

**What it changes:** one season is a single measurement, not evidence of
drift across rule eras on its own. That comparison needs several seasons run
through `estimate_coefficients_by_season`, which this module also provides,
once more seasons are ingested. What the 2023-24 season already shows is that
0.44 is now a measured quantity in this project rather than an assumed one,
and the first measurement does not match it.

---

## 4. Citation integrity

Found while archiving all 157 citations. Full detail in
`data/sources/MANIFEST.md`.

| Problem | Detail |
|---|---|
| One paper, three identifiers | SRC-34, SRC-35 and SRC-89 are all arXiv 2601.15000, which inflates the apparent evidence base |
| One dead page, two identifiers | SRC-39 and SRC-42 are the same URL, and it returns 404 |
| EPM's headline figure has no live source | The 85-90% reliability rests on SRC-39, which is gone. Only a screenshot survives |
| PIPM methodology source is gone | SRC-112 returns 404 |
| Eight citations archive nothing | Every FiveThirtyEight URL now redirects to `abcnews.com/politics`. Seven supported CARMELO, one supported RAPTOR |
| One source is not a source | SRC-64 is a podcast episode description that appears to have been read as an article |
| One typo, not a dead link | SRC-38's URL carries one extra word in its slug. The corrected address is live |

---

## 5. What the research still gets right

This page is a correction record, not a dismissal. The survey's central
conclusions hold up:

- Metrics built on lineup data with regularisation outperform box-score-only
  metrics by a wide margin.
- Team-level metrics are more reliable than individual ones, because aggregation
  cancels noise.
- Defence is the hardest thing to measure, and box-score defensive metrics are
  close to worthless.
- Multi-season pooling substantially reduces standard error.
- Low-minute players are noisy in every metric and need shrinkage.

Those are the load-bearing claims, and this project is built on them.
