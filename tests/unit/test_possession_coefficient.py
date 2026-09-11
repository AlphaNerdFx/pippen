"""Tests for the measured free throw possession coefficient.

Every test builds a small synthetic play-by-play sequence, using only the
columns `estimate_season_coefficient` documents as required
(`game_id`, `game_play_number`, `type_text`, `scoring_play`). No network, and
no dependence on the real hoopR file: the point of measuring per season is
that the logic has to be right on made-up data before it is trusted on
614,447 real rows.

Each test targets exactly one design decision from the module docstring, so a
failure points at which rule broke rather than requiring a re-derivation of
the whole coefficient from first principles.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from pippen.data.possession_coefficient import (
    CONVENTIONAL_COEFFICIENT,
    estimate_coefficients_by_season,
    estimate_season_coefficient,
)


def _game(events: list[tuple[str, bool]], game_id: int = 1, start: int = 1) -> pd.DataFrame:
    """Build a minimal, single-game play-by-play frame.

    Args:
        events: ``(type_text, scoring_play)`` pairs, already in the
            chronological order they happened in.
        game_id: Game identifier shared by every row.
        start: First ``game_play_number``; each later row increments by one,
            matching how hoopR numbers events within a game.

    Returns:
        A frame carrying exactly the four columns the module requires.
    """
    return pd.DataFrame(
        {
            "game_id": [game_id] * len(events),
            "game_play_number": range(start, start + len(events)),
            "type_text": [event[0] for event in events],
            "scoring_play": [event[1] for event in events],
            # Real hoopR data flags every shot attempt, free throws included,
            # and never flags a rebound. Derived here so a fixture reads as a
            # list of event names rather than a list of pairs of flags.
            "shooting_play": [_is_shot(event[0]) for event in events],
        }
    )


def _is_shot(type_text: str) -> bool:
    """Whether an event name denotes a shot attempt, matching hoopR's flag."""
    return type_text.startswith("Free Throw") or any(
        word in type_text for word in ("Shot", "Layup", "Dunk", "Jumper")
    )


# ------------------------------------------------------------ ordinary trips


