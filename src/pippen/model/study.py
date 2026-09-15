"""The pipeline that turns seasons on disk into the project's published tables.

Why this module exists
----------------------
The five modules beneath it are each usable and were collectively unreachable.
Building a dataset, fitting the fusion, crossing two identifier spaces,
aggregating to team level, constructing next season's target and comparing
candidates took about 130 lines of assembly, and that assembly lived in
throwaway scripts. The tables in ``docs/methodology/claim-under-test.md`` were
produced by those scripts, so the documentation's claim that the results
reproduce from this package was false.

Every other published number in this project comes from a committed entry
point: ``pippen coefficient``, ``pippen rapm``, ``pippen gate``,
``pippen reliability``. This module restores that property for the model layer,
and ``pippen train`` and ``pippen evaluate`` sit on top of it.

The two identifier boundaries
-----------------------------
Both are crossed here, and both are silent when wrong.

hoopR labels a season by the year it ends and the NBA by the year it starts, so
a RAPM window over NBA 2016 to 2018 needs hoopR box scores for 2017 to 2019.
Player box scores carry ESPN athlete ids while possessions carry NBA player
ids, and team box scores and stints disagree the same way about team ids. A
mistake in any of these still produces a table of the right shape.

Everything here works in NBA labels, converting at the edges through
:mod:`pippen.seasons` and :mod:`pippen.crosswalk` rather than inline.

What a window is
----------------
A rating for the window ending in season N is built from N-2, N-1 and N, and is
scored against team net rating in N+1. The roster used to aggregate is the one
from season N, as it was, not as it became: knowing next season's roster would
leak information the predictor would not have at the time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import pandas as pd

from pippen.crosswalk import build_crosswalk, team_crosswalk
from pippen.model.attribution import AttributionResult, explain
from pippen.model.baselines import BaselineResult, run_baselines
from pippen.model.claim import (
    ClaimResult,
    PairedComparison,
    aggregate_to_team,
    compare_candidates,
    paired_comparison,
    team_ratings,
)
from pippen.model.dataset import RAPM_COLUMN, build_fusion_dataset
from pippen.model.fusion import DEFAULT_FACTORS, FusionFit, fit_fusion
from pippen.model.panel import TeamPanel
from pippen.paths import season_file, stage_dir
from pippen.rapm.possessions import possessions_by_player, read_season_stints
from pippen.reliability.metrics import eligible_rows
from pippen.repro import DEFAULT_SEED
from pippen.seasons import hoopr_from_nba

#: Column the fused rating takes in the panel.
FUSION_COLUMN: Final = "fusion"

#: Seasons pooled into one rating by default.
DEFAULT_WINDOW: Final = 3

#: RAPM's measured split-half reliability at three seasons, from
#: ``docs/methodology/rapm-validation.md``. Used as its loading bound, which is
#: what defines the latent quantity; see ADR 0005.
RAPM_RELIABILITY: Final = 0.796

#: Where the measured metric reliabilities are written by ``pippen reliability``.
RELIABILITY_FILE: Final = "metric_reliability.parquet"


class MissingReliabilityError(FileNotFoundError):
    """The measured reliability table has not been produced yet."""


def load_measured_reliability() -> pd.Series:
    """Return each metric's measured reliability, with RAPM's added.

    Returns:
        Reliability per metric name, at 82 games, averaged over seasons.

    Raises:
        MissingReliabilityError: If ``pippen reliability`` has not been run.
    """
    path = stage_dir("processed") / RELIABILITY_FILE
    if not path.exists():
        raise MissingReliabilityError(
            f"no measured reliability at {path}; run `pippen reliability` first"
        )
    table = pd.read_parquet(path)
    measured = table[table["rule"] == "random"].groupby("metric")["reliability_at_82_games"].mean()
    measured.loc[RAPM_COLUMN] = RAPM_RELIABILITY
    return measured


def _roster(nba_season: int) -> tuple[pd.Series, pd.Series, dict[int, int]]:
    """Return each player's team and minutes for one season, in NBA ids.

    A player who changed teams is assigned the one he played most minutes for,
    since the aggregate needs exactly one team per player.

    Args:
        nba_season: Season start year.

    Returns:
        Team per NBA player id, minutes per NBA player id, and the NBA to ESPN
        team id mapping for that season.
    """
    box = eligible_rows(
        pd.read_parquet(season_file("raw", "player_box", hoopr_from_nba(nba_season)))
    )
    by_team = box.groupby(["athlete_id", "team_id"])["minutes"].sum().reset_index()
    most = by_team.sort_values("minutes").groupby("athlete_id").tail(1)

    played = possessions_by_player(read_season_stints(nba_season)).index
    crosswalk = build_crosswalk(
        box[["athlete_id", "athlete_display_name"]].drop_duplicates(),
        season=hoopr_from_nba(nba_season),
        played_nba_ids=played,
    )
    most = most.assign(nba_id=most["athlete_id"].map(crosswalk.espn_to_nba)).dropna(
        subset=["nba_id"]
    )
    most["nba_id"] = most["nba_id"].astype(int)

    teams = team_crosswalk(box[["team_id", "team_abbreviation"]].drop_duplicates())
    return (
        most.set_index("nba_id")["team_id"],
        most.set_index("nba_id")["minutes"],
        teams,
    )


@dataclass(frozen=True)
class WindowFit:
    """One window's fusion fit, kept so a caller can inspect it.

    Attributes:
        nba_seasons: Seasons pooled.
        target_season: Season whose net rating this window predicts.
        fit: The fitted fusion model.
    """

    nba_seasons: tuple[int, ...]
    target_season: int
    fit: FusionFit


def build_team_panel(
    nba_seasons: Sequence[int],
    *,
    window: int = DEFAULT_WINDOW,
    n_factors: int = DEFAULT_FACTORS,
    warmup: int = 1000,
    samples: int = 1000,
    chains: int = 2,
    seed: int = DEFAULT_SEED,
    reliability: pd.Series | None = None,
    on_progress: object = None,
) -> tuple[TeamPanel, list[WindowFit]]:
    """Build the team-season panel every candidate is scored on.

    One rolling window per target season. Each window fits the fusion model,
    aggregates every candidate to team level by minutes, and pairs the result
    with the following season's net rating.

    Args:
        nba_seasons: Seasons available, NBA labels, contiguous and ascending.
            The last one supplies a target and contributes no row of its own.
        window: Seasons pooled into one rating.
        n_factors: Factors in the fusion model.
        warmup: Sampler warmup iterations.
        samples: Posterior draws per chain.
        chains: Chains to run.
        seed: Seed for the sampler.
        reliability: Measured reliability per metric. Loaded from the processed
            stage when omitted.
        on_progress: Called with each :class:`WindowFit` as it completes.

    Returns:
        The panel and one fit per window.

    Raises:
        ValueError: If fewer seasons are given than a window plus its target.
        MissingReliabilityError: If reliability is needed and not on disk.
    """
    seasons = sorted(int(season) for season in nba_seasons)
    if len(seasons) < window + 1:
        raise ValueError(
            f"{len(seasons)} seasons is too few for a {window}-season window plus a "
            f"target season; at least {window + 1} are needed"
        )

    bounds = load_measured_reliability() if reliability is None else reliability

    rows: list[dict[str, object]] = []
    fits: list[WindowFit] = []
    for end in seasons[window - 1 : -1]:
        span = tuple(range(end - window + 1, end + 1))
        dataset, _ = build_fusion_dataset(span)
        fit = fit_fusion(
            dataset,
            bounds,
            warmup=warmup,
            samples=samples,
            chains=chains,
            n_factors=n_factors,
            seed=seed,
        )

        candidates = dataset.values.copy()
        candidates[FUSION_COLUMN] = fit.ratings.set_index("nba_id")["impact"]

        team_of, minutes, nba_to_espn = _roster(end)
        nba_target = team_ratings(end + 1).table["net_rating"]
        target = pd.Series(
            {
                nba_to_espn[team]: value
                for team, value in zip(nba_target.index, nba_target, strict=True)
                if team in nba_to_espn
            }
        )

        for name in candidates.columns:
            aggregated = aggregate_to_team(candidates[name], minutes, team_of)
            for team_id, value in zip(aggregated.index, aggregated, strict=True):
                rows.append(
                    {
                        "season": end,
                        "team_id": int(team_id),
                        "candidate": name,
                        "value": float(value),
                        "target": float(target.get(int(team_id), np.nan)),
                    }
                )

        record = WindowFit(nba_seasons=span, target_season=end + 1, fit=fit)
        fits.append(record)
        if on_progress is not None:
            on_progress(record)  # type: ignore[operator]

    long = pd.DataFrame(rows)
    wide = long.pivot_table(index=["season", "team_id"], columns="candidate", values="value")
    targets = (
        long.drop_duplicates(["season", "team_id"])
        .set_index(["season", "team_id"])["target"]
        .reindex(wide.index)
    )
    return TeamPanel.build(wide, targets), fits


@dataclass(frozen=True)
class ClaimReport:
    """Everything the claim under test produces, from one call.

    Attributes:
        single: Every candidate scored on its own.
        baselines: Supervised models over every candidate at once.
        box_only_baselines: The same, with RAPM and the fused rating removed,
            which asks what the box score can do alone.
        attribution: SHAP importances from the best baseline's fitted model.
        comparisons: Paired tests of the leading single candidate against
            others, so a gap in the table is tested rather than eyeballed.
    """

    single: ClaimResult
    baselines: list[BaselineResult]
    box_only_baselines: list[BaselineResult] = field(default_factory=list)
    attribution: AttributionResult | None = None
    comparisons: list[PairedComparison] = field(default_factory=list)

    @property
    def winner(self) -> str:
        """Name of the single candidate with the lowest error."""
        return self.single.winner

    def describe(self) -> str:
        """Return a one-line verdict, phrased the same way whichever way it goes."""
        best_baseline = self.baselines[0] if self.baselines else None
        tail = (
            f", best baseline {best_baseline.name} {best_baseline.rmse:.3f}"
            if best_baseline
            else ""
        )
        return f"{self.single.describe()}{tail}"


def evaluate_claim(
    panel: TeamPanel,
    *,
    trials: int = 40,
    seed: int = DEFAULT_SEED,
    experiment: str | None = "pippen-baselines",
    against: Sequence[str] = (FUSION_COLUMN, "true_shooting", "points_per_36"),
) -> ClaimReport:
    """Run every comparison the claim under test needs.

    Args:
        panel: The team-season table.
        trials: Optuna trials per search, per baseline.
        seed: Seed for the samplers.
        experiment: MLflow experiment name, or ``None`` to skip tracking.
        against: Candidates to test the winner against, pairwise.

    Returns:
        A :class:`ClaimReport`.
    """
    single = compare_candidates(panel)
    baselines = run_baselines(panel, trials=trials, seed=seed, experiment=experiment)
    box_only = run_baselines(
        panel.without(RAPM_COLUMN, FUSION_COLUMN),
        trials=trials,
        seed=seed,
        experiment=None if experiment is None else f"{experiment}-box-only",
    )

    attribution = None
    if baselines and baselines[0].fitted is not None:
        try:
            attribution = explain(baselines[0].fitted, panel.features, seed=seed)
        except (ValueError, TypeError):  # pragma: no cover - a linear best baseline
            attribution = None

    comparisons = []
    if not single.table.empty:
        best = str(single.table.iloc[0]["candidate"])
        for other in against:
            if other == best or other not in single.squared_errors.columns:
                continue
            comparisons.append(paired_comparison(single, best, other))

    return ClaimReport(
        single=single,
        baselines=baselines,
        box_only_baselines=box_only,
        attribution=attribution,
        comparisons=comparisons,
    )
