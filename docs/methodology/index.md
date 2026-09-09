# Method overview

## The problem with the existing approach

There are perhaps a dozen public NBA impact metrics. They disagree. A player can
sit in the top ten by one and outside the top forty by another, and no metric
tells you which to believe, or how firmly.

The usual response is to argue about which metric is best. This project does
something else.

## The reframe

Treat every public metric as a **noisy measurement of the same unobserved
quantity**. Let $\theta_p$ be player $p$'s true contribution to point
differential, which nobody ever observes. Each metric $m$ gives a reading:

$$
y_{p,m} = \alpha_m + \beta_m \theta_p + \varepsilon_{p,m},
\qquad \varepsilon_{p,m} \sim \mathcal{N}(0, \sigma_m^2)
$$

Now the question is no longer "which metric is right." It is "how noisy is each
one, and how should readings be combined given that noise." That is a
measurement-error problem, and statistics has answered it.

## The three steps

### 1. Own the ground truth

Compute [RAPM](rapm.md) from possession-level play-by-play rather than borrowing
a paywalled metric. Without this the project could not be reproduced, and could
not legally publish its inputs.

### 2. Measure reliability instead of asserting it

Split each player's season into odd and even games, compute each metric on both
halves, and correlate. A metric that disagrees with itself is measuring noise.
The details are on [Measuring reliability](reliability.md).

This replaces the common practice of assigning reliability by expert judgment.
The survey this project grew from scored metrics from 0 to 100 across six
criteria, and conceded in its own limitations section that the scoring "involves
some judgment." Judgment is a reasonable starting point and a poor foundation.

### 3. Fuse by inverse-variance weighting

A metric with reliability $r_m$ carries error variance proportional to
$1 - r_m$, so its weight is

$$
w_m \propto \frac{r_m}{1 - r_m}
$$

Fitting this hierarchically in NumPyro shrinks low-minute players toward the
league mean automatically and yields a posterior interval for every player, not
a point estimate.

The output is **RAIM**, the Reliability-Adjusted Impact Metric.

## How we will know whether it worked

> Does RAIM predict next-season team net rating better than any single input
> metric does, out of sample?

Aggregate each metric to team level weighted by minutes, predict the following
season's net rating, and compare out-of-sample error. If RAIM does not beat its
best input, the fusion added nothing, and that result gets published here.

## What this is not

It is not a claim to beat DARKO or EPM. Those systems are excellent and use
inputs this project does not have. It is a claim that combining public metrics
*while accounting for their measured noise* is better than picking one, and that
users deserve an interval alongside the number.