def test_two_shot_trip_ending_on_a_make_counts_as_ending_a_possession() -> None:
    df = _game(
        [
            ("Shooting Foul", False),
            ("Free Throw - 1 of 2", False),
            ("Free Throw - 2 of 2", True),
            ("Jump Shot", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 2
    assert result.possession_ending_trips == 1
    assert result.excluded_unresolved == 0
    assert result.coefficient == pytest.approx(0.5)


def test_two_shot_trip_missing_last_with_defensive_rebound_ends_possession() -> None:
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Defensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 2
    assert result.possession_ending_trips == 1


def test_missed_final_free_throw_with_offensive_rebound_does_not_end_possession() -> None:
    """The explicit case named in the task.

    A missed last free throw that the shooting team rebounds itself keeps its
    own possession alive.
    """
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Offensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 2
    assert result.possession_ending_trips == 0
    assert result.coefficient == pytest.approx(0.0)


def test_three_shot_trip_uses_only_the_third_shot() -> None:
    df = _game(
        [
            ("Free Throw - 1 of 3", True),
            ("Free Throw - 2 of 3", True),
            ("Free Throw - 3 of 3", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 3
    assert result.possession_ending_trips == 1


def test_non_final_shots_never_contribute_to_the_numerator_on_their_own() -> None:
    # Every shot before the last is attempted with the trip guaranteed to
    # continue, make or miss, so a made "1 of 2" must not be read as an
    # ending event.
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Offensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.possession_ending_trips == 0


# ------------------------------------------------------------------ and-ones


def test_and_one_free_throw_does_not_end_a_possession() -> None:
    # The made field goal already ended the possession (already counted via
    # FGA elsewhere); the free throw must not add a second ending event.
    df = _game(
        [
            ("Jump Shot", True),
            ("Shooting Foul", False),
            ("Free Throw - 1 of 1", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 1
    assert result.possession_ending_trips == 0
    assert result.coefficient == pytest.approx(0.0)


def test_and_one_free_throw_missed_still_does_not_end_a_possession() -> None:
    # Whether the single free throw is made or missed is irrelevant: the
    # possession already ended (or, for a take foul, never will) before this
    # shot happens at all.
    df = _game(
        [
            ("Jump Shot", True),
            ("Shooting Foul", False),
            ("Free Throw - 1 of 1", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.possession_ending_trips == 0


# ----------------------------------------------------------------- technical


def test_technical_free_throw_does_not_end_a_possession() -> None:
    df = _game(
        [
            ("Technical Foul", False),
            ("Free Throw - Technical", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 1
    assert result.possession_ending_trips == 0


# -------------------------------------------------------- flagrant / clear path


def test_flagrant_trip_never_ends_a_possession_even_when_the_last_shot_is_made() -> None:
    # Flagrant fouls award free throws and let the fouled team keep the ball
    # afterwards (a throw-in). A made last shot elsewhere would end a
    # possession; here it must not.
    df = _game(
        [
            ("Flagrant Foul Type 1", False),
            ("Free Throw - Flagrant 1 of 2", True),
            ("Free Throw - Flagrant 2 of 2", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.free_throw_attempts == 2
    assert result.possession_ending_trips == 0


def test_clear_path_trip_never_ends_a_possession() -> None:
    df = _game(
        [
            ("Clear Path Foul", False),
            ("Free Throw - Clear Path 1 of 2", False),
            ("Free Throw - Clear Path 2 of 2", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.possession_ending_trips == 0


# ------------------------------------------------------------- substitutions


def test_a_substitution_between_the_miss_and_the_rebound_is_skipped() -> None:
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Substitution", False),
            ("Defensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.possession_ending_trips == 1
    assert result.excluded_unresolved == 0


def test_two_consecutive_substitutions_are_still_skipped() -> None:
    # _MAX_LOOKAHEAD is 3: two intervening substitutions plus the resolving
    # event on the third step should still resolve.
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Substitution", False),
            ("Substitution", False),
            ("Offensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.possession_ending_trips == 0
    assert result.excluded_unresolved == 0


# -------------------------------------------------------------- unresolved


def test_a_missed_last_free_throw_with_no_rebound_nearby_is_excluded_not_guessed() -> None:
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("End Period", False),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    # The ambiguous last shot is dropped from both the numerator and the
    # denominator; the unambiguous first shot of the same trip is not.
    assert result.total_free_throw_attempts == 2
    assert result.free_throw_attempts == 1
    assert result.excluded_unresolved == 1
    assert result.possession_ending_trips == 0


def test_unrecognised_free_throw_label_raises_rather_than_guessing() -> None:
    df = _game([("Free Throw - Mystery", False)])

    with pytest.raises(ValueError, match="does not know how to classify"):
        estimate_season_coefficient(df, season=2024)


# ------------------------------------------------------------------- input


def test_missing_required_column_raises_a_clear_error() -> None:
    df = _game([("Free Throw - 1 of 1", True)]).drop(columns=["scoring_play"])

    with pytest.raises(ValueError, match="scoring_play"):
        estimate_season_coefficient(df, season=2024)


def test_a_season_with_no_free_throws_has_a_nan_coefficient() -> None:
    df = _game([("Jump Shot", True), ("Defensive Rebound", False)])
    result = estimate_season_coefficient(df, season=2024)

    assert result.total_free_throw_attempts == 0
    assert math.isnan(result.coefficient)
    assert math.isnan(result.diff_from_conventional)


def test_row_order_does_not_matter_the_function_sorts_by_game_play_number() -> None:
    ordered = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
            ("Defensive Rebound", False),
        ]
    )
    shuffled = ordered.sample(frac=1, random_state=0).reset_index(drop=True)

    ordered_result = estimate_season_coefficient(ordered, season=2024)
    shuffled_result = estimate_season_coefficient(shuffled, season=2024)

    assert shuffled_result == ordered_result


def test_lookahead_does_not_cross_a_game_boundary() -> None:
    # Game 1 ends on an unresolved missed free throw (nothing follows it in
    # its own game). Game 2's very first event is a Defensive Rebound, which
    # must not be mistaken for game 1's rebound.
    game_one = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", False),
        ],
        game_id=1,
        start=1,
    )
    game_two = _game(
        [
            ("Defensive Rebound", False),
            ("Jump Shot", True),
        ],
        game_id=2,
        start=1,
    )
    combined = pd.concat([game_one, game_two], ignore_index=True)

    result = estimate_season_coefficient(combined, season=2024)

    assert result.excluded_unresolved == 1
    assert result.possession_ending_trips == 0


# --------------------------------------------------------------- diff & table


def test_diff_from_conventional_is_measured_minus_the_fixed_constant() -> None:
    # One trip, two attempts, the last one made: one possession-ending trip
    # over two attempts is a coefficient of 0.5.
    df = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", True),
        ]
    )
    result = estimate_season_coefficient(df, season=2024)

    assert result.coefficient == pytest.approx(0.5)
    assert result.diff_from_conventional == pytest.approx(0.5 - CONVENTIONAL_COEFFICIENT)


def test_multi_season_table_has_one_row_per_season_sorted_ascending() -> None:
    season_2023 = _game(
        [
            ("Free Throw - 1 of 2", False),
            ("Free Throw - 2 of 2", False),
            ("Defensive Rebound", False),
        ]
    )
    season_2024 = _game(
        [
            ("Free Throw - 1 of 2", True),
            ("Free Throw - 2 of 2", True),
        ]
    )

    table = estimate_coefficients_by_season({2024: season_2024, 2023: season_2023})

    assert list(table["season"]) == [2023, 2024]
    assert list(table.columns) == [
        "season",
        "coefficient",
        "diff_from_conventional",
        "possession_ending_trips",
        "free_throw_attempts",
        "total_free_throw_attempts",
        "excluded_unresolved",
    ]
    row_2023 = table.loc[table["season"] == 2023].iloc[0]
    row_2024 = table.loc[table["season"] == 2024].iloc[0]
    # Both seasons: one trip, two attempts, the last one ends the
    # possession (2023 via a defensive rebound, 2024 via a make) -> 0.5.
    assert row_2023["coefficient"] == pytest.approx(0.5)
    assert row_2024["coefficient"] == pytest.approx(0.5)
    assert row_2023["free_throw_attempts"] == 2
    assert row_2024["free_throw_attempts"] == 2


def test_empty_season_mapping_returns_an_empty_table_with_the_right_columns() -> None:
    table = estimate_coefficients_by_season({})

    assert table.empty
    assert list(table.columns) == [
        "season",
        "coefficient",
        "diff_from_conventional",
        "possession_ending_trips",
        "free_throw_attempts",
        "total_free_throw_attempts",
        "excluded_unresolved",
    ]


@pytest.mark.parametrize(
    "filler",
    [
        "Substitution",
        "Full Timeout",
        "Jumpball",
        "Coach's Challenge (replaycenter)",
        "Shooting Foul",
    ],
)
def test_a_non_shot_between_the_miss_and_the_rebound_is_stepped_over(filler: str) -> None:
    """Anything that is not a shot is skipped while looking for the rebound.

    An earlier version skipped substitutions only and latched shut on anything
    else, so a foul call or a replay review sitting one event before a clear
    rebound label made the trip unresolvable. That silently excluded 29
    attempts from the 2023-24 season, and they were not random: six were
    coach's challenges.
    """
    events = _game([("Free Throw - 2 of 2", False), (filler, False), ("Defensive Rebound", False)])
    result = estimate_season_coefficient(events, 2024)
    assert result.excluded_unresolved == 0
    assert result.possession_ending_trips == 1


def test_a_shot_between_the_miss_and_the_rebound_stops_the_search() -> None:
    """A rebound after a new shot belongs to that shot, not to this free throw.

    This is the one thing the lookahead must not step over. Without it the
    search would attribute a later shot's rebound to this trip and count a
    possession that did not end here.
    """
    events = _game(
        [
            ("Free Throw - 2 of 2", False),
            ("Tip Shot", False),
            ("Defensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(events, 2024)
    assert result.excluded_unresolved == 1
    assert result.free_throw_attempts == 0


def test_three_consecutive_substitutions_are_still_stepped_over() -> None:
    """Runs of three substitutions are routine late in a game."""
    events = _game(
        [
            ("Free Throw - 2 of 2", False),
            ("Substitution", False),
            ("Substitution", False),
            ("Substitution", False),
            ("Defensive Rebound", False),
        ]
    )
    result = estimate_season_coefficient(events, 2024)
    assert result.excluded_unresolved == 0
    assert result.possession_ending_trips == 1
