"""Tests for the public API and the tables shipped inside the wheel.

This is the surface other people import, so it is the one place where a change
is a breaking change rather than a refactor. The tests below are deliberately
about the contract rather than the numbers: which names exist, what shape comes
back, what happens at the edges, and whether a caller can corrupt the cached
tables for everyone else in the process.
"""

from __future__ import annotations

import pytest

import pippen
from pippen.published import MissingBundledDataError, _read

# ------------------------------------------------------------------ the contract


def test_every_exported_name_exists() -> None:
    # A name in __all__ that is not importable makes `from pippen import *`
    # raise, and breaks documentation generators that walk the list.
    for name in pippen.__all__:
        assert hasattr(pippen, name), name


def test_the_public_surface_is_exactly_these_names() -> None:
    # Changing this set is a breaking change. The test exists so that the
    # decision is made deliberately rather than by adding an import.
    assert set(pippen.__all__) == {
        "FIRST_RAPM_SEASON",
        "LAST_RAPM_SEASON",
        "__version__",
        "metric_reliability",
        "possession_coefficient",
        "rapm_ratings",
    }


def test_the_version_is_a_release_rather_than_a_placeholder() -> None:
    assert pippen.__version__ != "0.0.0"
    parts = pippen.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


# ------------------------------------------------------------------ bundled data


def test_the_shipped_tables_are_present() -> None:
    # The failure this guards is quiet: package data declared for the wheel but
    # missing from the sdist builds an importable package that raises on first
    # real use, on someone else's machine.
    assert not _read("rapm_ratings.parquet").empty
    assert not _read("metric_reliability.parquet").empty


def test_a_missing_table_blames_the_build_rather_than_the_user() -> None:
    with pytest.raises(MissingBundledDataError, match="wheel was built without its data"):
        _read("a_table_that_was_never_shipped.parquet")


def test_the_cache_cannot_be_corrupted_by_a_caller() -> None:
    # _read is cached, so a caller that mutated what it received would change
    # what the next caller sees, anywhere in the process.
    first = pippen.rapm_ratings()
    first.loc[first.index[0], "total"] = -999.0
    second = pippen.rapm_ratings()
    assert second.loc[second.index[0], "total"] != -999.0


# ------------------------------------------------------------------ ratings


def test_ratings_carry_both_components_and_their_sum() -> None:
    ratings = pippen.rapm_ratings(window_end=2024)
    assert {"player", "offensive", "defensive", "total", "possessions"} <= set(ratings.columns)
    assert ratings["total"].sub(ratings["offensive"] + ratings["defensive"]).abs().max() < 1e-9


def test_every_window_covers_three_seasons() -> None:
    ratings = pippen.rapm_ratings()
    spans = (ratings["window_end"] - ratings["window_start"]).unique()
    assert list(spans) == [2]


def test_the_shipped_windows_span_the_covered_seasons() -> None:
    ratings = pippen.rapm_ratings()
    assert ratings["window_start"].min() == pippen.FIRST_RAPM_SEASON
    assert ratings["window_end"].max() == pippen.LAST_RAPM_SEASON


def test_a_window_that_was_not_computed_says_which_exist() -> None:
    with pytest.raises(ValueError, match="available windows end in"):
        pippen.rapm_ratings(window_end=1999)


def test_the_possession_floor_only_removes_rows() -> None:
    everyone = pippen.rapm_ratings(window_end=2024)
    regulars = pippen.rapm_ratings(window_end=2024, min_possessions=5000)
    assert len(regulars) < len(everyone)
    assert regulars["possessions"].min() >= 5000


def test_players_are_named_so_the_table_is_readable_without_a_lookup() -> None:
    ratings = pippen.rapm_ratings(window_end=2024, min_possessions=5000)
    assert ratings["player"].notna().all()
    assert ratings["player"].str.len().min() > 2


# ------------------------------------------------------------------ reliability


