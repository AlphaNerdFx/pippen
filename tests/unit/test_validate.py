"""Tests for dataset-level validation.

Each check exists to catch one specific corruption, so each check is tested by
producing that corruption and confirming it is caught. Tests that only feed
clean data would prove the checks run, not that they work.

The skip behaviour gets its own tests. A check reported as passed when it never
ran produces a green report for data nobody looked at, which is worse than no
report.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pippen.data import validate


def _schedule(game_ids: list[int] | None = None) -> pd.DataFrame:
    ids = game_ids if game_ids is not None else [401_585_001, 401_585_002]
    return pd.DataFrame(
        {
            "game_id": ids,
            "season": [2024] * len(ids),
            "game_date": ["2024-01-15"] * len(ids),
            "home_team_id": [1_610_612_743] * len(ids),
            "away_team_id": [1_610_612_747] * len(ids),
        }
    )


def _play_by_play(game_ids: list[int] | None = None, periods_per_game: int = 2) -> pd.DataFrame:
    ids = game_ids if game_ids is not None else [401_585_001, 401_585_002]
    rows = []
    for game_id in ids:
        for period in range(1, periods_per_game + 1):
            rows.append(
                {
                    "game_id": game_id,
                    "period": period,
                    "home_team_id": 1_610_612_743,
                    "away_team_id": 1_610_612_747,
                }
            )
    return pd.DataFrame(rows)


def _player_box(rows: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [401_585_001] * rows,
            "athlete_id": [203_999 + i for i in range(rows)],
            "team_id": [1_610_612_743] * rows,
        }
    )


def _team_box() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [401_585_001, 401_585_001],
            "team_id": [1_610_612_743, 1_610_612_747],
        }
    )


# ------------------------------------------------------------------ the result


def test_a_passed_check_is_ok() -> None:
    assert validate.CheckResult("x", "passed", "").ok


@pytest.mark.parametrize("status", ["failed", "skipped"])
def test_a_failed_or_skipped_check_is_not_ok(status: validate.CheckStatus) -> None:
    # A skip did not find a problem, but it also did not look. Treating those
    # the same is how unchecked data reaches a calculation.
    assert not validate.CheckResult("x", status, "").ok


# ------------------------------------------------------------------ completeness


def test_matching_schedule_and_events_pass() -> None:
    result = validate.check_schedule_and_play_by_play_agree(_schedule(), _play_by_play())
    assert result.status == "passed"


def test_a_scheduled_game_with_no_events_fails_and_is_named() -> None:
    result = validate.check_schedule_and_play_by_play_agree(
        _schedule([401_585_001, 401_585_002, 401_585_003]), _play_by_play([401_585_001])
    )
    assert result.status == "failed"
    assert "401585003" in result.detail


def test_events_for_an_unscheduled_game_fail() -> None:
    # Two files from different seasons, or from different sources.
    result = validate.check_schedule_and_play_by_play_agree(
        _schedule([401_585_001]), _play_by_play([401_585_001, 401_585_999])
    )
    assert result.status == "failed"
    assert "401585999" in result.detail


def test_gaps_in_both_directions_are_both_reported() -> None:
    result = validate.check_schedule_and_play_by_play_agree(
        _schedule([1, 2]), _play_by_play([2, 3])
    )
    assert result.status == "failed"
    assert "no events" in result.detail
    assert "not scheduled" in result.detail


@pytest.mark.parametrize(
    ("schedule", "events"),
    [(None, _play_by_play()), (_schedule(), None), (None, None)],
)
def test_a_missing_table_skips_rather_than_passes(
    schedule: pd.DataFrame | None, events: pd.DataFrame | None
) -> None:
    result = validate.check_schedule_and_play_by_play_agree(schedule, events)
    assert result.status == "skipped"
    assert not result.ok


def test_a_long_list_of_missing_games_is_truncated() -> None:
    # A report that dumps four thousand identifiers is a report nobody opens.
    result = validate.check_schedule_and_play_by_play_agree(
        _schedule(list(range(100))), _play_by_play([0])
    )
    assert result.status == "failed"
    assert "more" in result.detail
    assert len(result.detail) < 500


# ------------------------------------------------------------------- duplicates


def test_unique_rows_pass() -> None:
    assert validate.check_no_duplicate_rows(_player_box(), "player_box").status == "passed"


def test_a_table_concatenated_onto_itself_fails() -> None:
    doubled = pd.concat([_player_box(), _player_box()], ignore_index=True)
    result = validate.check_no_duplicate_rows(doubled, "player_box")
    assert result.status == "failed"
    assert "4 rows" in result.detail


def test_the_same_team_twice_in_one_game_fails() -> None:
    frame = _team_box()
    frame.loc[1, "team_id"] = frame.loc[0, "team_id"]
    assert validate.check_no_duplicate_rows(frame, "team_box").status == "failed"


def test_a_dataset_with_no_natural_key_is_skipped() -> None:
    result = validate.check_no_duplicate_rows(_player_box(), "play_by_play")
    assert result.status == "skipped"
    assert "natural key" in result.detail


def test_a_table_missing_its_key_column_is_skipped() -> None:
    result = validate.check_no_duplicate_rows(
        _player_box().drop(columns=["athlete_id"]), "player_box"
    )
    assert result.status == "skipped"


# --------------------------------------------------------------------- accuracy


def test_teams_agreeing_across_tables_pass() -> None:
    assert validate.check_teams_match_the_schedule(_schedule(), _play_by_play()).status == "passed"


def test_a_game_whose_teams_disagree_fails() -> None:
    # One table is wrong about the fixture, so every possession from the
    # play-by-play would be attributed to the wrong side.
    events = _play_by_play()
    events.loc[events["game_id"] == 401_585_002, "away_team_id"] = 1_610_612_738
    result = validate.check_teams_match_the_schedule(_schedule(), events)
    assert result.status == "failed"
    assert "401585002" in result.detail


def test_tables_sharing_no_games_are_skipped_not_passed() -> None:
    result = validate.check_teams_match_the_schedule(_schedule([1]), _play_by_play([999]))
    assert result.status == "skipped"


# ------------------------------------------------------------ temporal integrity


def test_periods_running_forwards_pass() -> None:
    assert validate.check_events_run_in_order(_play_by_play()).status == "passed"


def test_a_period_running_backwards_fails() -> None:
    # Two games concatenated under one identifier, or a file sorted by
    # something other than time and then trusted.
    events = _play_by_play([401_585_001], periods_per_game=4)
    events.loc[3, "period"] = 1
    result = validate.check_events_run_in_order(events)
    assert result.status == "failed"
    assert "401585001" in result.detail


def test_a_period_reset_between_games_is_not_a_failure() -> None:
    # Period 4 of one game followed by period 1 of the next is normal, and a
    # check that grouped incorrectly would flag every season.
    assert validate.check_events_run_in_order(_play_by_play(periods_per_game=4)).status == "passed"


def test_missing_period_column_skips() -> None:
    assert (
        validate.check_events_run_in_order(_play_by_play().drop(columns=["period"])).status
        == "skipped"
    )


def test_dates_inside_the_season_pass() -> None:
    assert validate.check_dates_fall_inside_the_season(_schedule(), 2024).status == "passed"


@pytest.mark.parametrize("bad_date", ["2022-01-15", "2025-12-01"])
def test_a_date_outside_the_season_fails(bad_date: str) -> None:
    frame = _schedule()
    frame.loc[0, "game_date"] = bad_date
    result = validate.check_dates_fall_inside_the_season(frame, 2024)
    assert result.status == "failed"
    assert "401585001" in result.detail


def test_an_october_date_belongs_to_the_following_season() -> None:
    # The 2023-24 season starts in October 2023 and is labelled 2024.
    frame = _schedule()
    frame["game_date"] = "2023-10-24"
    assert validate.check_dates_fall_inside_the_season(frame, 2024).status == "passed"


def test_unparseable_dates_skip_rather_than_fail() -> None:
    frame = _schedule()
    frame["game_date"] = "not a date"
    assert validate.check_dates_fall_inside_the_season(frame, 2024).status == "skipped"


# ------------------------------------------------------------------- the runner


def test_a_clean_season_passes_every_check() -> None:
    results = validate.validate_season(
        2024,
        {
            "schedules": _schedule(),
            "play_by_play": _play_by_play(),
            "player_box": _player_box(),
            "team_box": _team_box(),
        },
    )
    assert all(r.ok for r in results), validate.summarise(results)


def test_every_check_runs_even_after_one_fails() -> None:
    # A person should fix a season's files once, not re-run after each fix.
    results = validate.validate_season(
        2024,
        {
            "schedules": _schedule([1, 2]),
            "play_by_play": _play_by_play([3, 4]),
            "player_box": _player_box(),
            "team_box": _team_box(),
        },
    )
    assert len(results) == 7
    assert any(r.status == "failed" for r in results)


def test_an_empty_season_skips_everything_and_passes_nothing() -> None:
    results = validate.validate_season(2024, {})
    assert all(r.status == "skipped" for r in results)
    assert not any(r.ok for r in results)


def test_check_names_are_unique() -> None:
    # Names key the report rows, so a collision would hide one result.
    results = validate.validate_season(2024, {})
    names = [r.check for r in results]
    assert len(names) == len(set(names))


def test_the_summary_counts_and_lists_every_check() -> None:
    results = validate.validate_season(2024, {})
    report = validate.summarise(results)
    assert "7 checks" in report
    assert "skipped" in report
    for result in results:
        assert result.check in report
