r"""The measurement-error model that fuses metrics into one rating.

The model
---------
Every metric is treated as a noisy reading of one latent quantity per player:

.. math::

    y_{p,m} = \alpha_m + \beta_m \theta_p + \varepsilon_{p,m}

where :math:`\theta_p` is what the project is trying to estimate, the loading
:math:`\beta_m` says how much of metric *m* is that quantity, and
:math:`\varepsilon` is everything else.

Nothing here is new as statistics. It is a one-factor measurement-error model,
the same object that sits under factor analysis and under meta-analysis of
noisy estimates. What is new is refusing to assume the loadings and refusing to
set them from reliability.

Where reliability enters, and where it must not
-----------------------------------------------
The obvious move is to weight each metric by :math:`r/(1-r)`, the
inverse-variance weight. Measured on this data that is not merely suboptimal,
it is backwards: across fifteen box-score metrics, reliability correlates with
correlation against RAPM at :math:`r = -0.564`. Three-point rate is the most
reliable metric in the set and has no relationship with impact at all.

Reliability enters as a **bound** instead. Each column is standardised to unit
variance, so

.. math::

    1 = \beta_m^2 \operatorname{Var}(\theta) + \sigma_m^2

and with :math:`\operatorname{Var}(\theta) = 1` the residual scale is
determined rather than free:

.. math::

    \sigma_m = \sqrt{1 - \beta_m^2}

Classical test theory splits a standardised metric's variance into a reliable
share :math:`r_m` and an unreliable share :math:`1 - r_m`. The part of the
metric that tracks :math:`\theta` has to come out of the reliable share, so

.. math::

    \beta_m^2 \le r_m

That is the whole role of the measured reliability table: it caps how much of
each metric the model is allowed to attribute to the latent quantity. A metric
that disagrees with itself cannot be strong evidence about anything. A metric
that agrees with itself perfectly is *permitted* to load fully, and whether it
actually does is estimated from the data. Three-point rate is allowed a loading
up to 0.996 and the data gives it almost nothing.

One factor is not enough
------------------------
The first version of this model fitted a single factor, and it did not measure
impact. It measured *size*. Rebounds loaded at :math:`0.95`, blocks at
:math:`0.73`, three-point rate at :math:`-0.66`, and the resulting table put
every centre at one end and every small guard at the other. The anchor's own
loading came out at :math:`0.013`.

The cause is an assumption in the one-factor model that this data violates
badly. It says each metric is the latent quantity plus *independent* noise. Box
score rates are not independent: they share a large position axis, because how
many rebounds and blocks a player records is mostly a fact about his height and
his role. That shared structure is far stronger than the impact signal, and
fifteen position-laden columns outvote one impact column no matter how the
anchor is constrained. Pinning the anchor at its bound only flipped the sign,
putting the centres on top instead of the guards.

So the model fits several factors. The first is anchored to RAPM and is the one
reported as a rating. The others are free and exist to absorb the shared
structure that would otherwise contaminate it. The reliability bound then
applies to a metric's *total* reliable variance across all factors,

.. math::

    \sum_k \beta_{m,k}^2 \le r_m

which is what classical test theory actually claims, and the residual scale
follows as before.

This was foreseen. `docs/methodology/reliability.md` already listed correlated
errors as the assumption most likely to break, and said the model would
estimate a correlation structure rather than assume independence. The nuisance
factors are that structure.

Identification, and why a free anchor is not enough
---------------------------------------------------
A factor model is invariant to the sign and scale of the factor: negating
:math:`\theta` and every loading gives an identical likelihood. The scale is
fixed by :math:`\operatorname{Var}(\theta) = 1`.

Fixing the sign is not sufficient, and the first version of this model learned
that the hard way. With the anchor's loading merely constrained to be positive,
the sampler returned a factor with rebounds at :math:`-0.99`, blocks at
:math:`-0.68`, three-point rate at :math:`+0.64`, and RAPM at :math:`0.013`.
The top of the resulting table was every small guard in the league and the
bottom was every centre. The model had found *position*, which is much the
largest source of shared variance among box-score rates, and fifteen
position-laden columns outvoted the one column built to measure impact. The
output correlated :math:`-0.16` with RAPM.

The lesson is that an anchor has to fix the factor's *meaning*, not only its
sign. So the anchor's loading is held at its reliability bound,

.. math::

    \beta_{\text{anchor}} = \sqrt{r_{\text{anchor}}}

which says that all of the anchor's reliable variance is the latent quantity.
That is what makes :math:`\theta` "impact as well as RAPM can measure it"
rather than "whatever these columns have most in common". Every other metric's
loading then says how much of it is that quantity, which is the question the
project is actually asking.

RAPM is the anchor because it is the one input built to measure impact
directly. Pass ``anchor_loading="positive"`` to recover the free-anchor
behaviour, which is useful for showing what the box score alone contains and
is not a sensible way to produce ratings.

Missing values
--------------
An unobserved metric is dropped from the likelihood rather than filled. Filling
with the column mean would be a claim that the player is exactly league average
at it, which is far stronger than saying nothing.

Why NumPyro
-----------
The posterior is wanted, not a point estimate, because the project's output is
a rating with an interval rather than a number. NumPyro runs the No-U-Turn
Sampler on a compiled JAX graph, which handles a few hundred players and a
dozen metrics in seconds on a CPU, and it lets the model be written as the
equations above rather than as a hand-derived update rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import pandas as pd

from pippen.model.dataset import FusionDataset

#: Smallest residual scale allowed, so a loading at the bound cannot drive the
#: likelihood to a spike of zero width.
MIN_RESIDUAL_SCALE: Final = 0.05

#: Default sampler settings. Small because the model has a few hundred
#: parameters and mixes quickly.
DEFAULT_WARMUP: Final = 1000
DEFAULT_SAMPLES: Final = 1000
DEFAULT_CHAINS: Final = 2

#: Factors fitted by default. One is not enough: box-score rates share a large
#: position axis, and a single factor becomes that axis rather than impact.
DEFAULT_FACTORS: Final = 2
DEFAULT_SEED: Final = 20260910


class MissingDependencyError(ImportError):
    """NumPyro is needed to fit the fusion model."""


_MISSING = "numpyro and jax are required to fit the fusion model; install the 'fit' extra"


@dataclass(frozen=True)
class FusionFit:
    """Posterior summaries from one fit.

    Attributes:
        ratings: One row per player with the posterior mean of the latent
            quantity and an interval.
        loadings: One row per metric with its posterior loading, the bound
            reliability placed on it, and the share of the bound used.
        nba_seasons: Window fitted.
        anchor: Metric that defines the latent quantity.
        anchor_loading: How the anchor was constrained.
        n_factors: Factors fitted. Only the first is reported as a rating.
        draws: Posterior draws for ``intercept``, ``loading_matrix``,
            ``factors_by_player`` and ``scale``, kept only when the caller asks
            for them. They are what a posterior predictive check needs, and
            they are large, so they are not carried by default.
        diagnostics: Sampler diagnostics. ``max_r_hat`` covers the published
            quantities only, the first factor's scores and loadings.
            ``nuisance_r_hat`` covers the rotatable nuisance factors and is
            expected to be large; see :func:`fit_fusion` for why.
    """

    ratings: pd.DataFrame
    loadings: pd.DataFrame
    nba_seasons: tuple[int, ...]
    anchor: str
    anchor_loading: str
    n_factors: int
    diagnostics: dict[str, float]
    draws: dict[str, Any] | None = None

    @property
    def converged(self) -> bool:
        """True when the published quantities have an r-hat below 1.01.

        Deliberately ignores the nuisance factors, which are unidentified by
        construction and whose r-hat carries no information about whether the
        rating is stable.
        """
        return self.diagnostics.get("max_r_hat", float("inf")) < 1.01

    def describe(self) -> str:
        """Return a one-line summary including whether the sampler converged."""
        span = (
            f"{self.nba_seasons[0]}-{self.nba_seasons[-1]}"
            if len(self.nba_seasons) > 1
            else str(self.nba_seasons[0])
        )
        state = "converged" if self.converged else "NOT converged"
        return (
            f"NBA {span}: {len(self.ratings)} players, {len(self.loadings)} metrics, "
            f"{self.n_factors} factor(s), anchor {self.anchor!r} {self.anchor_loading}, "
            f"max r-hat {self.diagnostics.get('max_r_hat', float('nan')):.4f} ({state})"
        )


def _model(
    observations: Any,
    observed_mask: Any,
    bounds: Any,
    anchor_index: int,
    n_factors: int,
    fix_anchor: bool,
) -> None:
    """The NumPyro model. See the module docstring for the equations.

    Args:
        observations: Players by metrics, standardised, with zeros where
            unobserved. The zeros never reach the likelihood.
        observed_mask: True where a value was observed.
        bounds: Square root of each metric's measured reliability, capping the
            total length of its loading vector.
        anchor_index: Column that defines the first factor.
        n_factors: Factors to fit. One reproduces the original model and
            recovers position rather than impact; see the module docstring.
        fix_anchor: Hold the anchor's loading on the first factor at its bound.
    """
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist

    n_players, n_metrics = observations.shape

    with numpyro.plate("factors", n_factors, dim=-1), numpyro.plate("players", n_players, dim=-2):
        factors = numpyro.sample("factors_by_player", dist.Normal(0.0, 1.0))

    with numpyro.plate("metrics", n_metrics):
        # Columns are standardised, so an intercept should sit near zero.
        intercept = numpyro.sample("intercept", dist.Normal(0.0, 0.05))
    with (
        numpyro.plate("factors_for_metrics", n_factors, dim=-1),
        numpyro.plate("metrics_for_loadings", n_metrics, dim=-2),
    ):
        unconstrained = numpyro.sample("loading_unconstrained", dist.Normal(0.0, 1.0))

    # Map each metric's unconstrained vector smoothly into the ball of radius
    # sqrt(r), so the bound applies to its *total* reliable variance across
    # factors, which is what classical test theory actually claims.
    #
    # The obvious parameterisation, a unit direction times a separate length,
    # does not work. With one factor the direction collapses to a sign, which
    # is bimodal, and the sampler came back with an r-hat of 8. This map has no
    # such degeneracy: it is smooth and one-to-one from R^k onto the open ball
    # at every k, with no singularity at the origin.
    squared = jnp.sum(unconstrained**2, axis=-1, keepdims=True)
    loadings = bounds[:, None] * unconstrained / jnp.sqrt(1.0 + squared)

    if fix_anchor:
        # The anchor is pure first factor, by definition. Its loading there is
        # held at its bound and its loading on every nuisance factor is zero,
        # which is what stops the nuisance factors absorbing impact.
        anchor_row = jnp.zeros(n_factors).at[0].set(bounds[anchor_index])
        loadings = loadings.at[anchor_index].set(anchor_row)
    else:
        loadings = loadings.at[anchor_index, 0].set(jnp.abs(loadings[anchor_index, 0]))

    loadings = numpyro.deterministic("loading_matrix", loadings)
    numpyro.deterministic("loading", loadings[:, 0])

    explained = jnp.sum(loadings**2, axis=-1)
    scale = numpyro.deterministic(
        "scale", jnp.sqrt(jnp.clip(1.0 - explained, MIN_RESIDUAL_SCALE**2, 1.0))
    )

    expected = intercept[None, :] + factors @ loadings.T
    with numpyro.handlers.mask(mask=observed_mask):
        numpyro.sample("y", dist.Normal(expected, scale[None, :]), obs=observations)


def fit_fusion(
    dataset: FusionDataset,
    reliability: pd.Series,
    *,
    warmup: int = DEFAULT_WARMUP,
    samples: int = DEFAULT_SAMPLES,
    chains: int = DEFAULT_CHAINS,
    seed: int = DEFAULT_SEED,
    interval: float = 0.90,
    anchor_loading: str = "fixed",
    n_factors: int = DEFAULT_FACTORS,
    keep_draws: bool = False,
) -> FusionFit:
    """Fit the measurement-error model to one window.

    Args:
        dataset: The assembled player-by-metric table.
        reliability: Measured reliability per metric, between 0 and 1. A metric
            absent from this is given a bound of 1, meaning unconstrained, and
            that choice is visible in the returned loadings table.
        warmup: Sampler warmup iterations.
        samples: Posterior draws per chain.
        chains: Chains to run.
        seed: Seed for the sampler.
        interval: Credible interval width for the ratings.
        n_factors: Factors to fit. The default of 2 gives the model somewhere
            to put the position axis that dominates box-score rates. One factor
            recovers that axis instead of impact; see the module docstring.
        anchor_loading: ``"fixed"`` holds the anchor at its reliability bound,
            which defines what the latent quantity means. ``"positive"`` only
            fixes the sign, which is useful for showing what the box score
            contains on its own and produces a position axis rather than an
            impact one.
        keep_draws: Carry the posterior draws on the result. Needed for a
            posterior predictive check and otherwise a waste of memory.

    Returns:
        A :class:`FusionFit`.

    Raises:
        MissingDependencyError: If NumPyro is not installed.
        ValueError: If the anchor metric is absent, or ``anchor_loading`` is
            not one of the two accepted values.
    """
    if anchor_loading not in {"fixed", "positive"}:
        raise ValueError(f"anchor_loading must be 'fixed' or 'positive', got {anchor_loading!r}")
    try:
        import jax
        import numpyro
        from numpyro.infer import MCMC, NUTS
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError(_MISSING) from exc

    # JAX defaults to 32-bit floats, which was chosen for neural networks where
    # the gradient noise dwarfs the rounding. Here it showed up as a loading
    # held at a fixed bound coming back 1.3e-6 away from it. Sampling noise is
    # far larger than that, so the posterior is unaffected, but a quantity the
    # model states exactly should come back exactly, and a reader comparing two
    # runs should not have to wonder which differences are arithmetic. This is
    # process-wide because JAX offers no narrower switch.
    jax.config.update("jax_enable_x64", True)  # type: ignore[no-untyped-call]

    if dataset.anchor not in dataset.values.columns:
        raise ValueError(
            f"anchor {dataset.anchor!r} is not a column of the dataset; "
            f"the factor's sign would be unidentified"
        )

    numpyro.set_host_device_count(chains)

    frame = dataset.values
    metrics = list(frame.columns)
    raw_values = frame.to_numpy(dtype=np.float64)
    observed_mask = np.isfinite(raw_values)
    # Unobserved entries are masked out of the likelihood, so the value put
    # here is never read. Zero is used because NaN would propagate through the
    # gradient even under a mask.
    observations = np.where(observed_mask, raw_values, 0.0)

    bounds = np.array(
        [float(np.sqrt(min(max(reliability.get(name, 1.0), 0.0), 1.0))) for name in metrics]
    )
    anchor_index = metrics.index(dataset.anchor)

    kernel = NUTS(_model)
    mcmc = MCMC(
        kernel,
        num_warmup=warmup,
        num_samples=samples,
        num_chains=chains,
        progress_bar=False,
    )
    mcmc.run(
        jax.random.PRNGKey(seed),
        observations=observations,
        observed_mask=observed_mask,
        bounds=bounds,
        anchor_index=anchor_index,
        n_factors=n_factors,
        fix_anchor=anchor_loading == "fixed",
    )

    draws = mcmc.get_samples()
    # The first factor is the anchored one, and the only one reported as a
    # rating. The rest exist to absorb the shared structure that would
    # otherwise contaminate it.
    theta = np.asarray(draws["factors_by_player"])[:, :, 0]
    loading_matrix = np.asarray(draws["loading_matrix"])
    loading = loading_matrix[:, :, 0]

    tail = (1.0 - interval) / 2.0
    ratings = pd.DataFrame(
        {
            "nba_id": frame.index,
            "impact": theta.mean(axis=0),
            "sd": theta.std(axis=0, ddof=1),
            "lower": np.quantile(theta, tail, axis=0),
            "upper": np.quantile(theta, 1.0 - tail, axis=0),
        }
    ).sort_values("impact", ascending=False)

    loadings = pd.DataFrame(
        {
            "metric": metrics,
            "loading": loading.mean(axis=0),
            "loading_sd": loading.std(axis=0, ddof=1),
            "bound": bounds,
            "share_of_bound": np.abs(loading.mean(axis=0)) / np.where(bounds > 0, bounds, np.nan),
            "nuisance_length": np.sqrt(
                np.maximum((loading_matrix**2).sum(axis=-1) - loading**2, 0.0)
            ).mean(axis=0),
        }
    ).sort_values("loading", ascending=False)

    # Convergence is reported for the quantities this function returns, not
    # for every parameter in the model.
    #
    # With more than one factor the nuisance factors are rotatable and their
    # signs are free: rotating them and rotating their loadings the opposite
    # way leaves the likelihood unchanged. Different chains therefore settle on
    # different rotations, and an r-hat taken over those parameters comes back
    # in the hundreds while saying nothing about whether the answer is stable.
    # The first factor is not rotatable, because a rotation mixing it with a
    # nuisance factor would move the anchor's loading off the value it is
    # pinned at.
    #
    # So r-hat is computed on the first factor's player scores and loadings,
    # which are what get published, and the nuisance r-hat is reported beside
    # it rather than hidden, so the non-identification stays visible.
    grouped = mcmc.get_samples(group_by_chain=True)
    published_r_hat = float("nan")
    nuisance_r_hat = float("nan")
    if chains > 1:
        factor_chains = np.asarray(grouped["factors_by_player"])[..., 0]
        loading_chains = np.asarray(grouped["loading_matrix"])[..., 0]
        published_r_hat = float(
            max(
                np.nanmax(numpyro.diagnostics.gelman_rubin(factor_chains)),
                np.nanmax(numpyro.diagnostics.gelman_rubin(loading_chains)),
            )
        )
        if n_factors > 1:
            nuisance = np.asarray(grouped["factors_by_player"])[..., 1:]
            nuisance_r_hat = float(np.nanmax(numpyro.diagnostics.gelman_rubin(nuisance)))

    effective = (
        float(np.nanmin(numpyro.diagnostics.effective_sample_size(factor_chains)))
        if chains > 1
        else float("nan")
    )

    return FusionFit(
        ratings=ratings.reset_index(drop=True),
        loadings=loadings.reset_index(drop=True),
        nba_seasons=dataset.nba_seasons,
        anchor=dataset.anchor,
        anchor_loading=anchor_loading,
        n_factors=n_factors,
        draws=(
            {
                "intercept": np.asarray(draws["intercept"]),
                "loading_matrix": loading_matrix,
                "factors_by_player": np.asarray(draws["factors_by_player"]),
                "scale": np.asarray(draws["scale"]),
            }
            if keep_draws
            else None
        ),
        diagnostics={
            "max_r_hat": published_r_hat,
            "nuisance_r_hat": nuisance_r_hat,
            "min_n_eff": effective,
        },
    )
