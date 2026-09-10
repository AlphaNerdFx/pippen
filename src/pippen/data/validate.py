"""Dataset-level validation, run after ingest and before anything computes.

``schemas.py`` validates one table at a time: its columns, its dtypes, its
per-row constraints. That catches a malformed file. It cannot catch a
well-formed file that disagrees with the file next to it.

The checks here look across tables and across a season. A play-by-play file
missing forty games is perfectly valid on its own terms. Every column is
present, every dtype is right, every row passes. The only thing wrong with it
is that the schedule says there should be more games, and nothing except a
cross-table check will ever notice.

Failure, skip and pass are three different outcomes
    A check that could not run because an input was absent reports ``skipped``,
    never ``passed``. Reporting a check that never ran as a pass is the worst
    outcome available here, because it produces a green validation report for
    data nobody checked.

Season boundaries
    A season labelled by its end year runs from roughly October of the previous
    calendar year to June of the labelled year. The window used below is
    deliberately wider than that, from 1 August of the previous year to 30
    September of the labelled year. It exists to catch a year and season
    mix-up or an off-by-one in a filename, not to police the exact first and
    last day of a schedule that varies with lockouts, pandemics and
    tournaments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Mapping

CheckStatus = Literal["passed", "failed", "skipped"]

# Enough identifiers to start debugging, few enough to read. A report that
# dumps four thousand game identifiers is a report nobody opens.
_MAX_REPORTED: Final = 10

_SEASON_WINDOW_START_MONTH: Final = 8
_SEASON_WINDOW_END_MONTH: Final = 9


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one validation check.

    Attributes:
        check: Short stable name for the check, suitable for a report row.
        status: ``passed``, ``failed``, or ``skipped`` when a required input
            was absent.
        detail: One human-readable sentence. For a failure it says what is
            wrong and, where useful, which identifiers to look at. For a skip
            it says which input was missing.
    """

    check: str
    status: CheckStatus
    detail: str

    @property
    def ok(self) -> bool:
        """Whether this check found nothing wrong.

        A skip counts as not ok. It did not find a problem, but it also did not
        look, and treating those the same is how unchecked data reaches a
        calculation.
        """
        return self.status == "passed"


def _sample(identifiers: object) -> str:
    """Render a collection of identifiers as a short, readable list.

    Args:
        identifiers: Any iterable of identifiers.

    Returns:
        Up to :data:`_MAX_REPORTED` identifiers, comma separated, with a count
        of how many more were omitted.
    """
    values = sorted(identifiers)  # type: ignore[call-overload]
    shown = ", ".join(str(value) for value in values[:_MAX_REPORTED])
    remaining = len(values) - _MAX_REPORTED
    return f"{shown} and {remaining} more" if remaining > 0 else shown


def _skip(check: str, missing: str) -> CheckResult:
    """Build a skip result naming the input that was absent."""
    return CheckResult(check, "skipped", f"{missing} was not provided, so this check did not run")


# ------------------------------------------------------------------ completeness


def check_schedule_and_play_by_play_agree(
    schedule: pd.DataFrame | None, play_by_play: pd.DataFrame | None
) -> CheckResult:
    """Check that the schedule and the play-by-play cover the same games.

    A gap in either direction matters. Games in the schedule with no
    play-by-play are missing possessions, which biases anything computed from
    them. Games in the play-by-play with no schedule entry mean the two files
    came from different seasons or different sources.

    Args:
        schedule: The season's schedule table, or None if it was not ingested.
        play_by_play: The season's play-by-play table, or None.

    Returns:
        The check outcome.
    """
    check = "schedule_and_play_by_play_agree"
    if schedule is None:
        return _skip(check, "schedules")
    if play_by_play is None:
        return _skip(check, "play_by_play")

    scheduled = set(schedule["game_id"].dropna().unique())
    played = set(play_by_play["game_id"].dropna().unique())

    missing_pbp = scheduled - played
    unscheduled = played - scheduled
    if not missing_pbp and not unscheduled:
        return CheckResult(check, "passed", f"all {len(scheduled)} scheduled games have events")

    problems = []
    if missing_pbp:
        problems.append(
            f"{len(missing_pbp)} scheduled games have no events ({_sample(missing_pbp)})"
        )
    if unscheduled:
        problems.append(
            f"{len(unscheduled)} games have events but are not scheduled ({_sample(unscheduled)})"
        )
    return CheckResult(check, "failed", "; ".join(problems))


