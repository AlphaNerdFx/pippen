"""Tests for the pipeline module.

Most of what `study` does needs seasons on disk, so the end-to-end path is
exercised by running `pippen evaluate` rather than here. What these cover is the
arithmetic and the guards that would otherwise only fail after several minutes
of fitting: the window arithmetic, the reliability bound RAPM is given, and the
refusals that should happen before any compute starts.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pippen import paths
from pippen.model.claim import ClaimResult
from pippen.model.study import (
    DEFAULT_WINDOW,
    FUSION_COLUMN,
    RAPM_RELIABILITY,
    ClaimReport,
    MissingReliabilityError,
    WindowFit,
    build_team_panel,
    load_measured_reliability,
)

# ------------------------------------------------------------------ guards


def test_too_few_seasons_is_refused_before_any_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A three-season window needs a fourth season to supply a target. Failing
    # here costs nothing; failing after the first fit costs minutes.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    with pytest.raises(ValueError, match="too few for a 3-season window"):
        build_team_panel([2016, 2017, 2018], window=3)


def test_a_missing_reliability_table_names_the_command_that_makes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    with pytest.raises(MissingReliabilityError, match="pippen reliability"):
        load_measured_reliability()


# ------------------------------------------------------------------ reliability


def test_rapm_is_given_its_measured_three_season_reliability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This number is RAPM's loading bound, which is what defines the latent
    # quantity. It comes from the validation report, not from the table that
    # `pippen reliability` writes, so it has to be added here.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "metric": ["points_per_36", "points_per_36"],
            "season": [2023, 2024],
            "rule": ["random", "random"],
            "reliability_at_82_games": [0.96, 0.97],
        }
    ).to_parquet(processed / "metric_reliability.parquet")

    measured = load_measured_reliability()
    assert measured.loc["rapm"] == RAPM_RELIABILITY
    assert measured.loc["points_per_36"] == pytest.approx(0.965)


def test_only_the_random_split_rule_is_averaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Odd-even is reported alongside as a comparison. Averaging both rules
    # together would silently mix two estimators.
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "metric": ["points_per_36", "points_per_36"],
            "season": [2024, 2024],
            "rule": ["random", "odd_even"],
            "reliability_at_82_games": [0.90, 0.10],
        }
    ).to_parquet(processed / "metric_reliability.parquet")

    assert load_measured_reliability().loc["points_per_36"] == pytest.approx(0.90)


# ------------------------------------------------------------------ reporting


def _claim_result(candidates: list[str], errors: list[float]) -> ClaimResult:
    return ClaimResult(
        table=pd.DataFrame(
            {"candidate": candidates, "rmse": errors, "vs_best": [e - errors[0] for e in errors]}
        ),
        squared_errors=pd.DataFrame({name: [1.0] for name in candidates}),
        observations=180,
        folds=6,
    )


def test_the_report_names_the_winning_single_candidate() -> None:
    report = ClaimReport(single=_claim_result(["rapm", FUSION_COLUMN], [4.38, 4.48]), baselines=[])
    assert report.winner == "rapm"
    assert "fusion does not win" in report.describe()


def test_the_report_says_so_when_the_fusion_wins() -> None:
    report = ClaimReport(single=_claim_result([FUSION_COLUMN, "rapm"], [4.20, 4.38]), baselines=[])
    assert report.winner == FUSION_COLUMN
    assert "fusion wins" in report.describe()


def test_a_window_fit_records_which_season_it_predicts() -> None:
    record = WindowFit(nba_seasons=(2016, 2017, 2018), target_season=2019, fit=None)  # type: ignore[arg-type]
    assert record.target_season == 2019
    assert record.nba_seasons[-1] + 1 == record.target_season


def test_the_default_window_is_three_seasons() -> None:
    # Single-season RAPM measures 0.601 and three-season 0.796, which is the
    # reason the default is not one.
    assert DEFAULT_WINDOW == 3
