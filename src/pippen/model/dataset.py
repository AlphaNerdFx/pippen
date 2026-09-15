r"""Assembling the player-by-metric table the fusion model consumes.

What has to line up
-------------------
The measurement-error model treats every metric as a noisy reading of one
latent quantity per player:

.. math::

    y_{p,m} = \alpha_m + \beta_m \theta_p + \varepsilon_{p,m}

To fit that, every metric has to be observed for the same set of players over
the same stretch of basketball. Three things make that harder than it sounds.

The two sources label seasons differently
    hoopR names a season by the year it ends and the NBA by the year it starts,
    so a RAPM window over NBA 2016 to 2018 needs hoopR box scores for 2017 to
    2019. The conversion goes through :mod:`pippen.seasons` rather than being
    done inline, because an off-by-one here shifts every player's inputs by a
    year and nothing downstream would notice.

The two sources identify players differently
    Box scores carry ESPN athlete ids, possessions carry NBA player ids, and
    there is no shared key. :mod:`pippen.crosswalk` resolves it, and reports
    the residue rather than dropping it quietly.

The window has to be pooled before the metrics are computed, not after
    RAPM over three seasons is one rating fitted on three seasons of
    possessions. The box-score side has to match, so counting stats are summed
    across the window first and each metric computed once on the pooled totals.
    Averaging three single-season true-shooting figures would weight a
    20-minute season the same as a 2,500-minute one and would not be the same
    quantity.

Standardising
-------------
Each column is centred and scaled across the players in the window. The model
needs that for two reasons. The metrics arrive on wildly different scales,
from a three-point rate near 0.4 to points per 36 near 20, and a shared prior
on the loadings would otherwise mean different things for different metrics.
And the latent quantity has no natural units, so its scale has to be fixed
somewhere; fixing it at the anchor metric is cleaner when every column already
has unit variance.

The mean and standard deviation used are kept, so a fitted value can be put
back on its original scale.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

import numpy as np
import pandas as pd

from pippen.crosswalk import Crosswalk, build_crosswalk
from pippen.paths import season_file
from pippen.rapm.design import build_design
from pippen.rapm.possessions import possessions_by_player, read_season_stints
from pippen.rapm.ridge import fit_ridge
from pippen.reliability.metrics import METRICS, compute, eligible_rows, summarise_totals
from pippen.seasons import hoopr_from_nba

#: Name the RAPM column takes in the assembled table.
RAPM_COLUMN: Final = "rapm"

#: Minutes a player needs across the whole window to be included.
DEFAULT_MINUTES_FLOOR: Final = 1000.0

#: Possessions a player needs across the whole window to carry a RAPM rating
#: worth using. Below this the rating is mostly the ridge prior.
DEFAULT_POSSESSION_FLOOR: Final = 2000.0


class MissingSeasonError(FileNotFoundError):
    """A season needed for the window has not been prepared."""


@dataclass(frozen=True)
class FusionDataset:
    """Players by metrics, ready to fit.

    Attributes:
        values: Standardised metric values, players on the index and metrics on
            the columns. Missing entries are ``NaN`` and the model treats them
            as unobserved rather than as zero.
        raw: The same table before standardising.
        centres: Mean subtracted from each column.
        scales: Standard deviation divided out of each column.
        minutes: Minutes each player played across the window.
        possessions: Possessions behind each player's RAPM rating.
        nba_seasons: Seasons pooled, in NBA labels.
        anchor: Column whose loading is fixed to identify the latent scale.
    """

    values: pd.DataFrame
    raw: pd.DataFrame
    centres: pd.Series
    scales: pd.Series
    minutes: pd.Series
    possessions: pd.Series
    nba_seasons: tuple[int, ...]
    anchor: str

    def with_values(self, values: pd.DataFrame) -> FusionDataset:
        """Return a copy carrying different standardised values.

        Every other field describes the same players over the same window, so
        replacing the values alone is the only change a caller should be
        making. Exposing it here keeps the eight-field copy in one place;
        callers previously rebuilt the dataclass by hand, which meant a field
        added later would be silently dropped by whichever caller nobody
        remembered to update.

        Args:
            values: Replacement table, same index and columns.

        Returns:
            A new dataset. The original is unchanged.
        """
        return replace(self, values=values)

    @property
    def n_players(self) -> int:
        """Players in the table."""
        return len(self.values)

    @property
    def metrics(self) -> tuple[str, ...]:
        """Metric columns, anchor included."""
        return tuple(self.values.columns)

    def describe(self) -> str:
        """Return a one-line summary including how complete the table is."""
        filled = float(self.values.notna().to_numpy().mean())
        span = (
            f"{self.nba_seasons[0]}-{self.nba_seasons[-1]}"
            if len(self.nba_seasons) > 1
            else str(self.nba_seasons[0])
        )
        return (
            f"NBA {span}: {self.n_players} players x {len(self.metrics)} metrics, "
            f"{filled:.1%} observed, anchored on {self.anchor!r}"
        )


def _pooled_box_totals(
    nba_seasons: tuple[int, ...],
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    """Sum box-score counting stats across the window, keyed by ESPN id.

    Args:
        nba_seasons: Seasons in the window, NBA labels.

    Returns:
        The pooled totals, and each season's eligible rows keyed by NBA label,
        the latter needed to build a per-season crosswalk.

    Raises:
        MissingSeasonError: If a season's box score is not on disk.
    """
    per_season: dict[int, pd.DataFrame] = {}
    frames: list[pd.DataFrame] = []
    for nba_season in nba_seasons:
        hoopr_season = hoopr_from_nba(nba_season)
        path = season_file("raw", "player_box", hoopr_season)
        if not path.exists():
            raise MissingSeasonError(
                f"no player box for hoopR {hoopr_season} (NBA {nba_season}) at {path}"
            )
        rows = eligible_rows(pd.read_parquet(path))
        per_season[nba_season] = rows
        frames.append(rows)

    pooled = pd.concat(frames, ignore_index=True)
    return summarise_totals(pooled), per_season


def _window_crosswalk(
    per_season: dict[int, pd.DataFrame], played: dict[int, set[int]]
) -> tuple[dict[int, int], list[Crosswalk]]:
    """Resolve ESPN ids to NBA ids across every season in the window.

    Resolved per season and then unioned, because the season-presence check is
    what makes the name passes safe and it only works one season at a time.
    Later seasons win a conflict, which matters only for the handful of ids
    that change, and is recorded in the returned crosswalks either way.

    Args:
        per_season: Eligible box rows for each NBA season.
        played: NBA player ids appearing in each season's possessions.

    Returns:
        The merged mapping and the per-season crosswalks behind it.
    """
    merged: dict[int, int] = {}
    built: list[Crosswalk] = []
    for nba_season in sorted(per_season):
        rows = per_season[nba_season]
        players = rows[["athlete_id", "athlete_display_name"]].drop_duplicates()
        crosswalk = build_crosswalk(
            players,
            season=hoopr_from_nba(nba_season),
            played_nba_ids=played.get(nba_season, set()),
        )
        merged.update(crosswalk.espn_to_nba)
        built.append(crosswalk)
    return merged, built


def build_fusion_dataset(
    nba_seasons: tuple[int, ...],
    *,
    alpha: float = 3000.0,
    minutes_floor: float = DEFAULT_MINUTES_FLOOR,
    possession_floor: float = DEFAULT_POSSESSION_FLOOR,
) -> tuple[FusionDataset, list[Crosswalk]]:
    """Assemble the table for one multi-season window.

    Args:
        nba_seasons: Seasons to pool, NBA labels, contiguous.
        alpha: Ridge penalty for the RAPM fit.
        minutes_floor: Minutes a player needs across the window.
        possession_floor: Possessions a player needs for his RAPM rating.

    Returns:
        The dataset and the per-season crosswalks, so the join's residue can be
        inspected rather than assumed.

    Raises:
        MissingSeasonError: If a season's box score or stints are missing.
        ValueError: If no player clears both floors.
    """
    totals, per_season = _pooled_box_totals(nba_seasons)

    stint_frames = []
    played: dict[int, set[int]] = {}
    for nba_season in nba_seasons:
        try:
            stints = read_season_stints(nba_season)
        except FileNotFoundError as exc:
            raise MissingSeasonError(str(exc)) from exc
        stint_frames.append(stints)
        played[nba_season] = {int(pid) for pid in possessions_by_player(stints).index}

    pooled_stints = pd.concat(stint_frames, ignore_index=True)
    design = build_design(pooled_stints)
    ratings = fit_ridge(design, alpha).ratings().set_index("player_id")["total"]
    possessions = possessions_by_player(pooled_stints)

    mapping, crosswalks = _window_crosswalk(per_season, played)

    qualified = totals[totals["minutes"] >= minutes_floor].copy()
    qualified["nba_id"] = [mapping.get(int(espn)) for espn in qualified.index]
    qualified = qualified[qualified["nba_id"].notna()]
    qualified["nba_id"] = qualified["nba_id"].astype(int)

    enough = qualified["nba_id"].map(possessions).fillna(0.0) >= possession_floor
    qualified = qualified[enough]
    if qualified.empty:
        raise ValueError(
            f"no player cleared {minutes_floor:.0f} minutes and "
            f"{possession_floor:.0f} possessions in NBA {nba_seasons}"
        )

    indexed = qualified.set_index("nba_id")
    columns: dict[str, pd.Series] = {}
    # Metrics are computed on the pooled totals, so the window is one
    # measurement rather than an average of per-season ones.
    last_season = hoopr_from_nba(nba_seasons[-1])
    for metric in METRICS:
        columns[metric.name] = compute(metric, indexed, last_season)
    columns[RAPM_COLUMN] = indexed.index.to_series().map(ratings)

    raw = pd.DataFrame(columns, index=indexed.index)
    raw.index.name = "nba_id"

    centres = raw.mean()
    scales = raw.std(ddof=0).replace(0.0, np.nan)
    values = (raw - centres) / scales

    dataset = FusionDataset(
        values=values,
        raw=raw,
        centres=centres,
        scales=scales,
        minutes=indexed["minutes"],
        possessions=indexed.index.to_series().map(possessions),
        nba_seasons=tuple(nba_seasons),
        anchor=RAPM_COLUMN,
    )
    return dataset, crosswalks