# ------------------------------------------------------------------- consistency


def check_no_duplicate_rows(frame: pd.DataFrame | None, dataset: str) -> CheckResult:
    """Check a table has no repeated rows on its natural key.

    This is what a re-download concatenated on top of itself looks like, and it
    inflates every per-player total downstream without changing the shape of
    the table.

    Args:
        frame: The table to check, or None if it was not ingested.
        dataset: Dataset name, used to pick the natural key and to name the
            check.

    Returns:
        The check outcome. A dataset with no defined natural key is skipped
        rather than passed.
    """
    check = f"no_duplicate_rows_{dataset}"
    if frame is None:
        return _skip(check, dataset)

    keys: Mapping[str, list[str]] = {
        "player_box": ["game_id", "athlete_id"],
        "team_box": ["game_id", "team_id"],
        "schedules": ["game_id"],
    }
    key = keys.get(dataset)
    if key is None:
        return CheckResult(check, "skipped", f"{dataset!r} has no defined natural key to check")
    if any(column not in frame.columns for column in key):
        return _skip(check, f"one of {key} in {dataset}")

    duplicated = frame[frame.duplicated(subset=key, keep=False)]
    if duplicated.empty:
        return CheckResult(check, "passed", f"{len(frame)} rows, all unique on {key}")

    offenders = duplicated[key[0]].unique()
    return CheckResult(
        check,
        "failed",
        f"{len(duplicated)} rows repeat on {key} (games: {_sample(offenders)})",
    )


# ---------------------------------------------------------------------- accuracy


def check_teams_match_the_schedule(
    schedule: pd.DataFrame | None, play_by_play: pd.DataFrame | None
) -> CheckResult:
    """Check each game's teams agree between the schedule and the play-by-play.

    Both tables independently record which two teams played. When they
    disagree, one of them is wrong about the fixture, and every possession
    attributed from the play-by-play is attributed to the wrong side.

    Args:
        schedule: The season's schedule table, or None.
        play_by_play: The season's play-by-play table, or None.

    Returns:
        The check outcome.
    """
    check = "teams_match_the_schedule"
    if schedule is None:
        return _skip(check, "schedules")
    if play_by_play is None:
        return _skip(check, "play_by_play")

    from_schedule = schedule.set_index("game_id")[["home_team_id", "away_team_id"]]
    from_events = (
        play_by_play.groupby("game_id")[["home_team_id", "away_team_id"]].first().astype("Int64")
    )
    shared = from_schedule.index.intersection(from_events.index)
    if len(shared) == 0:
        return CheckResult(check, "skipped", "the two tables share no game identifiers")

    left = from_schedule.loc[shared].astype("Int64")
    right = from_events.loc[shared]
    disagreeing = shared[(left != right).any(axis=1)]

    if len(disagreeing) == 0:
        return CheckResult(check, "passed", f"teams agree across {len(shared)} games")
    return CheckResult(
        check,
        "failed",
        f"{len(disagreeing)} games disagree on which teams played ({_sample(disagreeing)})",
    )


# ------------------------------------------------------------- temporal integrity


def check_events_run_in_order(play_by_play: pd.DataFrame | None) -> CheckResult:
    """Check each game's periods do not run backwards.

    Rows arrive in event order. A period that decreases partway through a game
    means two games were concatenated under one identifier, or the file was
    sorted by something other than time and the ordering was then trusted.

    Clock values are deliberately not checked. hoopR's exact encoding of
    ``clock_minutes`` and ``clock_seconds`` has not been verified, and a wrong
    assumption about it would fail valid rows rather than catch corrupt ones.

    Args:
        play_by_play: The season's play-by-play table, or None.

    Returns:
        The check outcome.
    """
    check = "events_run_in_order"
    if play_by_play is None:
        return _skip(check, "play_by_play")
    if "period" not in play_by_play.columns:
        return _skip(check, "the period column")

    period = pd.to_numeric(play_by_play["period"], errors="coerce")
    went_backwards = period.groupby(play_by_play["game_id"]).diff() < 0
    offenders = play_by_play.loc[went_backwards, "game_id"].unique()

    if len(offenders) == 0:
        return CheckResult(check, "passed", "periods are non-decreasing within every game")
    return CheckResult(
        check,
        "failed",
        f"{len(offenders)} games have a period that runs backwards ({_sample(offenders)})",
    )


