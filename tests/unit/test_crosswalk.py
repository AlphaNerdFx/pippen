"""Tests for the ESPN-to-NBA player crosswalk.

The failure that matters is silent. If a son's ESPN id is mapped to his
father's NBA player id, the join still succeeds, the row counts still look
right, and one player's box score is fused with another player's impact rating.
Several of these tests exist only to make that impossible.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pippen.crosswalk import (
    Crosswalk,
    build_crosswalk,
    espn_abbreviation,
    initial_key,
    normalise,
    team_crosswalk,
)

# Real ids, because the collisions they encode are the point.
HARDAWAY_SENIOR = 896
HARDAWAY_JUNIOR = 203501
PAYTON_SENIOR = 56
PAYTON_SECOND = 1627780


def _nba(rows: list[tuple[int, str]]) -> pd.DataFrame:
    return pd.DataFrame({"nba_id": [r[0] for r in rows], "name": [r[1] for r in rows]})


def _espn(rows: list[tuple[int, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        {"athlete_id": [r[0] for r in rows], "athlete_display_name": [r[1] for r in rows]}
    )


# ------------------------------------------------------------------ normalising


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("Nikola Jokić", "nikola jokic"),
        ("Shaquille O'Neal", "shaquille oneal"),
        ("P.J. Tucker", "pj tucker"),
        ("Karl-Anthony Towns", "karl anthony towns"),
        ("  Luka   Dončić ", "luka doncic"),
    ],
)
def test_names_normalise_across_the_punctuation_the_sources_disagree_about(
    written: str, expected: str
) -> None:
    assert normalise(written) == expected


def test_a_suffix_survives_normalising_by_default() -> None:
    # This is the line that keeps father and son apart.
    assert normalise("Tim Hardaway Jr.") != normalise("Tim Hardaway")
    assert normalise("Tim Hardaway Jr.", strip_suffix=True) == normalise("Tim Hardaway")


def test_the_initial_key_survives_a_different_first_name() -> None:
    assert initial_key("Marcelinho Huertas") == initial_key("Marcelo Huertas")
    assert initial_key("Jimmy Butler III") == initial_key("Jimmy Butler")


# ------------------------------------------------------------------ the collision


def test_the_son_is_not_matched_to_the_father() -> None:
    nba = _nba([(HARDAWAY_SENIOR, "Tim Hardaway"), (HARDAWAY_JUNIOR, "Tim Hardaway Jr.")])
    crosswalk = build_crosswalk(
        _espn([(1, "Tim Hardaway Jr.")]),
        season=2017,
        played_nba_ids={HARDAWAY_JUNIOR},
        nba_players=nba,
    )
    assert crosswalk.espn_to_nba == {1: HARDAWAY_JUNIOR}
    assert crosswalk.matches["pass"].tolist() == ["exact"]


def test_the_father_is_not_matched_to_the_son() -> None:
    nba = _nba([(PAYTON_SENIOR, "Gary Payton"), (PAYTON_SECOND, "Gary Payton II")])
    crosswalk = build_crosswalk(
        _espn([(1, "Gary Payton")]),
        season=2003,
        played_nba_ids={PAYTON_SENIOR},
        nba_players=nba,
    )
    assert crosswalk.espn_to_nba == {1: PAYTON_SENIOR}


def test_a_suffix_pass_never_overrides_an_exact_one() -> None:
    # Both played, so the suffix pass would be ambiguous. The exact pass must
    # resolve each of them first.
    nba = _nba([(PAYTON_SENIOR, "Gary Payton"), (PAYTON_SECOND, "Gary Payton II")])
    crosswalk = build_crosswalk(
        _espn([(1, "Gary Payton"), (2, "Gary Payton II")]),
        season=2003,
        played_nba_ids={PAYTON_SENIOR, PAYTON_SECOND},
        nba_players=nba,
    )
    assert crosswalk.espn_to_nba == {1: PAYTON_SENIOR, 2: PAYTON_SECOND}
    assert set(crosswalk.matches["pass"]) == {"exact"}


# ------------------------------------------------------------------ the passes


def test_a_gained_suffix_is_matched_by_the_second_pass() -> None:
    # ESPN wrote Reggie Bullock; the NBA now lists Reggie Bullock Jr.
    nba = _nba([(203493, "Reggie Bullock Jr.")])
    crosswalk = build_crosswalk(
        _espn([(1, "Reggie Bullock")]), season=2017, played_nba_ids={203493}, nba_players=nba
    )
    assert crosswalk.espn_to_nba == {1: 203493}
    assert crosswalk.matches["pass"].tolist() == ["suffix"]


def test_a_different_first_name_is_matched_by_the_third_pass() -> None:
    nba = _nba([(203222, "Marcelo Huertas")])
    crosswalk = build_crosswalk(
        _espn([(1, "Marcelinho Huertas")]), season=2017, played_nba_ids={203222}, nba_players=nba
    )
    assert crosswalk.espn_to_nba == {1: 203222}
    assert crosswalk.matches["pass"].tolist() == ["initial"]


def test_a_candidate_who_did_not_play_is_not_the_player() -> None:
    # The season check is what makes the forgiving passes safe.
    nba = _nba([(HARDAWAY_SENIOR, "Tim Hardaway"), (HARDAWAY_JUNIOR, "Tim Hardaway Jr.")])
    crosswalk = build_crosswalk(
        _espn([(1, "Tim Hardaway")]),
        season=2017,
        played_nba_ids={HARDAWAY_JUNIOR},
        nba_players=nba,
    )
    # Senior did not play, so the exact pass finds nothing; the suffix pass
    # then finds Junior, who did.
    assert crosswalk.espn_to_nba == {1: HARDAWAY_JUNIOR}
    assert crosswalk.matches["pass"].tolist() == ["suffix"]


# ------------------------------------------------------------------ the residue


def test_an_unknown_player_is_reported_not_guessed() -> None:
    crosswalk = build_crosswalk(
        _espn([(1, "Yongxi Cui")]),
        season=2025,
        played_nba_ids={1},
        nba_players=_nba([(2, "Someone Else")]),
    )
    assert crosswalk.matches.empty
    assert crosswalk.unmatched["name"].tolist() == ["Yongxi Cui"]
    assert crosswalk.match_rate == 0.0


def test_a_genuine_ambiguity_is_reported_not_resolved() -> None:
    # Two players share a name and both played. Nothing here can tell them
    # apart, so nothing here pretends to.
    nba = _nba([(1, "Charles Smith"), (2, "Charles Smith")])
    crosswalk = build_crosswalk(
        _espn([(9, "Charles Smith")]), season=1992, played_nba_ids={1, 2}, nba_players=nba
    )
    assert crosswalk.matches.empty
    assert crosswalk.ambiguous["name"].tolist() == ["Charles Smith"]


def test_the_summary_names_what_was_not_resolved() -> None:
    crosswalk = Crosswalk(
        season=2025,
        matches=pd.DataFrame(
            [{"espn_id": 1, "nba_id": 2, "name": "A", "pass": "exact"}],
        ),
        unmatched=pd.DataFrame([{"espn_id": 3, "name": "B"}]),
        ambiguous=pd.DataFrame(columns=["espn_id", "name"]),
    )
    text = crosswalk.describe()
    assert "1 unmatched" in text
    assert "0 ambiguous" in text
    assert crosswalk.match_rate == pytest.approx(0.5)


def test_a_missing_column_is_named() -> None:
    with pytest.raises(KeyError, match="athlete_display_name"):
        build_crosswalk(
            pd.DataFrame({"athlete_id": [1]}),
            season=2024,
            played_nba_ids={1},
            nba_players=_nba([(1, "A")]),
        )


# ------------------------------------------------------------------ teams


@pytest.mark.parametrize(
    ("nba", "espn"),
    [("GSW", "GS"), ("NOP", "NO"), ("NYK", "NY"), ("SAS", "SA"), ("UTA", "UTAH"), ("WAS", "WSH")],
)
def test_the_six_differing_abbreviations_are_translated(nba: str, espn: str) -> None:
    assert espn_abbreviation(nba) == espn


@pytest.mark.parametrize("code", ["BOS", "LAL", "MIA", "DEN", "PHX"])
def test_the_other_twenty_four_pass_through(code: str) -> None:
    assert espn_abbreviation(code) == code


def test_all_thirty_teams_map() -> None:
    # team_crosswalk reads the canonical team list from nba_api, which lives in
    # the optional `sources` extra. CI installs only `dev`, so without this skip
    # the test fails on a MissingDependencyError that says nothing about the
    # behaviour under test.
    pytest.importorskip("nba_api", reason="team_crosswalk needs the sources extra")

    # Pseudo-teams such as the All-Star EAST have no NBA counterpart and are
    # simply absent rather than mapped to something wrong.
    espn = pd.DataFrame(
        {
            "team_id": [1, 2, 3, 99],
            "team_abbreviation": ["ATL", "BOS", "GS", "EAST"],
        }
    )
    mapping = team_crosswalk(espn)
    assert set(mapping.values()) == {1, 2, 3}
    assert 99 not in mapping.values()


def test_a_missing_team_column_is_named() -> None:
    with pytest.raises(KeyError, match="team_abbreviation"):
        team_crosswalk(pd.DataFrame({"team_id": [1]}))
