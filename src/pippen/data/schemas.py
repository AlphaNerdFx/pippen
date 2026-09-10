"""pandera schemas for every table this project ingests.

A downstream regression cannot tell a malformed download from a bad season. If
a column silently changes dtype between two seasons' Parquet files, or a
required identifier goes missing for a handful of rows, the RAPM solver or the
reliability measurement will still run and will still print an answer. The
answer will be wrong and nothing will say so. These schemas exist to fail
loudly at the point of ingest, before a bad file reaches any calculation.

Known limitation, load-bearing for the rest of the pipeline
    The ``play_by_play`` table validated here is ESPN-sourced, via hoopR. It
    records event participants only (``athlete_id_1``/``2``/``3``) and carries
    no on-court lineup column. RAPM needs the full five-man lineup for both
    teams on every possession, so it cannot be computed from this table, no
    matter how clean a copy of it passes validation. That requires
    ``pbpstats`` running against NBA API data instead. This module checks the
    shape of the data; it makes no claim about what can be computed from it.

Schema source and confidence
    ``play_by_play`` was built from a real hoopR Parquet file's schema, read
    directly. Its column set is ground truth. ``player_box``, ``team_box`` and
    ``schedules`` have not been checked against a real file yet: each defines
    a small core of columns the author is confident must exist, based on
    documented hoopR/SportsDataverse conventions, and is marked provisional in
    the comments above it. Expand those three once a real sample has been
    ingested and read.

Strictness
    Every schema below sets ``strict=False``. hoopR adds columns to its
    published tables over time, and a hard failure the day the publisher adds
    one would break every scheduled refresh for a reason that has nothing to
    do with data quality. ``strict=False`` lets unrecognised columns pass
    through untouched rather than raising or silently dropping them. Dropping
    (``strict="filter"``) was considered and rejected: a discarded column
    leaves no trace, and a future stage that starts to depend on it would fail
    somewhere downstream instead of here.

Coercion
    Every schema also sets ``coerce=True``. One season's file read as
    ``int32`` and another's as ``int64`` for the same column is a real,
    observed source of silent divergence: a join or a concatenation between
    the two can produce upcasting, duplication, or a dtype-driven mismatch
    that never raises. Coercing every declared column to its schema dtype
    means every season leaves validation in the same dtype, or validation
    fails and says which column would not coerce.
"""

from __future__ import annotations

from typing import Any, Final

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

# NBA founding season through a round number comfortably past any season this
# project will see. Not a precise bound, just wide enough to still catch real
# corruption: a season of 0, a four-digit typo, or a year/season mix-up.
_MIN_SEASON: Final = 1946
_MAX_SEASON: Final = 2100

