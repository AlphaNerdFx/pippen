"""Conversion between the two season-labelling conventions this project meets.

The trap
--------
A basketball season spans two calendar years, and the project's two data
sources disagree about which one names it.

hoopR labels a season by the year it **ends**. Its ``team_box_2017.parquet``
holds games from 2016-10-25 to 2017-04-12, which is the 2016-17 season.

The NBA labels a season by the year it **starts**. Game id ``0021600001`` is
from that same 2016-17 season, and data.nba.com serves it under ``/nba/2016/``.

So hoopR 2017 and NBA 2016 are the same basketball. Every join between a RAPM
rating and a box-score metric crosses this boundary, and getting it wrong
shifts every player's inputs by a full year. Nothing downstream would catch it:
the join still matches, the row counts still look right, and the model simply
learns from the wrong season.

The rule
--------
``hoopr = nba + 1``. These functions exist so that rule is applied by name
rather than remembered, and so a reader of a call site can see which convention
a number is in.

Where each convention appears
-----------------------------
================================  ==========
Module or path                    Convention
================================  ==========
``pippen.data.hoopr``             hoopR
``data/raw/play_by_play/*``       hoopR
``data/raw/player_box/*``         hoopR
``data/raw/team_box/*``           hoopR
``pippen.data.possession_coefficient``  hoopR
``pippen.rapm.pbp_source``        NBA
``pippen.rapm.possessions``       NBA
``data/raw/pbpstats/*``           NBA
================================  ==========
"""

from __future__ import annotations

from typing import Final

#: Difference between the two labels for the same season.
OFFSET: Final = 1


def hoopr_from_nba(nba_season: int) -> int:
    """Return the hoopR label for the season the NBA calls ``nba_season``.

    Args:
        nba_season: Season start year, as used in NBA game ids and
            data.nba.com URLs. 2016 means the 2016-17 season.

    Returns:
        The hoopR label for the same season, 2017 for the example above.
    """
    return nba_season + OFFSET


def nba_from_hoopr(hoopr_season: int) -> int:
    """Return the NBA label for the season hoopR calls ``hoopr_season``.

    Args:
        hoopr_season: Season end year, as used in hoopR file names. 2017 means
            the 2016-17 season.

    Returns:
        The NBA label for the same season, 2016 for the example above.
    """
    return hoopr_season - OFFSET


def describe(nba_season: int) -> str:
    """Return the human name of a season given its NBA label.

    Args:
        nba_season: Season start year.

    Returns:
        A string such as ``2016-17``, unambiguous under either convention,
        which is what belongs in anything a person reads.
    """
    return f"{nba_season}-{(nba_season + 1) % 100:02d}"