def check_dates_fall_inside_the_season(schedule: pd.DataFrame | None, season: int) -> CheckResult:
    """Check every scheduled date falls inside the season it is labelled with.

    Catches a year and season mix-up, or a filename off by one, both of which
    produce a table that is internally consistent and attached to the wrong
    year. See the module docstring for why the window is wider than a real
    schedule.

    Args:
        schedule: The season's schedule table, or None.
        season: Season end year, so 2024 means the 2023-24 season.

    Returns:
        The check outcome.
    """
    check = "dates_fall_inside_the_season"
    if schedule is None:
        return _skip(check, "schedules")
    if "game_date" not in schedule.columns:
        return _skip(check, "the game_date column")

    # ISO 8601 explicitly rather than letting pandas guess. Guessing is slower,
    # warns, and can silently read the same column two different ways across
    # two seasons. A date that is not ISO is worth surfacing here rather than
    # quietly reinterpreting.
    dates = pd.to_datetime(schedule["game_date"], errors="coerce", format="ISO8601")
    if dates.notna().sum() == 0:
        return CheckResult(
            check,
            "skipped",
            "no game_date parsed as ISO 8601, so the dates could not be checked",
        )

    start = pd.Timestamp(year=season - 1, month=_SEASON_WINDOW_START_MONTH, day=1)
    end = pd.Timestamp(year=season, month=_SEASON_WINDOW_END_MONTH, day=30)
    outside = schedule.loc[dates.notna() & ((dates < start) | (dates > end)), "game_id"]

    if outside.empty:
        window = f"{start.date()} to {end.date()}"
        return CheckResult(check, "passed", f"all dates fall within {window}")
    return CheckResult(
        check,
        "failed",
        f"{len(outside)} games fall outside the {season} season window ({_sample(outside.unique())})",
    )


# ------------------------------------------------------------------- the runner


def validate_season(season: int, tables: Mapping[str, pd.DataFrame | None]) -> list[CheckResult]:
    """Run every applicable check for one season and return all results.

    Every check runs, including after one fails. A person should be able to fix
    a season's files once rather than re-running validation after each
    individual fix.

    Args:
        season: Season end year, so 2024 means the 2023-24 season.
        tables: Ingested tables by dataset name. A dataset that is absent, or
            present with the value None, causes the checks that need it to
            report ``skipped`` rather than ``passed``.

    Returns:
        One result per check, in a stable order.
    """
    schedule = tables.get("schedules")
    play_by_play = tables.get("play_by_play")

    results = [
        check_schedule_and_play_by_play_agree(schedule, play_by_play),
        check_teams_match_the_schedule(schedule, play_by_play),
        check_events_run_in_order(play_by_play),
        check_dates_fall_inside_the_season(schedule, season),
    ]
    results.extend(
        check_no_duplicate_rows(tables.get(dataset), dataset)
        for dataset in ("schedules", "player_box", "team_box")
    )
    return results


def summarise(results: list[CheckResult]) -> str:
    """Render a list of check results as a short report.

    Args:
        results: The results to render.

    Returns:
        A multi-line report: one counts line, then one line per check.
    """
    counts = {
        status: sum(1 for r in results if r.status == status)
        for status in ("passed", "failed", "skipped")
    }
    header = ", ".join(f"{count} {status}" for status, count in counts.items() if count)
    lines = [f"{len(results)} checks: {header}"]
    lines.extend(f"  [{r.status:7s}] {r.check}: {r.detail}" for r in results)
    return "\n".join(lines)