def test_reliability_defaults_to_the_averaged_random_splits() -> None:
    # Odd-even is a single draw kept for comparison. Averaging the two rules
    # together would silently mix two estimators.
    assert set(pippen.metric_reliability()["rule"]) == {"random"}
    assert set(pippen.metric_reliability(rule="odd_even")["rule"]) == {"odd_even"}


def test_an_unknown_split_rule_lists_the_ones_that_exist() -> None:
    with pytest.raises(ValueError, match="available"):
        pippen.metric_reliability(rule="coin_flip")


def test_no_column_is_named_reliability_without_a_length() -> None:
    # The same measurement implies very different figures at one season and at
    # three, so a bare "reliability" column would invite the wrong one.
    columns = pippen.metric_reliability().columns
    assert "reliability" not in columns
    assert any("reliability_at" in name for name in columns)


def test_shooting_efficiency_is_the_least_reliable_thing_measured() -> None:
    # The project's headline reliability finding, pinned so a change to the
    # shipped table cannot pass unnoticed.
    pooled = (
        pippen.metric_reliability()
        .groupby("metric")["reliability_at_82_games"]
        .mean()
        .sort_values()
    )
    assert set(pooled.index[:2]) == {"effective_field_goal", "true_shooting"}
    assert pooled.index[-1] == "three_point_rate"


def test_a_season_with_no_measurement_says_what_is_covered() -> None:
    with pytest.raises(ValueError, match="available"):
        pippen.metric_reliability(season=1946)


# ------------------------------------------------------------------ coefficient


def test_the_measured_coefficient_differs_from_the_convention() -> None:
    # Every one of 25 measured seasons came out below 0.44, so a value equal to
    # it would mean the measurement was lost somewhere.
    assert pippen.possession_coefficient(2024) < 0.44


def test_an_unmeasured_season_falls_back_rather_than_failing() -> None:
    assert 0.3 < pippen.possession_coefficient(1985) < 0.5


def test_the_coefficient_is_a_plain_float() -> None:
    # A numpy scalar would satisfy most callers and then surprise one that
    # serialises it to JSON.
    value = pippen.possession_coefficient(2024)
    assert type(value) is float


def test_the_tenure_columns_sit_inside_their_window() -> None:
    """A player cannot have played a season the window does not contain."""
    ratings = pippen.rapm_ratings()
    assert (ratings["first_season"] >= ratings["window_start"]).all()
    assert (ratings["last_season"] <= ratings["window_end"]).all()
    assert (ratings["first_season"] <= ratings["last_season"]).all()
    assert set(ratings["seasons_played"].unique()) <= {1, 2, 3}


def test_most_rows_do_not_cover_the_whole_window() -> None:
    """The reason the tenure columns exist, pinned so it cannot be forgotten.

    Labelling a rating by its window implies three seasons of evidence. For
    more than half these rows that is an overstatement, which is why the
    dashboard and the API both lead with the seasons actually played.
    """
    ratings = pippen.rapm_ratings()
    partial = ratings["seasons_played"] < 3
    assert partial.sum() > len(ratings) / 2


def test_a_player_can_miss_a_season_in_the_middle_of_a_window() -> None:
    """seasons_played is not last minus first: 83 rows have a gap.

    Seth Curry played 2016-17 and 2018-19 and missed 2017-18 injured, so his
    2016-2018 window spans three seasons and rests on two.
    """
    ratings = pippen.rapm_ratings()
    span = ratings["last_season"] - ratings["first_season"] + 1
    assert (ratings["seasons_played"] <= span).all()
    assert (ratings["seasons_played"] < span).any(), "expected at least one gap season"


def test_austin_reaves_is_labelled_by_the_season_he_played() -> None:
    """The row that prompted the columns. He debuted in 2021-22."""
    reaves = pippen.rapm_ratings()
    reaves = reaves[reaves["player_id"] == 1630559].sort_values("window_end")
    earliest = reaves.iloc[0]
    assert earliest["window_start"] == 2019, "his earliest window opens in 2019-20"
    assert earliest["first_season"] == earliest["last_season"] == 2021
    assert earliest["seasons_played"] == 1