# ---------------------------------------------------------------- play_by_play
# Verified column set (see module docstring). Every one of these 30 columns is
# required to exist; nullability below reflects which of them are plausibly
# absent on a per-event basis rather than per-file, based on what each column
# means, not on measurement, since no sample has been checked row by row.
#
# `clock_minutes` and `clock_seconds` intentionally carry no range check.
# hoopR/ESPN's exact encoding (seconds-of-the-current-minute vs. some other
# split) has not been verified, and a wrong guess at a bound would fail valid
# rows instead of catching corrupt ones. `period` and `period_number` are
# both checked as >= 1 rather than checked against each other, for the same
# reason: their exact relationship has not been confirmed.
#
# No row-uniqueness constraint is declared. The verified column list has no
# event or sequence identifier, so there is no honest key to enforce one on.
PLAY_BY_PLAY_SCHEMA: Final[DataFrameSchema] = DataFrameSchema(
    columns={
        "game_id": Column("Int64", nullable=False, coerce=True),
        "period": Column("Int64", nullable=False, coerce=True, checks=Check.ge(1)),
        "period_number": Column("Int64", nullable=False, coerce=True, checks=Check.ge(1)),
        "period_display_value": Column("string", nullable=True, coerce=True),
        "clock_display_value": Column("string", nullable=True, coerce=True),
        "clock_minutes": Column("Int64", nullable=True, coerce=True),
        "clock_seconds": Column("Int64", nullable=True, coerce=True),
        "wallclock": Column("string", nullable=True, coerce=True),
        "type_id": Column("Int64", nullable=False, coerce=True),
        # Nullable: not every event (e.g. a period marker) is attributable to
        # one team or one player. Team names/abbreviations are per-game and
        # constant, so those stay required.
        "team_id": Column("Int64", nullable=True, coerce=True),
        "athlete_id_1": Column("Int64", nullable=True, coerce=True),
        "athlete_id_2": Column("Int64", nullable=True, coerce=True),
        "athlete_id_3": Column("Int64", nullable=True, coerce=True),
        "athlete_name_1": Column("string", nullable=True, coerce=True),
        "athlete_name_2": Column("string", nullable=True, coerce=True),
        "athlete_name_3": Column("string", nullable=True, coerce=True),
        "coordinate_x": Column("Float64", nullable=True, coerce=True),
        "coordinate_y": Column("Float64", nullable=True, coerce=True),
        "coordinate_x_raw": Column("Float64", nullable=True, coerce=True),
        "coordinate_y_raw": Column("Float64", nullable=True, coerce=True),
        "home_team_id": Column("Int64", nullable=False, coerce=True),
        "home_team_name": Column("string", nullable=False, coerce=True),
        "home_team_mascot": Column("string", nullable=True, coerce=True),
        "home_team_abbrev": Column("string", nullable=False, coerce=True),
        "home_team_name_alt": Column("string", nullable=True, coerce=True),
        "away_team_id": Column("Int64", nullable=False, coerce=True),
        "away_team_name": Column("string", nullable=False, coerce=True),
        "away_team_mascot": Column("string", nullable=True, coerce=True),
        "away_team_abbrev": Column("string", nullable=False, coerce=True),
        "away_team_name_alt": Column("string", nullable=True, coerce=True),
        "home_team_spread": Column("Float64", nullable=True, coerce=True),
    },
    strict=False,
    coerce=True,
)

# ---------------------------------------------------------------- player_box
# Provisional. Not checked against a real file (see module docstring). Core
# limited to what player-level box scores need to be at all: which game,
# which player, which team, and one representative shooting percentage to
# carry the 0-1 constraint. Extend this once a real sample is available,
# rather than guessing at the full stat line now.
PLAYER_BOX_SCHEMA: Final[DataFrameSchema] = DataFrameSchema(
    columns={
        "game_id": Column("Int64", nullable=False, coerce=True),
        "season": Column(
            "Int64", nullable=False, coerce=True, checks=Check.in_range(_MIN_SEASON, _MAX_SEASON)
        ),
        "athlete_id": Column("Int64", nullable=False, coerce=True),
        "team_id": Column("Int64", nullable=False, coerce=True),
        "minutes": Column("Float64", nullable=True, coerce=True, checks=Check.ge(0)),
        "field_goal_pct": Column(
            "Float64", nullable=True, coerce=True, checks=Check.in_range(0, 1)
        ),
    },
    # One row per player per game. A repeat of this pair means a duplicated
    # row from a bad concatenation or a re-download landing on top of itself.
    unique=["game_id", "athlete_id"],
    strict=False,
    coerce=True,
)

# ---------------------------------------------------------------- team_box
# Provisional, same caveat as player_box.
TEAM_BOX_SCHEMA: Final[DataFrameSchema] = DataFrameSchema(
    columns={
        "game_id": Column("Int64", nullable=False, coerce=True),
        "season": Column(
            "Int64", nullable=False, coerce=True, checks=Check.in_range(_MIN_SEASON, _MAX_SEASON)
        ),
        "team_id": Column("Int64", nullable=False, coerce=True),
        "field_goal_pct": Column(
            "Float64", nullable=True, coerce=True, checks=Check.in_range(0, 1)
        ),
    },
    # Exactly one row per team per game: two rows per game_id, never the same
    # team_id twice.
    unique=["game_id", "team_id"],
    strict=False,
    coerce=True,
)

