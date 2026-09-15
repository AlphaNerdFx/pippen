# ADR 0005: The anchor defines the latent quantity

- Status: Accepted
- Date: 2026-09-15
- Deciders: AlphaNerdFx

## Context

The fusion model treats every metric as a noisy reading of one latent quantity
per player:

    y[p,m] = alpha[m] + beta[m] * theta[p] + epsilon[p,m]

A factor model of this shape is invariant to the sign and scale of the factor.
Standardising the columns fixes the scale. The first version fixed the sign by
requiring the anchor metric's loading to be positive, RAPM being the anchor
because it is the one input built to measure impact directly. Fixing the sign
leaves the factor free to become whatever the columns have most in common, and
on this data that turned out to be a problem with a large and visible failure. The sampler returned:

| Metric | Loading |
|---|---|
| Rebounds per 36 | -0.99 |
| Defensive rebounds per 36 | -0.96 |
| Offensive rebounds per 36 | -0.90 |
| Blocks per 36 | -0.68 |
| Three-point rate | +0.64 |
| RAPM | +0.013 |

The top of the resulting table was every small guard in the league and the
bottom was every centre. The output correlated -0.16 with RAPM. The model had
found player size.

The one-factor model assumes each metric is the latent quantity plus
*independent* noise. Box-score rates violate that badly: they share a large
position axis, because how many rebounds and blocks a player records is mostly
a fact about his height and his role. That shared structure is far stronger than
the impact signal, and fifteen position-laden columns outvote one impact column
however the anchor's sign is constrained.

Pinning the anchor at its reliability bound without adding factors only flipped
the sign, putting DeAndre Jordan, Hassan Whiteside, Rudy Gobert and Andre
Drummond on top instead of the guards.

This was foreseen in outline. `docs/methodology/reliability.md` already listed
correlated errors as the assumption most likely to break, and said the model
would estimate a correlation structure rather than assume independence.

## Decision

The anchor defines what the latent quantity means. Its loading on the first
factor is held at its reliability bound, and its loading on every other factor
is zero:

    beta[anchor, 0] = sqrt(r_anchor),  beta[anchor, k>0] = 0

That says all of the anchor's reliable variance is the latent quantity, which
makes theta "impact as well as RAPM can measure it" rather than "whatever these
columns have most in common".

Nuisance factors are fitted alongside, free, to absorb the shared structure that
would otherwise contaminate the first. Two is the default. Only the first factor
is published as a rating.

Measured on NBA 2016-17 to 2018-19, 435 players:

| Factors | Published r-hat | Nuisance r-hat | Spearman against RAPM | Top of the table |
|---|---|---|---|---|
| 1 | 1.0025 | n/a | 0.407 | Jordan, Gobert, Whiteside, Drummond |
| 2 | 1.0039 | 22.8 | 0.763 | Curry, Harden, Embiid, LeBron, Westbrook |
| 3 | 1.0032 | 6.8 | 0.760 | Curry, Gobert, Durant, LeBron, Lillard |
| 4 | 1.0051 | 2.7 | 0.866 | |

`anchor_loading="positive"` recovers the free-anchor behaviour. It is kept
because it shows what the box score contains on its own, and it is not a
sensible way to produce ratings.

## Consequences

**Gained: the headline number has a defined meaning.** Without the pin it is
whatever the input columns share, which on this data is height.

**Accepted: the anchor's own intervals are too narrow, and this is the cost of
the pin.** Pinning the loading also determines the residual scale, since
standardised columns force `sigma = sqrt(1 - beta^2)`. At beta = 0.892 that is
0.452, the narrowest residual in the model. The model is told, rather than
allowed to infer, that RAPM is measured tightly, and held-out RAPM values
disagree. Posterior predictive coverage at nominal 90 percent:

| Metric | Coverage |
|---|---|
| RAPM | 0.703 |
| Eleven metrics between | 0.869 and 0.963 |
| Rebounds per 36 | 1.000 |

Overall coverage is 90.9 percent, so the model passes on average while being
badly wrong on the one column that defines the factor. Because theta is defined
by RAPM, understating RAPM's noise understates the uncertainty in every
published rating. **The intervals on player ratings are a floor on the true
uncertainty rather than a faithful estimate of it, and they are published with
that statement attached.**

The fix is known and deliberately not applied: replace the hard pin with a tight
prior centred on the bound, so the loading can move if the data insists, keeping
identification while letting the residual scale be estimated. It needs a rerun
of the calibration and the claim, which is why it is recorded here rather than
made quietly. Tracked in `docs/methodology/calibration.md`.

**Accepted: the nuisance factors are unidentified by construction.** They can be
rotated and sign-flipped without changing the likelihood, so their r-hat runs
into the tens and carries no information. Convergence is reported for the first
factor's scores and loadings, which are what get published, with the nuisance
r-hat printed beside it rather than hidden.

**Noted: more factors purify the first factor toward the anchor.** Spearman
against RAPM rises from 0.407 at one factor to 0.866 at four. In the limit the
fusion reproduces its anchor and adds nothing, so the factor count is a real
choice and not a free parameter to maximise. Two is used.
