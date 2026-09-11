"""Measured fraction of free throw attempts that end a possession.

Basketball analytics estimates possessions as ``FGA + 0.44 * FTA + TOV``. The
0.44 is not an arbitrary tuning constant. It estimates the fraction of free
throw *attempts* that consume a possession, because not every free throw ends
one:

* On a two-shot common foul, only the second shot ends the trip.
* On an and-one, the field goal already ended the possession; the free throw
  adds nothing further to count.
* On a three-shot foul, only the third shot ends the trip.
* Technical free throws are awarded on a dead ball with no possession change
  at all; the team that had the ball keeps it.
* Flagrant and clear-path fouls award free throws *and* let the fouled team
  keep the ball afterwards (a throw-in, not a change of possession), win or
  miss the last shot.
* A missed final free throw followed by an offensive rebound does not end the
  possession either; the shooting team just keeps playing.

``docs/methodology/errata.md`` (section 3) records that this project's own
research documents mischaracterised 0.44 as a PER-specific flaw, when the same
constant serves the same purpose in Pace, turnover rate, true shooting and
usage rate. The legitimate version of that complaint is that the true fraction
is empirical and can drift with rule changes. For the 2023-24 season alone the
NBA introduced "transition take foul" and "away from play foul", single-shot
fouls that let the offense keep the ball. This module measures the
coefficient per season from play-by-play instead of assuming a fixed value.

How a free throw is identified
    hoopR's ``type_text`` column carries values like ``"Free Throw - 1 of 2"``,
    ``"Free Throw - Technical"``, ``"Free Throw - Flagrant 2 of 3"`` and
    ``"Free Throw - Clear Path 1 of 2"``. Verified against the real 2023-24
    play-by-play file (614,447 rows): every free throw row's ``type_text``
    starts with ``"Free Throw"``, and every non-technical one ends in a
    ``"<k> of <n>"`` pattern giving its position in the trip and the trip
    size. Only the last shot of a trip (``k == n``) can possibly end a
    possession; every earlier shot in a multi-shot trip is attempted with the
    trip guaranteed to continue regardless of make or miss.

What this module cannot determine
    A missed final free throw is followed, almost always, directly by a
    ``"Defensive Rebound"`` or ``"Offensive Rebound"`` event, and hoopR's own
    rebound labels are already possession-relative (an "offensive" rebound is
    taken by the team that just shot, whichever team that is), so the labels
    alone settle the question without needing to compare team identifiers.
    A substitution is sometimes logged between the miss and the rebound, so
    the lookahead skips up to :data:`_MAX_LOOKAHEAD` consecutive substitution
    rows before giving up. Verified on the real 2023-24 file: this resolves
    all but 5 of 57,076 free throw attempts (0.009%). Each of those five is a
    missed final free throw followed immediately by another shot with no
    rebound row logged between them. The shooting team plainly kept the ball,
    but no rebound label says so, and inferring one from the shooter's team
    would be a guess rather than a reading. Rather than guess, those attempts
    are excluded from both the numerator and the denominator and reported
    separately as :attr:`SeasonPossessionCoefficient.excluded_unresolved`, so
    a wrong assumption never gets dressed up as a measurement.

Why this is vectorised rather than a per-row loop
    A single season's play-by-play is hundreds of thousands of rows (614,447
    for 2023-24 alone). Everything below operates on whole columns with
    pandas string, comparison and ``groupby().shift()`` operations, which run
    as compiled loops inside pandas/NumPy. A Python ``for`` loop over rows
    would still finish, but 25 seasons of it is the difference between a
    command that returns and one nobody waits for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Mapping

# The conventional constant this module measures against. See
# docs/methodology/errata.md, section 3.
CONVENTIONAL_COEFFICIENT: Final[float] = 0.44

# Every free throw's type_text ends in "<k> of <n>" except technical free
# throws, which have no trip position at all (a technical is never part of a
# multi-shot trip). Anchored at the end of the string since "Free Throw -
# Flagrant 1 of 2" and "Free Throw - Clear Path 1 of 2" carry extra words
# before the position.
_TRIP_POSITION: Final = re.compile(r"(\d+) of (\d+)$")

# How far to look past a missed final free throw for the rebound that settles
# it. Substitutions are the common filler, but fouls, jump balls, timeouts and
# replay reviews all appear too, and runs of three consecutive substitutions
# are routine late in a game. Four steps covers every case observed in the
# real 2023-24 file. This is a small, fixed number of vectorised shift
# operations, not an unbounded loop.
_MAX_LOOKAHEAD: Final = 4

_REQUIRED_COLUMNS: Final = (
    "game_id",
    "game_play_number",
    "type_text",
    "scoring_play",
    "shooting_play",
)


@dataclass(frozen=True)
class SeasonPossessionCoefficient:
    """The measured possession coefficient for one season.

    Attributes:
        season: Season end year, e.g. 2024 for the 2023-24 season.
        coefficient: Possession-ending trips divided by free throw attempts,
            restricted to attempts whose outcome could be determined. ``nan``
            if no attempt in the season could be classified.
        diff_from_conventional: ``coefficient - CONVENTIONAL_COEFFICIENT``.
            Positive means this season's free throws ended possessions more
            often than the conventional constant assumes.
        possession_ending_trips: Numerator, the count of free throw trips
            whose last shot ended the shooting team's possession.
        free_throw_attempts: Denominator, the count of free throw attempts
            whose outcome could be classified. Every attempt in a resolved
            trip counts, not just the last one, matching how ``FTA`` is
            counted in the conventional formula.
        total_free_throw_attempts: All free throw attempts seen, including
            the ones excluded as unresolved. Reported so a reader can see how
            much of the season's free throws the coefficient is actually
            built from.
        excluded_unresolved: Free throw attempts excluded from both the
            numerator and the denominator because a missed final free throw
            was not followed, within :data:`_MAX_LOOKAHEAD` events, by a
            clearly labelled rebound. See the module docstring.
    """

    season: int
    coefficient: float
    diff_from_conventional: float
    possession_ending_trips: int
    free_throw_attempts: int
    total_free_throw_attempts: int
    excluded_unresolved: int


def _require_columns(play_by_play: pd.DataFrame) -> None:
    """Raise a clear error if a required column is missing.

    Args:
        play_by_play: The frame to check.

    Raises:
        ValueError: If any of :data:`_REQUIRED_COLUMNS` is absent. A missing
            column would otherwise surface as a cryptic ``KeyError`` deep
            inside the classification logic below.
    """
    missing = [column for column in _REQUIRED_COLUMNS if column not in play_by_play.columns]
    if missing:
        raise ValueError(f"play_by_play is missing required column(s): {', '.join(missing)}")


def _classify_free_throws(play_by_play: pd.DataFrame) -> pd.DataFrame:
    """Classify every free throw row as ending a possession, or not.

    Every design decision from the module docstring lives here. The result
    has one row per input row (in chronological order), with three added
    boolean-ish columns: ``is_free_throw``, ``is_last_of_trip`` and
    ``ends_possession`` (nullable: ``pd.NA`` where the outcome could not be
    determined, and meaningless where ``is_last_of_trip`` is false, since only
    the last shot of a trip can end a possession).

    Args:
        play_by_play: Play-by-play rows for one or more games. Must carry
            ``game_id``, ``game_play_number``, ``type_text`` and
            ``scoring_play``.

    Returns:
        A copy of ``play_by_play``, sorted into chronological order within
        each game, with the classification columns added.

    Raises:
        ValueError: If a free throw's ``type_text`` is neither a technical
            free throw nor parseable as a "<k> of <n>" trip position. This
            would mean hoopR introduced a free throw label this module does
            not know about, and guessing at its meaning is exactly what this
            module exists to avoid. See the module docstring.
    """
    _require_columns(play_by_play)

    # game_play_number is hoopR's own within-game chronological sequence.
    # Sorting on it explicitly, rather than trusting the caller's row order,
    # means the lookahead below is only ever wrong if hoopR's own numbering
    # is, not if a caller handed rows in a different order.
    df = play_by_play.sort_values(["game_id", "game_play_number"], kind="stable").reset_index(
        drop=True
    )
    type_text = df["type_text"].fillna("")

    is_free_throw = type_text.str.startswith("Free Throw", na=False)
    is_technical = is_free_throw & type_text.str.contains("Technical", na=False)
    # Flagrant and clear-path fouls both award free throws to the fouled team
    # *and* let that team keep the ball afterwards (a throw-in), regardless
    # of whether the last free throw is made or missed. Neither ends a
    # possession, so both are excluded from the numerator the same way.
    retains_ball = is_free_throw & (
        type_text.str.contains("Flagrant", na=False)
        | type_text.str.contains("Clear Path", na=False)
    )

    position_size = type_text.str.extract(_TRIP_POSITION)
    position = pd.to_numeric(position_size[0], errors="coerce")
    trip_size = pd.to_numeric(position_size[1], errors="coerce")
    has_trip_position = position.notna() & trip_size.notna()

    unrecognised = is_free_throw & ~is_technical & ~has_trip_position
    if unrecognised.any():
        examples = sorted(type_text.loc[unrecognised].unique())[:5]
        raise ValueError(
            "found free throw type_text value(s) this module does not know how to "
            f"classify (neither technical nor a parseable trip position): {examples}"
        )

    is_last_of_trip = is_free_throw & (is_technical | (has_trip_position & (position == trip_size)))
    # A trip of size 1 that is not flagrant is, in NBA rules, either an
    # and-one (a shooting foul on a made basket, where the field goal already
    # ended the possession and is already counted via FGA) or a take foul /
    # away-from-play foul (rules added for 2023-24, which award one free
    # throw and let the offense keep the ball). Both leave the offense's
    # possession unended by the free throw itself, so both are excluded from
    # the numerator the same way, deliberately without telling them apart.
    # Distinguishing them would mean pattern-matching specific foul-type
    # strings that are themselves a rule-era artifact, which is the exact
    # fragility this per-season measurement exists to route around.
    is_one_shot_trip = (
        is_free_throw & has_trip_position & (trip_size == 1) & ~is_technical & ~retains_ball
    )

    made = df["scoring_play"].fillna(False).astype(bool)

    # Only a missed last shot of an ordinary (non-technical, non-retained,
    # multi-shot) trip has an outcome that depends on what happens next.
    plain_last = is_last_of_trip & ~is_technical & ~retains_ball & ~is_one_shot_trip
    missed_plain_last = plain_last & ~made

    ends_possession = pd.Series(pd.NA, index=df.index, dtype="boolean")
    # Technical, flagrant and clear-path trips, and one-shot trips, never end
    # the shooting team's possession. See the reasoning above and in the
    # module docstring.
    ends_possession = ends_possession.mask(is_last_of_trip & is_technical, False)
    ends_possession = ends_possession.mask(is_last_of_trip & retains_ball, False)
    ends_possession = ends_possession.mask(is_last_of_trip & is_one_shot_trip, False)
    # An ordinary trip's last shot, if made, ends the possession: the ball
    # goes to the opponent to inbound.
    ends_possession = ends_possession.mask(plain_last & made, True)

    # If missed, hoopR's rebound label already says who kept the ball, and its
    # labels are already possession-relative: an "offensive" rebound is taken
    # by whichever team just shot, so no team-identifier comparison is
    # needed. The candidate is committed to `ends_possession` only when it is
    # actually one of the two rebound labels; a non-rebound, non-substitution
    # candidate (the common case: play just continues) is left alone so a
    # later step never overwrites an already-settled row, and a row that
    # still has no answer keeps `still_unresolved` true so the next step gets
    # a chance to look further past a substitution.
    by_game = df.groupby("game_id")
    # Scan forward for the rebound that settles this free throw. Two rules
    # decide when to stop, and both come from a structured column rather than
    # a list of event names that would have to be guessed and maintained.
    #
    # Resolve at the first rebound label. `Defensive Rebound` and
    # `Offensive Rebound` are already possession-relative, so no team
    # comparison is needed.
    #
    # Abandon at the first shot attempt, because a rebound found after a new
    # shot belongs to that shot and not to this free throw. `shooting_play` is
    # true for every shot type and false for every rebound, substitution,
    # timeout, foul, jump ball and replay review, so it separates the two
    # cases exactly.
    #
    # Everything else is skipped rather than treated as a wall. An earlier
    # version only skipped substitutions and latched shut on anything else, so
    # a foul call or a coach's challenge sitting one event before a perfectly
    # clear rebound label made the whole trip unresolvable. That excluded 29
    # attempts from the 2023-24 season, and they were not random: six were
    # coach's challenges and seven were runs of three substitutions.
    still_unresolved = missed_plain_last.copy()
    search_open = pd.Series(True, index=df.index)
    for step in range(1, _MAX_LOOKAHEAD + 1):
        candidate = by_game["type_text"].shift(-step)
        # eq(True) rather than fillna(False).astype(bool): a shift past the end
        # of a game yields NA, and eq treats that as False without triggering
        # pandas' object-dtype downcasting, which is deprecated.
        candidate_is_shot = by_game["shooting_play"].shift(-step).eq(True)
        can_resolve_here = still_unresolved & search_open

        ends_possession = ends_possession.mask(
            can_resolve_here & (candidate == "Defensive Rebound"), True
        )
        ends_possession = ends_possession.mask(
            can_resolve_here & (candidate == "Offensive Rebound"), False
        )
        still_unresolved &= ends_possession.isna()
        # A new shot ends the search for good. Anything else is stepped over.
        search_open &= ~candidate_is_shot
    # Anything still pd.NA here (missed_plain_last with no rebound label found
    # within the lookahead) is unresolved: excluded rather than guessed.

    result = df.copy()
    result["is_free_throw"] = is_free_throw
    result["is_last_of_trip"] = is_last_of_trip
    result["ends_possession"] = ends_possession
    return result


def estimate_season_coefficient(
    play_by_play: pd.DataFrame, season: int
) -> SeasonPossessionCoefficient:
    """Estimate the possession coefficient for one season.

    Args:
        play_by_play: One season's play-by-play rows. Must carry ``game_id``,
            ``game_play_number``, ``type_text`` and ``scoring_play`` (all
            present in hoopR's published play-by-play). Extra columns are
            ignored.
        season: Season end year, e.g. 2024 for the 2023-24 season. Used only
            to label the result; not cross-checked against the frame's own
            ``season`` column, since that check belongs to
            :mod:`pippen.data.validate`, not here.

    Returns:
        The measured coefficient and the counts it was computed from. If the
        season has no classifiable free throw attempts at all, ``coefficient``
        and ``diff_from_conventional`` are ``nan`` rather than raising, since
        an empty season is a legitimate (if useless) input.
    """
    classified = _classify_free_throws(play_by_play)

    is_free_throw = classified["is_free_throw"]
    is_last_of_trip = classified["is_last_of_trip"]
    ends_possession = classified["ends_possession"]

    total_attempts = int(is_free_throw.sum())
    unresolved_attempts = int((is_last_of_trip & ends_possession.isna()).sum())
    used_attempts = total_attempts - unresolved_attempts
    possession_ending_trips = int(ends_possession.loc[is_last_of_trip].fillna(False).sum())

    coefficient = possession_ending_trips / used_attempts if used_attempts else float("nan")

    return SeasonPossessionCoefficient(
        season=season,
        coefficient=coefficient,
        diff_from_conventional=coefficient - CONVENTIONAL_COEFFICIENT,
        possession_ending_trips=possession_ending_trips,
        free_throw_attempts=used_attempts,
        total_free_throw_attempts=total_attempts,
        excluded_unresolved=unresolved_attempts,
    )


def estimate_coefficients_by_season(seasons: Mapping[int, pd.DataFrame]) -> pd.DataFrame:
    """Estimate the possession coefficient across several seasons.

    Args:
        seasons: Play-by-play frames keyed by season end year, e.g.
            ``{2024: play_by_play_2024}``. Each frame is passed to
            :func:`estimate_season_coefficient` unchanged.

    Returns:
        One row per season, sorted by season ascending, with columns
        ``season``, ``coefficient``, ``diff_from_conventional``,
        ``possession_ending_trips``, ``free_throw_attempts``,
        ``total_free_throw_attempts`` and ``excluded_unresolved``, the same
        fields as :class:`SeasonPossessionCoefficient`, so a reader can see
        the sample size behind every coefficient rather than just the number.
        Empty (zero rows, with those columns) if ``seasons`` is empty.
    """
    results = [
        estimate_season_coefficient(play_by_play, season)
        for season, play_by_play in sorted(seasons.items())
    ]
    columns = [
        "season",
        "coefficient",
        "diff_from_conventional",
        "possession_ending_trips",
        "free_throw_attempts",
        "total_free_throw_attempts",
        "excluded_unresolved",
    ]
    if not results:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([vars(result) for result in results], columns=columns)
