"""Add the seasons a player actually played to the shipped RAPM table.

A rating is computed over a three-season window, and a player who joined the
league partway through that window still gets a row labelled with the whole
window. Austin Reaves appears under 2019-2021 having played only 2021-22, which
reads as three seasons of evidence when it is one.

The window is still the right unit for the fit. It is the wrong unit for a
label, and the shipped table carried no way to tell them apart.

This derives, per player and per window, the first and last season in which that
player recorded a possession, from the stint files the ratings were fit on. It
augments the existing table rather than recomputing the ratings, so every
published figure keeps its value.

The check that makes this trustworthy: per-season possessions summed over the
seasons a player actually played must equal the possession count already in the
shipped table, for every one of its rows. If that reconciliation fails the
script writes nothing.

Run from the repository root, with data/interim/stints_*.parquet present:

    uv run python scripts/add_tenure_columns.py
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import pandas as pd

STINTS = Path("data/interim")
TABLE = Path("src/pippen/_data/rapm_ratings.parquet")


def possessions_by_player_season() -> dict[int, collections.Counter[int]]:
    """Return possessions per player per NBA season, from the stint files.

    A player's possessions are those of every stint they appear in, on either
    side of the ball, which is the same convention the design matrix uses: one
    row per stint with the player marked +1 on offence or -1 on defence.

    Returns:
        Mapping of player id to a counter of season to possessions.
    """
    totals: dict[int, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    files = sorted(STINTS.glob("stints_*.parquet"))
    if not files:
        raise SystemExit(f"no stint files in {STINTS}; run `pippen stints` first")

    for path in files:
        match = re.search(r"(\d{4})", path.name)
        if match is None:
            continue
        season = int(match.group(1))
        frame = pd.read_parquet(path, columns=["offense_lineup", "defense_lineup", "possessions"])
        for column in ("offense_lineup", "defense_lineup"):
            exploded = (
                frame[[column, "possessions"]]
                .assign(player_id=frame[column].str.split("-"))
                .explode("player_id")
            )
            summed = exploded.groupby("player_id")["possessions"].sum()
            for player_id, possessions in summed.items():
                totals[int(player_id)][season] += int(possessions)
        print(f"  read {path.name}: {len(frame):,} stints")
    return totals


def main() -> int:
    """Augment the shipped table, refusing to write if the totals disagree."""
    if not TABLE.exists():
        raise SystemExit(f"{TABLE} not found")

    print("deriving per-season possessions from stints")
    totals = possessions_by_player_season()

    table = pd.read_parquet(TABLE)
    print(f"shipped table: {len(table):,} rows, columns {list(table.columns)}")

    first_seasons: list[int] = []
    last_seasons: list[int] = []
    seasons_played: list[int] = []
    disagreements: list[str] = []

    for row in table.itertuples(index=False):
        window = range(int(row.window_start), int(row.window_end) + 1)
        by_season = totals.get(int(row.player_id), collections.Counter())
        played = [season for season in window if by_season.get(season, 0) > 0]

        if not played:
            # No stint evidence inside the window. Keep the window as the span
            # rather than inventing one, and report it.
            disagreements.append(
                f"player {row.player_id} window {row.window_start}-{row.window_end}: no stints"
            )
            first_seasons.append(int(row.window_start))
            last_seasons.append(int(row.window_end))
            seasons_played.append(0)
            continue

        derived = sum(by_season[season] for season in played)
        if derived != int(row.possessions):
            disagreements.append(
                f"player {row.player_id} window {row.window_start}-{row.window_end}: "
                f"derived {derived} but table says {int(row.possessions)}"
            )
        first_seasons.append(played[0])
        last_seasons.append(played[-1])
        seasons_played.append(len(played))

    if disagreements:
        print(
            f"\nREFUSING TO WRITE: {len(disagreements)} row(s) did not reconcile", file=sys.stderr
        )
        for line in disagreements[:10]:
            print(f"  {line}", file=sys.stderr)
        return 1

    table["first_season"] = pd.Series(first_seasons, dtype="int64")
    table["last_season"] = pd.Series(last_seasons, dtype="int64")
    table["seasons_played"] = pd.Series(seasons_played, dtype="int64")
    table.to_parquet(TABLE, index=False)

    partial = int((table["seasons_played"] < 3).sum())
    print("\nevery row reconciled against the shipped possession count")
    print(f"wrote {TABLE} ({TABLE.stat().st_size:,} bytes)")
    print(f"rows whose player did not play the whole window: {partial:,} of {len(table):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
