"""Joining ESPN athlete ids to NBA player ids.

The problem
-----------
This project draws on two sources that share no key. Box scores come from
hoopR, which is ESPN-sourced and identifies players by ``athlete_id``. RAPM
comes from data.nba.com, which identifies them by NBA ``player_id``. The
fusion model has to put a player's box-score metrics beside his RAPM rating,
and nothing in either file says which rows belong to the same person.

The only shared attribute is the name, and names are a bad key. They collide
between fathers and sons who both played, they change when a player adopts a
suffix, and they are transliterated differently between sources.

The approach
------------
Three passes over increasingly forgiving name keys, each one checked against a
fact the project already knows: which NBA player ids actually appear in that
season's possession data. A candidate that did not play that season is not that
player, whatever the name says.

``exact``
    Normalised name including any suffix. ``Gary Payton`` and
    ``Gary Payton II`` stay distinct here, which matters because both played.

``suffix``
    Suffix stripped. Catches a player whose canonical name gained a suffix
    between sources, such as Reggie Bullock, listed by the NBA as Reggie
    Bullock Jr. and by ESPN without it.

``initial``
    Last name plus first initial. Catches transliteration and nickname
    differences, such as Marcelinho against Marcelo Huertas.

A pass accepts a match only when exactly one candidate played that season.
Anything still ambiguous is reported as ambiguous rather than resolved by
picking the first, because picking the first is how a son's box score ends up
attached to his father's impact rating with nothing downstream to catch it.

Why not fuzzy string distance
-----------------------------
Edit distance would match the remaining handful and would also match pairs that
are genuinely different people, silently. The residue here is small enough to
list, and listing it is more useful than a similarity threshold nobody can
audit. Unmatched players are returned, not dropped.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

import pandas as pd

from pippen.errors import MissingDependencyError

#: Name suffixes stripped by the second pass.
SUFFIXES: Final = ("jr", "sr", "ii", "iii", "iv", "v")

#: Passes attempted, in order. Each is more forgiving than the last.
PASSES: Final = ("exact", "suffix", "initial")

_SUFFIX_PATTERN: Final = re.compile(r"\b(" + "|".join(SUFFIXES) + r")\b")
_SPACES: Final = re.compile(r"\s+")


def normalise(name: str, *, strip_suffix: bool = False) -> str:
    """Return a comparable form of a player name.

    Strips accents, lowercases, and removes the punctuation the two sources
    disagree about: full stops in initials, apostrophes, and hyphens.

    Args:
        name: Name as written by either source.
        strip_suffix: Also remove a generational suffix. Off by default,
            because ``Gary Payton`` and ``Gary Payton II`` are different people
            and both played.

    Returns:
        The normalised name.
    """
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower().replace(".", "").replace("'", "").replace("-", " ")
    if strip_suffix:
        text = _SUFFIX_PATTERN.sub("", text)
    return _SPACES.sub(" ", text).strip()


def initial_key(name: str) -> str:
    """Return a last-name-plus-first-initial key.

    The most forgiving key used, for transliteration and nickname differences.
    Built from the suffix-stripped name so that ``Marcelinho Huertas`` and
    ``Marcelo Huertas`` meet.

    Args:
        name: Name as written by either source.

    Returns:
        A key such as ``huertas m``, or the whole normalised name when it is a
        single word.
    """
    parts = normalise(name, strip_suffix=True).split()
    if len(parts) < 2:
        return " ".join(parts)
    return f"{parts[-1]} {parts[0][0]}"


def _keys(name: str) -> dict[str, str]:
    """Return the key for each pass, for one name."""
    return {
        "exact": normalise(name),
        "suffix": normalise(name, strip_suffix=True),
        "initial": initial_key(name),
    }


@dataclass(frozen=True)
class Crosswalk:
    """A resolved mapping between the two identifier spaces.

    Attributes:
        season: hoopR season label the crosswalk was built for.
        matches: One row per matched player, with ``espn_id``, ``nba_id``,
            ``name`` and the ``pass`` that resolved it.
        unmatched: Players with no candidate that played this season.
        ambiguous: Players with more than one such candidate. Reported rather
            than resolved.
    """

    season: int
    matches: pd.DataFrame
    unmatched: pd.DataFrame
    ambiguous: pd.DataFrame

    @property
    def espn_to_nba(self) -> dict[int, int]:
        """The mapping, as a plain dictionary."""
        return {
            int(espn): int(nba)
            for espn, nba in zip(self.matches["espn_id"], self.matches["nba_id"], strict=True)
        }

    @property
    def match_rate(self) -> float:
        """Share of players resolved, between 0 and 1."""
        total = len(self.matches) + len(self.unmatched) + len(self.ambiguous)
        return len(self.matches) / total if total else 0.0

    def describe(self) -> str:
        """Return a one-line summary naming what was not resolved."""
        counts = self.matches["pass"].value_counts().to_dict()
        detail = ", ".join(f"{name} {counts.get(name, 0)}" for name in PASSES)
        return (
            f"season {self.season}: {len(self.matches)} matched "
            f"({self.match_rate:.1%}) by {detail}; "
            f"{len(self.unmatched)} unmatched, {len(self.ambiguous)} ambiguous"
        )


def nba_player_names() -> pd.DataFrame:
    """Return every NBA player id and name from ``nba_api``'s static list.

    The list ships with the package, so this needs no network and no rate
    limiting.

    Returns:
        A frame with ``nba_id`` and ``name``.

    Raises:
        MissingDependencyError: If ``nba_api`` is not installed.
    """
    try:
        from nba_api.stats.static import players
    except ImportError as exc:
        raise MissingDependencyError(
            "nba_api is required for the player crosswalk; install the 'sources' extra"
        ) from exc
    listed = players.get_players()
    return pd.DataFrame(
        {
            "nba_id": [int(entry["id"]) for entry in listed],
            "name": [str(entry["full_name"]) for entry in listed],
        }
    )


def build_crosswalk(
    espn_players: pd.DataFrame,
    *,
    season: int,
    played_nba_ids: Collection[int],
    nba_players: pd.DataFrame | None = None,
) -> Crosswalk:
    """Resolve ESPN athlete ids to NBA player ids for one season.

    Args:
        espn_players: Frame with ``athlete_id`` and ``athlete_display_name``,
            one row per player.
        season: hoopR season label, for reporting.
        played_nba_ids: NBA player ids known to have appeared that season,
            typically from the season's stints. This is what makes the name
            passes safe: a candidate who did not play is not the right player.
        nba_players: Frame with ``nba_id`` and ``name``. Defaults to
            :func:`nba_player_names`.

    Returns:
        A :class:`Crosswalk`.

    Raises:
        KeyError: If ``espn_players`` lacks a required column.
    """
    required = {"athlete_id", "athlete_display_name"}
    missing = sorted(required - set(espn_players.columns))
    if missing:
        raise KeyError(f"espn_players is missing columns: {missing}")

    nba = nba_players if nba_players is not None else nba_player_names()
    played = {int(identifier) for identifier in played_nba_ids}

    indexes: dict[str, dict[str, list[int]]] = {}
    for name in PASSES:
        keyed = nba.assign(key=[_keys(value)[name] for value in nba["name"]])
        grouped = keyed.groupby("key")["nba_id"].apply(list).to_dict()
        indexes[name] = {str(key): list(value) for key, value in grouped.items()}

    matched: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []

    for espn_id, display_name in zip(
        espn_players["athlete_id"], espn_players["athlete_display_name"], strict=True
    ):
        keys = _keys(str(display_name))
        best: tuple[str, int] | None = None
        seen_candidates = False

        for name in PASSES:
            candidates = indexes[name].get(keys[name], [])
            if candidates:
                seen_candidates = True
            here = [candidate for candidate in candidates if candidate in played]
            if len(here) == 1:
                best = (name, here[0])
                break

        if best is not None:
            matched.append(
                {
                    "espn_id": int(espn_id),
                    "nba_id": int(best[1]),
                    "name": str(display_name),
                    "pass": best[0],
                }
            )
        elif seen_candidates:
            ambiguous.append({"espn_id": int(espn_id), "name": str(display_name)})
        else:
            unmatched.append({"espn_id": int(espn_id), "name": str(display_name)})

    columns = ["espn_id", "nba_id", "name", "pass"]
    return Crosswalk(
        season=season,
        matches=pd.DataFrame(matched, columns=columns),
        unmatched=pd.DataFrame(unmatched, columns=["espn_id", "name"]),
        ambiguous=pd.DataFrame(ambiguous, columns=["espn_id", "name"]),
    )


#: ESPN and the NBA agree on twenty-four of thirty team abbreviations. These
#: six differ. Derived by comparing the two sets on 2016-17 rather than
#: recalled, and valid across the seasons on disk, which contain no relocation
#: or rebrand.
NBA_TO_ESPN_ABBREVIATION: Final = {
    "GSW": "GS",
    "NOP": "NO",
    "NYK": "NY",
    "SAS": "SA",
    "UTA": "UTAH",
    "WAS": "WSH",
}


def espn_abbreviation(nba_tricode: str) -> str:
    """Return the ESPN abbreviation for an NBA tricode.

    Args:
        nba_tricode: Three-letter NBA code, such as ``GSW``.

    Returns:
        The ESPN spelling, which is the same string for twenty-four of thirty
        teams.
    """
    return NBA_TO_ESPN_ABBREVIATION.get(nba_tricode, nba_tricode)


def team_crosswalk(espn_teams: pd.DataFrame) -> dict[int, int]:
    """Map NBA team ids to ESPN team ids.

    The two sources disagree on both the identifier and the abbreviation, so
    this goes through the abbreviation with the six known differences applied.
    Team ids are stable across seasons, unlike player ids, so one mapping
    serves every season on disk.

    Args:
        espn_teams: Frame carrying ``team_id`` and ``team_abbreviation`` as
            hoopR writes them, typically from a box score.

    Returns:
        NBA team id to ESPN team id, covering only the teams present in
        ``espn_teams``. A pseudo-team such as the All-Star ``EAST`` has no NBA
        counterpart and is simply absent.

    Raises:
        MissingDependencyError: If ``nba_api`` is not installed.
        KeyError: If a required column is absent.
    """
    required = {"team_id", "team_abbreviation"}
    missing = sorted(required - set(espn_teams.columns))
    if missing:
        raise KeyError(f"espn_teams is missing columns: {missing}")

    try:
        from nba_api.stats.static import teams as nba_teams
    except ImportError as exc:
        raise MissingDependencyError(
            "nba_api is required for the team crosswalk; install the 'sources' extra"
        ) from exc

    espn_by_abbreviation = {
        str(abbreviation): int(team_id)
        for team_id, abbreviation in zip(
            espn_teams["team_id"], espn_teams["team_abbreviation"], strict=True
        )
    }

    mapping: dict[int, int] = {}
    for entry in nba_teams.get_teams():
        espn_code = espn_abbreviation(str(entry["abbreviation"]))
        if espn_code in espn_by_abbreviation:
            mapping[int(entry["id"])] = espn_by_abbreviation[espn_code]
    return mapping
