# Measuring reliability

This is the part of the project that is not standard practice.

## The usual approach, and its problem

Metric surveys typically score reliability by expert judgment: rate each metric
on transparency, context adjustment, defensive capture and so on, then average.
The survey this project grew from does exactly that, across six criteria on a 0
to 100 scale.

The problem is not that the judgments are bad. It is that they are judgments.
Two analysts scoring the same metric will disagree, there is no way to adjudicate,
and the resulting number cannot be checked by anyone. For a project whose entire
premise is *accounting for reliability*, an unfalsifiable reliability score is
the wrong foundation.

## Measuring it instead

Reliability has a standard definition in measurement theory: the share of a
measurement's variance that is signal rather than noise. It is estimated by
measuring the same thing twice and correlating the results.

For a season metric, the two measurements come from splitting the season:

1. Compute metric $m$ using only the player's **odd-numbered** games.
2. Compute metric $m$ using only the player's **even-numbered** games.
3. Correlate the two halves across all qualifying players.

Odd and even rather than first-half and second-half, deliberately: teams change
over a season, and a first-versus-second split would confound real change with
measurement noise.

## The Spearman-Brown correction

Each half uses roughly 41 games, but the metric is quoted on a full 82. A
half-length measurement is noisier than the real thing, so the raw correlation
understates reliability. Spearman-Brown corrects for the length difference:

$$
r_m = \frac{2 \rho_{\text{halves}}}{1 + \rho_{\text{halves}}}
$$

A half-split correlation of 0.70 corresponds to a full-season reliability of
0.82.

## Turning reliability into a weight

Classical measurement theory gives error variance as proportional to $1 - r_m$.
Inverse-variance weighting, the standard method for combining noisy estimates in
meta-analysis, therefore gives:

$$
w_m \propto \frac{r_m}{1 - r_m}
$$

The behaviour is what intuition wants. A metric with reliability 0.9 gets nine
times the weight of one with reliability 0.5. A metric with reliability near
zero contributes nothing.

## What gets reported

Measured reliabilities are published next to the tier assignments from the prior
survey, including where they disagree. Disagreements are the interesting part and
will not be quietly dropped.

## Known limitations

- **Reliability is not validity.** A metric can be perfectly consistent and
  consistently measure the wrong thing. Split-half reliability caps how useful a
  metric can be; it does not establish that it is useful.
- **Low-minute players inflate noise.** A minutes threshold is required, and the
  choice of threshold changes the result. It is reported alongside.
- **Correlated errors break the weighting.** Inverse-variance weighting assumes
  the metrics' errors are independent. Metrics sharing inputs, and most of them
  share box scores, violate this. The hierarchical model estimates a correlation
  structure rather than assuming independence, and the assumption is checked
  rather than trusted.
