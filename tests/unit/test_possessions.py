"""Tests for stint extraction from parsed possessions.

`pbpstats` is not exercised here. Its possession objects are replaced with
fakes carrying the two statistics this project actually reads, so the
aggregation, the filtering and the event-order shim can be tested without a
downloaded game. The shim in particular needs a fake: reproducing it against
real data would mean keeping a 2016 play-by-play file in the repository, and
data never enters git.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from pippen import paths
from pippen.rapm import possessions as mod
from pippen.rapm.possessions import (
    MissingPlayByPlayError,
    PointsReconciliation,
    _assign_event_order,
    _possession_row,
    game_stints,
    has_valid_lineups,
    season_stints,
)

# ------------------------------------------------------------------ fakes


class _FakeEvent:
    """An event with the linked-list structure `pbpstats` builds."""

    def __init__(self, period: int, event_num: int, order: int | None = None) -> None:
        self.period = period
        self.event_num = event_num
        self.previous_event: _FakeEvent | None = None
        self.next_event: _FakeEvent | None = None
        if order is not None:
            self.order = order


def _chain(period: int, count: int, with_order: bool = False) -> list[_FakeEvent]:
    """Build one period's doubly linked event chain."""
    events = [
        _FakeEvent(period, index, order=index if with_order else None) for index in range(count)
    ]
    for earlier, later in pairwise(events):
        earlier.next_event = later
        later.previous_event = earlier
    return events


class _FakePossession:
    def __init__(self, stats: list[dict[str, Any]], events: list[_FakeEvent]) -> None:
        self.possession_stats = stats
        self.events = events


def _stat(key: str, value: int, offense: int = 1, defense: int = 2) -> dict[str, Any]:
    return {
        "stat_key": key,
        "stat_value": value,
        "team_id": offense,
        "opponent_team_id": defense,
        "lineup_id": "1-2-3-4-5",
        "opponent_lineup_id": "6-7-8-9-10",
    }


def _scoring_possession(points: int, offense: int = 1, defense: int = 2) -> _FakePossession:
    stats = [_stat("OffPoss", 1, offense, defense)]
    if points:
        stats.append(_stat("OpponentPoints", points, offense, defense))
    return _FakePossession(stats, _chain(1, 3))


# ------------------------------------------------------------------ one possession


def test_a_possession_without_offposs_does_not_count() -> None:
    # pbpstats omits OffPoss on period-boundary artefacts. Counting them would
    # inflate the denominator of every rating.
    assert _possession_row(_FakePossession([_stat("SecondsPlayedOff", 12)], [])) is None


def test_a_possession_with_no_points_still_counts() -> None:
    row = _possession_row(_FakePossession([_stat("OffPoss", 1)], []))
    assert row is not None
    assert row["points"] == 0


def test_points_come_from_the_defenders_opponent_points() -> None:
    row = _possession_row(_scoring_possession(3))
    assert row is not None
    assert row["points"] == 3
    assert row["offense_lineup"] == "1-2-3-4-5"
    assert row["defense_lineup"] == "6-7-8-9-10"


# ------------------------------------------------------------------ aggregation


def test_repeated_matchups_collapse_into_one_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "load_possessions",
        lambda game_id: [_scoring_possession(2), _scoring_possession(0), _scoring_possession(3)],
    )
    frame = game_stints("0022300001")
    assert len(frame) == 1
    assert frame.iloc[0]["possessions"] == 3
    assert frame.iloc[0]["points"] == 5
    assert frame.iloc[0]["game_id"] == "0022300001"


def test_different_matchups_stay_separate(monkeypatch: pytest.MonkeyPatch) -> None:
    other = _FakePossession(
        [
            {
                "stat_key": "OffPoss",
                "stat_value": 1,
                "team_id": 2,
                "opponent_team_id": 1,
                "lineup_id": "6-7-8-9-10",
                "opponent_lineup_id": "1-2-3-4-5",
            }
        ],
        [],
    )
    monkeypatch.setattr(mod, "load_possessions", lambda game_id: [_scoring_possession(2), other])
    frame = game_stints("0022300001")
    assert len(frame) == 2


