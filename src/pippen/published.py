"""The tables shipped inside the wheel, and the functions that read them.

Why the package carries data at all
-----------------------------------
Rebuilding these numbers takes hours. Possession data comes from data.nba.com at
one request per second by compliance rule, 11,070 games for the covered seasons,
and the ridge solve and reliability measurement run on top of that. An install
that could do nothing until the user had waited out that pipeline would be a
library rather than a metric, and Phase 4's exit condition asks for a metric.

So the computed outputs travel with the code. They are small, about 60 KiB
together, because a rating is one row per player per window rather than the
millions of possessions behind it.

The licence position
--------------------
Everything here is a derived value computed in this repository, which is the
category `docs/guides/licensing.md` marks publishable. The raw play-by-play that
produced it is not redistributed and is not in the wheel. RAPM is computed from
data.nba.com possessions, where derived features may be published and raw
responses may not. The reliability table is computed from hoopR, which is
CC BY 4.0, so it carries attribution rather than restriction.

Reading package data
--------------------
`importlib.resources.files` locates the tables rather than arithmetic on
``__file__``. The older approach assumes the package is a directory on a real
filesystem, which holds until someone installs from a zip import, runs from a
frozen bundle, or vendors the package inside another archive. The resources API
asks the loader that actually imported the module where its files are, so it
keeps working in all of those.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import as_file, files
from typing import Final

import pandas as pd

from pippen.data.possession_coefficient import coefficient_for_season

#: Import package whose installed files are searched for the shipped tables.
_DATA_PACKAGE: Final = "pippen"
#: Directory inside that package holding them.
_DATA_DIRECTORY: Final = "_data"

#: Earliest season covered by the shipped RAPM, in NBA labels. data.nba.com
#: serves no play-by-play before this; see docs/methodology/data-quirks.md.
FIRST_RAPM_SEASON: Final = 2016

#: Latest season covered. The upstream feed stopped being populated after it.
LAST_RAPM_SEASON: Final = 2024


class MissingBundledDataError(FileNotFoundError):
    """A table that should have been packaged is not in the installed wheel."""


@lru_cache(maxsize=4)
def _read(filename: str) -> pd.DataFrame:
    """Read one packaged table.

    Cached because these are read-mostly reference tables and a caller asking
    twice should not pay twice. The cache holds the frame, so a caller that
    mutates what it receives would affect the next caller; every public function
    here returns a copy for that reason.

    Args:
        filename: Name of the file inside the package data directory.

    Returns:
        The table.

    Raises:
        MissingBundledDataError: If the file is absent, which means the wheel
            was built without its data rather than that the user did something
            wrong.
    """
    # Chained rather than joinpath(a, b): the Traversable protocol only
    # guarantees a single-argument joinpath on Python 3.10.
    resource = files(_DATA_PACKAGE).joinpath(_DATA_DIRECTORY).joinpath(filename)
    if not resource.is_file():
        raise MissingBundledDataError(
            f"{filename} is not in the installed package. The wheel was built "
            f"without its data; reinstall from a release artifact."
        )
    with as_file(resource) as path:
        return pd.read_parquet(path)


def rapm_ratings(window_end: int | None = None, *, min_possessions: float = 0.0) -> pd.DataFrame:
    """Return player impact per 100 possessions, by three-season window.

    Each rating pools three seasons. A single season measures 0.601 on
    split-half reliability and three seasons 0.796, which is why single-season
    ratings are not shipped.

    Args:
        window_end: Last season of the window, in NBA labels, so 2024 means the
            window ending with the 2024-25 season. Every window is returned when
            omitted.
        min_possessions: Drop players below this many possessions in the window.
            A rating resting on few possessions is mostly the ridge prior, and
            its narrow bootstrap interval reflects that shrinkage rather than
            precision.

    Returns:
        One row per player per window, with ``offensive``, ``defensive`` and
        ``total`` in points per 100 possessions. Both components are signed so
        that higher is better, so ``total`` is their sum.

        ``first_season``, ``last_season`` and ``seasons_played`` describe the
        seasons in which that player actually recorded a possession inside the
        window, which is not always the whole window. 2,994 of the 5,427 rows
        cover fewer than three seasons, so reading ``window_start`` to
        ``window_end`` as the evidence behind a rating overstates it. Austin
        Reaves appears under the window ending 2021 having played only 2021-22.

        The window is still the right unit for the fit: a player is estimated
        against everyone who shared the floor across all three seasons. It is
        the wrong unit for a label.

    Raises:
        MissingBundledDataError: If the table is not in the installed package.
        ValueError: If ``window_end`` names a window that was not computed.
    """
    table = _read("rapm_ratings.parquet")
    if window_end is not None:
        available = sorted(table["window_end"].unique())
        if window_end not in available:
            raise ValueError(
                f"no window ends in {window_end}; available windows end in "
                f"{available[0]} through {available[-1]}"
            )
        table = table[table["window_end"] == window_end]
    if min_possessions > 0:
        table = table[table["possessions"] >= min_possessions]
    # Copied explicitly. Whether a filter or reset_index already produced one
    # depends on the pandas version and on whether any filtering happened at
    # all, and _read is cached, so a caller mutating the result would change
    # what every later caller in the process sees.
    return table.reset_index(drop=True).copy()


def metric_reliability(season: int | None = None, *, rule: str = "random") -> pd.DataFrame:
    """Return the measured split-half reliability of each box-score metric.

    Reliability here is the share of a metric's variance that is signal rather
    than noise, estimated by splitting each player's season in two, computing
    the metric on each half, correlating across players, and applying the
    Spearman-Brown correction for length.

    The figures are a ceiling on how much a metric can contribute rather than a
    weight to apply. Across this metric set reliability correlates -0.564 with
    correlation against RAPM, so the most repeatable metrics are the least
    related to winning.

    Args:
        season: hoopR season label, which names the year a season ends, so 2024
            means 2023-24. Every season is returned when omitted.
        rule: ``random`` for the average of 100 random splits, or ``odd_even``
            for the single conventional split, reported for comparison.

    Returns:
        One row per metric per season, carrying the half correlation, its spread
        across splits, and the reliability implied at 82 games. No column is
        named ``reliability`` alone, because the same measurement implies very
        different figures at different lengths.

    Raises:
        MissingBundledDataError: If the table is not in the installed package.
        ValueError: If ``season`` or ``rule`` is not present.
    """
    table = _read("metric_reliability.parquet")
    rules = sorted(table["rule"].unique())
    if rule not in rules:
        raise ValueError(f"unknown rule {rule!r}; available: {rules}")
    table = table[table["rule"] == rule]
    if season is not None:
        available = sorted(table["season"].unique())
        if season not in available:
            raise ValueError(
                f"no measurement for {season}; available: {available[0]} to {available[-1]}"
            )
        table = table[table["season"] == season]
    return table.reset_index(drop=True).copy()


def possession_coefficient(season: int) -> float:
    """Return the measured share of free throw attempts that consume a possession.

    The conventional value is 0.44 and appears in true shooting, usage, pace and
    turnover rate. This project measured it per season from play-by-play across
    1,467,112 attempts, and every one of 25 seasons came out below the
    convention, pooling at 0.4178.

    The reason is arithmetic. A two-shot foul ends one possession rather than
    two, an and-one ends none, and the mix of those shifts with rule changes.

    Args:
        season: hoopR season label, which names the year a season ends.

    Returns:
        The measured coefficient, or the pooled value for a season with no
        measurement of its own.
    """
    return coefficient_for_season(season)
