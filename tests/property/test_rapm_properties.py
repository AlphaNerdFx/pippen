"""Properties the RAPM pipeline must hold for any input, not just the examples.

An example test says the code handled one case. A property test states a rule
and lets Hypothesis search for an input that breaks it. That suits this layer:
the design matrix and the solve are pure functions of a stint frame, the rules
they must obey are short to state, and the failures that matter are the ones
nobody thought to write an example for.

Three properties are checked here, matching Phase 2's list.

Five a side
    Every row of the design matrix names exactly five offensive and five
    defensive players. A row that does not means the substitution walk lost
    track, and the solver would place a player on the floor who was not there.

Possessions reconcile
    Total possessions and points in the design equal the totals in the stints
    it was built from. Aggregation must not create or destroy evidence.

Order invariance
    Ratings must not depend on the order players happen to appear in, nor on
    the order the stint rows arrive in. Both are arbitrary, so any dependence
    on them is a bug in indexing rather than a property of basketball.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pippen.rapm.design import build_design
from pippen.rapm.ridge import fit_ridge

# A pool small enough that lineups overlap, which is the regime that makes
# RAPM hard, and large enough that ten distinct players can be drawn.
_PLAYER_POOL = 14

_stint_counts = st.integers(min_value=1, max_value=60)
_point_counts = st.integers(min_value=0, max_value=150)


@st.composite
def _stint_frames(draw: st.DrawFn, min_rows: int = 1, max_rows: int = 40) -> pd.DataFrame:
    """Generate a stint frame with well-formed five-a-side lineups."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    n_games = draw(st.integers(min_value=1, max_value=4))
    rows = []
    for _ in range(n_rows):
        ten = draw(
            st.lists(
                st.integers(min_value=1, max_value=_PLAYER_POOL),
                min_size=10,
                max_size=10,
                unique=True,
            )
        )
        possessions = draw(_stint_counts)
        rows.append(
            {
                "game_id": f"G{draw(st.integers(min_value=0, max_value=n_games - 1))}",
                "offense_team_id": 1,
                "defense_team_id": 2,
                "offense_lineup": "-".join(str(p) for p in ten[:5]),
                "defense_lineup": "-".join(str(p) for p in ten[5:]),
                "possessions": possessions,
                "points": draw(_point_counts),
            }
        )
    return pd.DataFrame(rows)


_SETTINGS = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


# ------------------------------------------------------------------ five a side


@_SETTINGS
@given(frame=_stint_frames())
def test_every_row_has_five_players_on_each_side(frame: pd.DataFrame) -> None:
    design = build_design(frame)
    dense = design.matrix.toarray()
    assert set((dense == 1.0).sum(axis=1)) == {5}
    assert set((dense == -1.0).sum(axis=1)) == {5}


@_SETTINGS
@given(frame=_stint_frames())
def test_no_player_appears_on_both_sides_of_one_row(frame: pd.DataFrame) -> None:
    # A player cannot guard himself. If he could, his offensive and defensive
    # columns would cancel and his rating would be unidentifiable.
    design = build_design(frame)
    dense = design.matrix.toarray()
    offence = dense[:, : design.n_players] == 1.0
    defence = dense[:, design.n_players :] == -1.0
    assert not (offence & defence).any()


# ------------------------------------------------------------ reconciliation


@_SETTINGS
@given(frame=_stint_frames())
def test_possessions_are_neither_created_nor_lost(frame: pd.DataFrame) -> None:
    design = build_design(frame)
    assert design.weights.sum() == frame["possessions"].sum()


@_SETTINGS
@given(frame=_stint_frames())
def test_points_survive_the_round_trip_through_the_target(frame: pd.DataFrame) -> None:
    # The design stores a rate, not a count, so the count has to be recoverable
    # from the rate and the weight or evidence has been lost.
    design = build_design(frame)
    recovered = design.target * design.weights / 100.0
    assert np.allclose(recovered.sum(), frame["points"].sum())


# ------------------------------------------------------------ order invariance


@_SETTINGS
@given(frame=_stint_frames(min_rows=4), seed=st.integers(min_value=0, max_value=10_000))
def test_ratings_do_not_depend_on_the_order_of_the_rows(frame: pd.DataFrame, seed: int) -> None:
    shuffled = frame.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    original = fit_ridge(build_design(frame), 500.0).ratings().set_index("player_id")
    reordered = fit_ridge(build_design(shuffled), 500.0).ratings().set_index("player_id")

    aligned = reordered.reindex(original.index)
    assert np.allclose(original["total"], aligned["total"], atol=1e-6)


@_SETTINGS
@given(frame=_stint_frames(min_rows=4))
def test_ratings_do_not_depend_on_how_players_are_numbered(frame: pd.DataFrame) -> None:
    # Relabelling every player must permute the ratings and change nothing
    # else. A dependence here would mean a column index leaked into the maths.
    offset = 1000

    def relabel(lineup: str) -> str:
        return "-".join(str(int(p) + offset) for p in lineup.split("-"))

    renamed = frame.copy()
    renamed["offense_lineup"] = renamed["offense_lineup"].map(relabel)
    renamed["defense_lineup"] = renamed["defense_lineup"].map(relabel)

    original = fit_ridge(build_design(frame), 500.0).ratings()
    shifted = fit_ridge(build_design(renamed), 500.0).ratings()

    assert np.allclose(
        original.sort_values("player_id")["total"].to_numpy(),
        shifted.sort_values("player_id")["total"].to_numpy(),
        atol=1e-6,
    )


@_SETTINGS
@given(frame=_stint_frames(min_rows=4))
def test_the_players_in_the_frame_are_exactly_the_players_rated(frame: pd.DataFrame) -> None:
    design = build_design(frame)
    named = {
        int(player)
        for column in ("offense_lineup", "defense_lineup")
        for lineup in frame[column]
        for player in lineup.split("-")
    }
    assert set(design.player_ids) == named
    assert len(fit_ridge(design, 500.0).ratings()) == len(named)