def test_a_game_with_no_counted_possessions_returns_the_right_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod, "load_possessions", lambda game_id: [])
    frame = game_stints("0022300001")
    assert frame.empty
    assert list(frame.columns) == list(mod.STINT_COLUMNS)


# ------------------------------------------------------------------ lineup validity


def test_only_five_a_side_rows_are_marked_valid() -> None:
    frame = pd.DataFrame(
        {
            "offense_lineup": ["1-2-3-4-5", "1-2-3-4", "1-2-3-4-5"],
            "defense_lineup": ["6-7-8-9-10", "6-7-8-9-10", "6-7-8-9-10-11"],
        }
    )
    assert has_valid_lineups(frame).tolist() == [True, False, False]


# ------------------------------------------------------------------ the order shim


def test_order_is_assigned_across_every_period_not_just_the_first() -> None:
    # The chains link only within a period, so following one from the first
    # possession reaches period 1 and stops. This is the bug that made every
    # pre-2023 game fail.
    first, second, third = _chain(1, 4), _chain(2, 3), _chain(3, 2)
    possessions = [
        _FakePossession([], [first[0]]),
        _FakePossession([], [second[1]]),
        _FakePossession([], [third[0]]),
    ]
    assigned = _assign_event_order(possessions)
    assert assigned == 9
    assert [event.order for event in first] == [0, 1, 2, 3]
    assert [event.order for event in second] == [4, 5, 6]
    assert [event.order for event in third] == [7, 8]


def test_order_is_left_alone_when_the_feed_supplied_it() -> None:
    # From 2023-24 the raw feed carries `ord`, and overwriting it would discard
    # the upstream ordering in favour of a reconstruction.
    events = _chain(1, 4, with_order=True)
    possessions = [_FakePossession([], [events[0]])]
    assert _assign_event_order(possessions) == 0
    assert [event.order for event in events] == [0, 1, 2, 3]


def test_ordering_follows_period_then_event_number() -> None:
    later_period = _chain(2, 2)
    earlier_period = _chain(1, 2)
    possessions = [_FakePossession([], [later_period[0]]), _FakePossession([], [earlier_period[0]])]
    _assign_event_order(possessions)
    assert earlier_period[0].order < later_period[0].order


def test_no_possessions_is_not_an_error() -> None:
    assert _assign_event_order([]) == 0


# ------------------------------------------------------------------ reconciliation


def test_reconciliation_reports_agreement_and_disagreement() -> None:
    agree = PointsReconciliation("G", {1: 110, 2: 108}, {1: 110, 2: 108})
    assert agree.agrees
    assert "reconcile" in agree.describe()

    differ = PointsReconciliation("G", {1: 110, 2: 108}, {1: 111, 2: 108})
    assert not differ.agrees
    assert "!=" in differ.describe()


# ------------------------------------------------------------------ season level


def test_a_missing_download_names_the_file_it_wanted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    with pytest.raises(MissingPlayByPlayError, match="0022300001"):
        mod.load_possessions("0022300001")


def test_one_bad_game_does_not_stop_the_season(monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(game_id: str) -> pd.DataFrame:
        if game_id == "B":
            raise ValueError("malformed")
        row = _possession_row(_scoring_possession(2))
        assert row is not None
        return pd.DataFrame([{**row, "game_id": game_id, "possessions": 1}])

    monkeypatch.setattr(mod, "game_stints", flaky)
    result = season_stints(2016, game_ids=["A", "B", "C"])
    assert result.games_parsed == 2
    assert [game for game, _ in result.failures] == ["B"]
    assert "1 games failed to parse" in result.summary()


def test_progress_is_reported_for_every_game(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "game_stints", lambda game_id: pd.DataFrame())
    seen: list[tuple[str, str | None]] = []
    season_stints(2016, game_ids=["A", "B"], on_progress=lambda g, e: seen.append((g, e)))
    assert seen == [("A", None), ("B", None)]
