"""Cross-source check: do possession-derived points match an independent score?

Every other test in this project checks the code against itself. This one
checks it against a different organisation's record of the same games. The
possessions come from data.nba.com, walked by ``pbpstats``; the scores come
from ESPN by way of hoopR. If the possession walk drops events, double-counts
free throws, or attributes points to the wrong side, the two disagree.

The test skips when the data is not on disk, because data never enters git and
a clean checkout has none. It is not marked ``network``: it reads what has
already been downloaded and makes no requests of its own.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from pippen.crosswalk import espn_abbreviation
from pippen.paths import season_file
from pippen.rapm.pbp_source import cache_root
from pippen.rapm.possessions import game_stints, points_by_team
from pippen.seasons import hoopr_from_nba

#: How many games to check. The point is to catch a systematic error, which
#: shows up in the first handful, not to re-verify every game on every run.
GAMES_CHECKED = 40


def _downloaded_games(season: int) -> list[Path]:
    prefix = f"data_002{season % 100:02d}"
    return sorted(cache_root().glob(f"pbp/{prefix}*.json"))


@pytest.fixture(scope="module")
def reference_scores() -> pd.DataFrame:
    """Final scores from hoopR, the independent source."""
    # hoopR labels a season by the year it ends, so the 2016-17 season the
    # NBA calls 2016 lives in hoopR's 2017 file. See pippen.seasons.
    path = season_file("raw", "team_box", hoopr_from_nba(2016))
    if not path.exists():
        pytest.skip(f"no hoopR team box on disk at {path}")
    frame = pd.read_parquet(
        path, columns=["game_date", "team_abbreviation", "team_score", "season_type"]
    )
    return frame[frame["season_type"] == 2]


@pytest.fixture(scope="module")
def downloaded() -> list[Path]:
    games = _downloaded_games(2016)
    if len(games) < GAMES_CHECKED:
        pytest.skip(f"only {len(games)} games of 2016-17 downloaded; run `pippen possessions`")
    return games[:GAMES_CHECKED]


def test_possession_points_match_an_independent_source(
    downloaded: list[Path], reference_scores: pd.DataFrame
) -> None:
    compared = 0
    disagreements: list[str] = []

    for path in downloaded:
        match = re.search(r"data_(\d+)\.json", path.name)
        assert match is not None
        game_id = match.group(1)

        raw = json.loads(path.read_text())["g"]
        gcode = raw.get("gcode", "")
        if "/" not in gcode:
            continue
        stamp, teams = gcode.split("/")
        played_on = pd.Timestamp(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}").date()
        sides = [espn_abbreviation(teams[:3]), espn_abbreviation(teams[3:])]

        rows = reference_scores[
            (reference_scores["game_date"] == played_on)
            & (reference_scores["team_abbreviation"].isin(sides))
        ]
        if len(rows) != 2:
            continue

        try:
            stints = game_stints(game_id)
        except Exception:  # a parse failure is measured elsewhere, not here
            continue

        derived = sorted(points_by_team(stints).values())
        reference = sorted(int(score) for score in rows["team_score"])
        compared += 1
        if derived != reference:
            disagreements.append(f"{game_id} {gcode}: possessions {derived} vs hoopR {reference}")

    assert compared >= 20, f"only {compared} games could be joined to a reference score"
    assert not disagreements, "\n".join(disagreements)


def test_every_checked_game_has_five_players_a_side(downloaded: list[Path]) -> None:
    from pippen.rapm.possessions import has_valid_lineups

    checked = 0
    for path in downloaded[:10]:
        match = re.search(r"data_(\d+)\.json", path.name)
        assert match is not None
        try:
            stints = game_stints(match.group(1))
        except Exception:
            continue
        if stints.empty:
            continue
        checked += 1
        assert has_valid_lineups(stints).all(), f"{path.name} has a malformed lineup"
    assert checked > 0, "no game parsed, so nothing was checked"
