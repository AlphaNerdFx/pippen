"""Tests for the fusion dataset assembler.

The assembler crosses both of the project's identifier boundaries at once, the
season labelling and the player ids, and an error in either produces a table
that still has the right shape. These check the arithmetic that would otherwise
go unnoticed: that the window is pooled before metrics are computed rather than
after, and that standardising is reversible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.model.dataset import RAPM_COLUMN, FusionDataset
from pippen.seasons import describe, hoopr_from_nba, nba_from_hoopr


def _dataset(n_players: int = 40, seed: int = 4) -> FusionDataset:
    rng = np.random.default_rng(seed)
    index = pd.Index(range(1, n_players + 1), name="nba_id")
    raw = pd.DataFrame(
        {
            "points_per_36": rng.normal(18.0, 4.0, n_players),
            "true_shooting": rng.normal(0.56, 0.04, n_players),
            RAPM_COLUMN: rng.normal(0.0, 2.0, n_players),
        },
        index=index,
    )
    centres = raw.mean()
    scales = raw.std(ddof=0)
    return FusionDataset(
        values=(raw - centres) / scales,
        raw=raw,
        centres=centres,
        scales=scales,
        minutes=pd.Series(rng.uniform(1000, 3000, n_players), index=index),
        possessions=pd.Series(rng.uniform(4000, 20000, n_players), index=index),
        nba_seasons=(2016, 2017, 2018),
        anchor=RAPM_COLUMN,
    )


# ------------------------------------------------------------------ seasons


def test_the_season_conversion_round_trips() -> None:
    for nba_season in range(2002, 2026):
        assert nba_from_hoopr(hoopr_from_nba(nba_season)) == nba_season


def test_hoopr_is_one_ahead_of_the_nba() -> None:
    # hoopR's 2017 file holds the 2016-17 season, which the NBA calls 2016.
    assert hoopr_from_nba(2016) == 2017
    assert nba_from_hoopr(2024) == 2023


def test_a_season_describes_itself_unambiguously() -> None:
    assert describe(2016) == "2016-17"
    assert describe(1999) == "1999-00"


# ------------------------------------------------------------------ the table


def test_standardising_is_reversible() -> None:
    dataset = _dataset()
    recovered = dataset.values * dataset.scales + dataset.centres
    assert np.allclose(recovered.to_numpy(), dataset.raw.to_numpy())


def test_every_column_is_centred_and_scaled() -> None:
    dataset = _dataset()
    assert np.allclose(dataset.values.mean().to_numpy(), 0.0, atol=1e-10)
    assert np.allclose(dataset.values.std(ddof=0).to_numpy(), 1.0, atol=1e-10)


def test_the_anchor_is_present_as_a_column() -> None:
    dataset = _dataset()
    assert dataset.anchor in dataset.metrics
    assert dataset.anchor == RAPM_COLUMN


def test_the_summary_reports_how_complete_the_table_is() -> None:
    dataset = _dataset()
    text = dataset.describe()
    assert "2016-2018" in text
    assert "100.0% observed" in text
    assert dataset.n_players == 40


def test_missing_values_are_reported_rather_than_filled() -> None:
    # The model treats an absent metric as unobserved. A zero would be read as
    # exactly league average, which is a much stronger claim than "unknown".
    dataset = _dataset()
    holed = dataset.values.copy()
    holed.iloc[0, 0] = np.nan
    replaced = FusionDataset(
        values=holed,
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=dataset.nba_seasons,
        anchor=dataset.anchor,
    )
    assert "99.2% observed" in replaced.describe()
    assert replaced.values.isna().sum().sum() == 1


def test_a_single_season_window_describes_itself_without_a_range() -> None:
    dataset = _dataset()
    single = FusionDataset(
        values=dataset.values,
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=(2016,),
        anchor=dataset.anchor,
    )
    assert "NBA 2016:" in single.describe()


def test_a_constant_column_does_not_divide_by_zero() -> None:
    # A metric with no spread carries no information and must not become
    # infinities that quietly poison the fit.
    index = pd.Index([1, 2, 3], name="nba_id")
    raw = pd.DataFrame({"flat": [1.0, 1.0, 1.0], RAPM_COLUMN: [0.0, 1.0, 2.0]}, index=index)
    scales = raw.std(ddof=0).replace(0.0, np.nan)
    values = (raw - raw.mean()) / scales
    assert values["flat"].isna().all()
    assert np.isfinite(values[RAPM_COLUMN]).all()


@pytest.mark.parametrize("seasons", [(2016,), (2016, 2017), (2016, 2017, 2018)])
def test_windows_of_any_length_are_described(seasons: tuple[int, ...]) -> None:
    dataset = _dataset()
    window = FusionDataset(
        values=dataset.values,
        raw=dataset.raw,
        centres=dataset.centres,
        scales=dataset.scales,
        minutes=dataset.minutes,
        possessions=dataset.possessions,
        nba_seasons=seasons,
        anchor=dataset.anchor,
    )
    assert str(seasons[0]) in window.describe()