# ---------------------------------------------------------------- schedules
# Provisional, same caveat as player_box. One row per game, so game_id itself
# must be unique here, unlike in the box scores.
SCHEDULES_SCHEMA: Final[DataFrameSchema] = DataFrameSchema(
    columns={
        "game_id": Column("Int64", nullable=False, coerce=True, unique=True),
        "season": Column(
            "Int64", nullable=False, coerce=True, checks=Check.in_range(_MIN_SEASON, _MAX_SEASON)
        ),
        "game_date": Column("string", nullable=True, coerce=True),
        "home_team_id": Column("Int64", nullable=False, coerce=True),
        "away_team_id": Column("Int64", nullable=False, coerce=True),
    },
    checks=[
        # Catches a join or scrape bug that copies one side's team into both,
        # not a real matchup. Not decorative: a team cannot play itself.
        Check(
            lambda frame: frame["home_team_id"] != frame["away_team_id"],
            name="distinct_teams",
            error="home_team_id must differ from away_team_id",
        ),
    ],
    strict=False,
    coerce=True,
)

# Single lookup so a caller asks for a schema by the same dataset name used
# throughout the rest of the data layer (see `pippen.data.hoopr.DATASETS`),
# instead of importing each schema constant by hand.
SCHEMAS: Final[dict[str, DataFrameSchema]] = {
    "play_by_play": PLAY_BY_PLAY_SCHEMA,
    "player_box": PLAYER_BOX_SCHEMA,
    "team_box": TEAM_BOX_SCHEMA,
    "schedules": SCHEDULES_SCHEMA,
}


class SchemaValidationError(ValueError):
    """A table failed schema validation.

    Raised by :func:`validate` with every failing row and check already
    collected, rather than only the first one, so a human fixes the file once
    instead of re-running validation after every single fix.
    """


def get_schema(dataset: str) -> DataFrameSchema:
    """Return the pandera schema for one dataset, by name.

    Args:
        dataset: Dataset name, e.g. ``"play_by_play"``. Must be a key of
            :data:`SCHEMAS`.

    Returns:
        The schema registered for ``dataset``.

    Raises:
        ValueError: If ``dataset`` is not a known dataset name.
    """
    try:
        return SCHEMAS[dataset]
    except KeyError:
        valid = ", ".join(sorted(SCHEMAS))
        raise ValueError(f"unknown dataset {dataset!r}; expected one of: {valid}") from None


def validate(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Validate a table against its schema and return the validated copy.

    Validation is lazy: every failing column and check is collected before
    raising, instead of stopping at the first one. Coercion happens as part
    of validation, so the returned frame's dtypes match the schema even when
    the input's did not.

    Args:
        frame: The table to validate.
        dataset: Dataset name identifying which schema to check against, e.g.
            ``"play_by_play"``. Must be a key of :data:`SCHEMAS`.

    Returns:
        ``frame`` with schema-declared columns coerced to their schema dtype.
        Columns not declared in the schema are passed through unchanged.

    Raises:
        ValueError: If ``dataset`` is not a known dataset name.
        SchemaValidationError: If ``frame`` fails one or more checks. The
            message lists every failure: which column, which check, which
            value, and which row.
    """
    schema = get_schema(dataset)
    try:
        validated = schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        raise SchemaValidationError(_describe_failures(dataset, exc)) from exc
    return validated


def _describe_failures(dataset: str, exc: pa.errors.SchemaErrors) -> str:
    """Render a pandera lazy-validation error as one human-readable report.

    Args:
        dataset: Dataset name the failing frame was validated against, used
            only to head the report.
        exc: The collected validation errors.

    Returns:
        A multi-line message: one summary line, then one line per failure.
    """
    cases = exc.failure_cases
    lines = [f"{dataset!r} failed schema validation ({len(cases)} problem(s)):"]
    lines.extend(f"  - {_describe_one_failure(row)}" for row in cases.itertuples())
    return "\n".join(lines)


def _describe_one_failure(row: Any) -> str:
    """Render one row of a pandera ``failure_cases`` table as one line.

    Args:
        row: A named tuple from iterating a ``failure_cases`` DataFrame.

    Returns:
        A single line naming the column, the check, and the offending value.
    """
    check = str(row.check)
    if check == "column_in_dataframe":
        return f"required column {row.failure_case!r} is missing"
    if check == "column_in_schema":
        return f"unexpected column {row.failure_case!r} is not declared in the schema"

    where = f"column {row.column!r}" if row.column else "table"
    at_row = f", row {row.index}" if pd.notna(row.index) else ""
    return f"{where} failed check {check!r} on value {row.failure_case!r}{at_row}"
