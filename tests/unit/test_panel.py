"""Tests for the team-season panel.

The panel exists to make one guarantee enforceable: every candidate is scored
on the same team-seasons. That was previously a comment, and two modules
disagreed about it. These check the guarantee holds and that the folds cannot
put a season on both sides of a split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pippen.model.panel import (
    EmptyPanelError,
    Fold,
    NotEnoughSeasonsError,
    TeamPanel,
)


def _frame(seasons: int = 4, teams: int = 30, seed: int = 5) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2016 + seasons):
        for team in range(teams):
            rows.append(
                {
                    "season": season,
                    "team_id": team,
                    "a": rng.normal(),
                    "b": rng.normal(),
                    "target": rng.normal(0.0, 4.0),
                }
            )
    frame = pd.DataFrame(rows).set_index(["season", "team_id"])
    return frame[["a", "b"]], frame["target"]


# ------------------------------------------------------------------ construction


def test_rows_without_a_target_are_dropped() -> None:
    # A candidate cannot be scored on a row with nothing to predict, and two
    # modules previously disagreed about whether to drop it.
    features, target = _frame(seasons=2, teams=10)
    target.iloc[:5] = np.nan
    panel = TeamPanel.build(features, target)
    assert panel.n_observations == 15
    assert panel.target.notna().all()


def test_a_panel_with_no_targets_is_refused() -> None:
    features, target = _frame(seasons=2, teams=5)
    with pytest.raises(EmptyPanelError, match="next-season target"):
        TeamPanel.build(features, pd.Series(np.nan, index=target.index))


def test_seasons_come_from_the_index() -> None:
    features, target = _frame(seasons=3, teams=4)
    panel = TeamPanel.build(features, target)
    assert sorted(panel.seasons.unique()) == [2016, 2017, 2018]


def test_the_target_is_aligned_to_the_features() -> None:
    features, target = _frame(seasons=2, teams=6)
    shuffled = target.sample(frac=1.0, random_state=3)
    panel = TeamPanel.build(features, shuffled)
    assert (panel.target.index == panel.features.index).all()
    assert panel.target.loc[features.index[0]] == target.loc[features.index[0]]


# ------------------------------------------------------------------ candidates


def test_candidates_can_be_dropped_and_selected() -> None:
    features, target = _frame(seasons=2, teams=5)
    panel = TeamPanel.build(features, target)
    assert panel.candidates == ("a", "b")
    assert panel.without("a").candidates == ("b",)
    assert panel.only("a").candidates == ("a",)


def test_dropping_a_candidate_that_is_absent_is_not_an_error() -> None:
    # A window need not carry every column, and a caller should not have to
    # know which ones it happened to have.
    features, target = _frame(seasons=2, teams=5)
    panel = TeamPanel.build(features, target)
    assert panel.without("never_present").candidates == ("a", "b")


def test_dropping_does_not_mutate_the_original() -> None:
    features, target = _frame(seasons=2, teams=5)
    panel = TeamPanel.build(features, target)
    panel.without("a")
    assert panel.candidates == ("a", "b")


# ------------------------------------------------------------------ folds


def test_one_fold_per_season() -> None:
    features, target = _frame(seasons=4, teams=10)
    panel = TeamPanel.build(features, target)
    folds = panel.folds()
    assert [fold.held_out for fold in folds] == [2016, 2017, 2018, 2019]


def test_a_season_is_never_on_both_sides_of_a_split() -> None:
    features, target = _frame(seasons=4, teams=10)
    panel = TeamPanel.build(features, target)
    for fold in panel.folds():
        assert not bool((fold.train & fold.test).any())
        assert set(panel.seasons[fold.test]) == {fold.held_out}
        assert fold.held_out not in set(panel.seasons[fold.train])


def test_every_row_is_held_out_exactly_once() -> None:
    features, target = _frame(seasons=4, teams=10)
    panel = TeamPanel.build(features, target)
    counts = pd.concat([fold.test.astype(int) for fold in panel.folds()], axis=1).sum(axis=1)
    assert bool((counts == 1).all())


def test_inner_folds_exclude_the_outer_held_out_season() -> None:
    # This is what makes nested selection nested. If the outer season leaked
    # into the inner search, the tuning would see what it is later scored on.
    features, target = _frame(seasons=4, teams=10)
    panel = TeamPanel.build(features, target)
    inner = panel.folds(over=[2016, 2017, 2018])
    assert [fold.held_out for fold in inner] == [2016, 2017, 2018]
    for fold in inner:
        assert 2019 not in set(panel.seasons[fold.train])
        assert 2019 not in set(panel.seasons[fold.test])


def test_one_season_cannot_be_split() -> None:
    features, target = _frame(seasons=1, teams=10)
    panel = TeamPanel.build(features, target)
    with pytest.raises(NotEnoughSeasonsError, match="at least two"):
        panel.folds()


def test_a_fold_reports_whether_it_is_worth_fitting() -> None:
    index = pd.MultiIndex.from_tuples([(2016, 1), (2017, 1)], names=["season", "team_id"])
    thin = Fold(
        held_out=2017,
        train=pd.Series([True, False], index=index),
        test=pd.Series([False, True], index=index),
    )
    assert not thin.usable


def test_the_summary_names_the_span() -> None:
    features, target = _frame(seasons=3, teams=10)
    described = TeamPanel.build(features, target).describe()
    assert "2016-2018" in described
    assert "2 candidates" in described
