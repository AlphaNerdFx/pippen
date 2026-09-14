"""Retrieval of play-by-play with on-court lineups, for RAPM.

Why this module exists at all
-----------------------------
RAPM needs to know which ten players were on the floor for every possession.
The hoopR bulk Parquet this project uses everywhere else is ESPN-sourced and
carries event participants only, with no lineup column, so it cannot answer
that question. Reconstructing lineups means replaying substitution events and
handling the cases where the feed omits them, which is the highest-risk parser
in the project. ``pbpstats`` already solves it, so this project does not
rewrite it.

The seam: pbpstats parses, this module fetches
----------------------------------------------
``pbpstats`` ships its own HTTP loaders, and they are not usable here:

* no rate limiting, while this project is bound to one request per second;
* no validity check before caching, so an empty or error payload is written to
  disk and every later read returns it silently;
* a plain ``open(path, "w")``, which truncates the target before writing, so an
  interrupt mid-write leaves a truncated file that also poisons the cache;
* no ``User-Agent``, which data.nba.com rejects outright with HTTP 403.

Rather than subclass or monkeypatch four loader classes, this module downloads
into the directory layout ``pbpstats`` expects and then runs it with
``{"source": "file"}``. The network side stays here, where rate limiting,
retries, atomic writes and payload validation already exist in the same shapes
as :mod:`pippen.data.hoopr`. ``pbpstats`` does only the job it was chosen for.

Which upstream feed, and why
----------------------------
Three routes to lineup-bearing play-by-play were measured on 2026-09-15:

======================  ==========================  ======================
Route                   Seasons returning data      pbpstats support
======================  ==========================  ======================
``playbyplayv2``        none                        native, and broken
``data.nba.com``        2016 through 2024           native, needs a UA
``playbyplayv3``        2015 through 2025           none, needs an adapter
======================  ==========================  ======================

``playbyplayv2`` is what ``pbpstats`` calls. It now answers HTTP 200 with the
two-byte body ``{}`` for every game of every season, so the whole
``stats_nba`` path is dead. ``playbyplayv3`` is alive but drops the numeric
``EVENTMSGTYPE``/``EVENTMSGACTIONTYPE`` codes and carries a single ``personId``
per action, so a substitution no longer names the outgoing and incoming player
in one event. Adapting it means reimplementing the substitution tracking that
``pbpstats`` was chosen to supply, so it is deliberately not done here.

That leaves data.nba.com, which covers 2016 through 2024. 2015 is not served
(HTTP 403) and 2025 onward returns a stub with an empty period array, so the
feed has stopped being populated. :data:`FIRST_SEASON` and :data:`LAST_SEASON`
record that range, and the covered span is nine seasons rather than the ten
originally planned.

The User-Agent finding
----------------------
data.nba.com returns HTTP 403 when the ``User-Agent`` is absent, and also when
it contains a URL. ``Mozilla/5.0 (Windows NT 10.0; Win64; x64) pippen/0.0.0``
is accepted while the same string with ``(+https://github.com/...)`` appended
is refused. The default below therefore keeps a browser-shaped prefix, which
the filter requires, followed by this package's own name and version, so the
traffic stays identifiable. Override it with :data:`USER_AGENT_ENV_VAR`.

One request per game
--------------------
``pbpstats`` can build possessions from the play-by-play file alone; the
box score file is optional. Reconstructed lineups were compared with and
without it on game ``0022300001`` and were identical across all 484 events, so
this module fetches play-by-play only. That halves the traffic, and the
accuracy the box score would have guarded is instead checked against the hoopR
box scores already on disk, which costs no requests and covers every game
rather than the ones someone thought to spot-check.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from pippen import __version__
from pippen.data.nba_api import RateLimiter, default_limiter
from pippen.paths import stage_dir

_SCHEDULE_URL: Final = "https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{season}/league/00_full_schedule.json"
_PBP_URL: Final = "https://data.nba.com/data/v2015/json/mobile_teams/nba/{season}/scores/pbp/{game_id}_full_pbp.json"

#: Earliest season data.nba.com serves. 2015 answers HTTP 403.
FIRST_SEASON: Final = 2016
#: Latest season data.nba.com serves. 2025 onward returns an empty stub.
LAST_SEASON: Final = 2024

#: Subdirectories ``pbpstats`` expects beneath its cache root.
CACHE_SUBDIRS: Final = ("schedule", "pbp", "game_details", "overrides")

#: Prefix marking a regular-season game id. ``001`` is preseason, ``004`` playoffs.
REGULAR_SEASON_PREFIX: Final = "002"

USER_AGENT_ENV_VAR: Final = "PIPPEN_DATA_NBA_USER_AGENT"
_DEFAULT_USER_AGENT_TEMPLATE: Final = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) pippen/{version}"

_DEFAULT_TIMEOUT_SECONDS: Final = 30.0
_MAX_ATTEMPTS: Final = 4
_BACKOFF_INITIAL_SECONDS: Final = 1.0
_BACKOFF_MAX_SECONDS: Final = 20.0


class TransientDownloadError(Exception):
    """A network failure worth retrying: timeout, connection reset, or 5xx."""


class SeasonNotCoveredError(ValueError):
    """A season outside the range data.nba.com actually serves."""


@dataclass(frozen=True)
class GameDownloadResult:
    """Outcome of fetching one game's play-by-play.

    Attributes:
        game_id: The NBA game id, such as ``0022300001``.
        path: Where the file landed, whether freshly downloaded or already present.
        downloaded: True if a request was made, false if the cache was reused.
        error: ``None`` on success, otherwise a human-readable reason.
    """

    game_id: str
    path: Path
    downloaded: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when the file is on disk and passed its validity check."""
        return self.error is None


def user_agent() -> str:
    """Return the ``User-Agent`` to send to data.nba.com.

    Returns:
        The value of :data:`USER_AGENT_ENV_VAR` if set, otherwise a
        browser-shaped default carrying this package's name and version. See
        the module docstring for why the browser prefix is not optional.
    """
    override = os.environ.get(USER_AGENT_ENV_VAR)
    return override if override else _DEFAULT_USER_AGENT_TEMPLATE.format(version=__version__)


def cache_root(*, create: bool = False) -> Path:
    """Return the directory ``pbpstats`` reads from, creating the layout on request.

    Args:
        create: When true, create the root and every subdirectory
            :data:`CACHE_SUBDIRS` names. ``pbpstats`` writes into these
            without creating them, and this project's own downloads need them
            to exist before the first atomic write.

    Returns:
        The resolved cache root, ``<data root>/raw/pbpstats``.
    """
    root = stage_dir("raw", create=create) / "pbpstats"
    if create:
        for name in CACHE_SUBDIRS:
            (root / name).mkdir(parents=True, exist_ok=True)
    return root


def schedule_path(season: int) -> Path:
    """Return the cache path for one season's schedule, in ``pbpstats`` naming."""
    return cache_root() / "schedule" / f"data_nba_{season}.json"


def game_path(game_id: str) -> Path:
    """Return the cache path for one game's play-by-play, in ``pbpstats`` naming."""
    return cache_root() / "pbp" / f"data_{game_id}.json"


def check_season(season: int) -> None:
    """Raise if ``season`` falls outside the range data.nba.com serves.

    Args:
        season: Season start year, so 2023 means the 2023-24 season.

    Raises:
        SeasonNotCoveredError: If the season is outside
            :data:`FIRST_SEASON` to :data:`LAST_SEASON`. The message names the
            reason rather than only the bound, because the bound is an
            upstream fact rather than a policy of this project.
    """
    if season < FIRST_SEASON:
        raise SeasonNotCoveredError(
            f"season {season} predates data.nba.com play-by-play coverage; "
            f"the earliest served season is {FIRST_SEASON} and {FIRST_SEASON - 1} "
            f"and older answer HTTP 403"
        )
    if season > LAST_SEASON:
        raise SeasonNotCoveredError(
            f"season {season} is past the last season data.nba.com populated; "
            f"{LAST_SEASON} is the most recent, and later seasons return an "
            f"empty period array rather than an error"
        )


def _is_valid_schedule(payload: Any) -> bool:
    """True when a schedule payload carries at least one month of games."""
    return isinstance(payload, dict) and bool(payload.get("lscd"))


def _is_valid_pbp(payload: Any) -> bool:
    """True when a play-by-play payload carries at least one period.

    The check that matters. data.nba.com answers HTTP 200 with
    ``{"g": {..., "pd": []}}`` for seasons it no longer populates, so status
    code alone would cache an empty game as if it were real.
    """
    if not isinstance(payload, dict):
        return False
    game = payload.get("g")
    return isinstance(game, dict) and bool(game.get("pd"))


def _retry_policy() -> Retrying:
    """Return the retry controller for a single download.

    Built fresh on each call rather than baked into a decorator so a test can
    shrink the attempt count without reaching into module state.

    Returns:
        A :class:`tenacity.Retrying` that retries only
        :class:`TransientDownloadError`, backing off exponentially and
        re-raising the final failure rather than swallowing it.
    """
    return Retrying(
        retry=retry_if_exception_type(TransientDownloadError),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=_BACKOFF_INITIAL_SECONDS, max=_BACKOFF_MAX_SECONDS),
        reraise=True,
    )


def build_session() -> requests.Session:
    """Return a session carrying the headers data.nba.com requires.

    Returns:
        A :class:`requests.Session` with :func:`user_agent` applied. Reusing
        one session across a season's downloads keeps the TCP connection and
        TLS handshake alive, which matters over thousands of sequential
        requests.
    """
    session = requests.Session()
    session.headers["User-Agent"] = user_agent()
    return session


def _get_json(session: requests.Session, url: str, *, timeout: float) -> Any:
    """Fetch one URL and decode it, classifying failures as transient or not.

    Args:
        session: Session to issue the request through.
        url: Absolute URL to fetch.
        timeout: Per-request timeout in seconds.

    Returns:
        The decoded JSON payload.

    Raises:
        TransientDownloadError: On a timeout, a connection error, a 5xx reply,
            or a body that does not parse as JSON. A malformed body is treated
            as transient because the usual cause is a truncated response.
        requests.HTTPError: On a 4xx reply, which retrying will not fix.
    """
    try:
        response = session.get(url, timeout=timeout)
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise TransientDownloadError(f"{type(exc).__name__}: {exc}") from exc

    if response.status_code >= 500:
        raise TransientDownloadError(f"HTTP {response.status_code} from {url}")
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise TransientDownloadError(f"response was not valid JSON: {exc}") from exc


def _write_json_atomically(payload: Any, target: Path) -> None:
    """Write ``payload`` to ``target`` so readers never observe a partial file.

    Writes to a temporary file in the same directory, then renames it over the
    target. ``rename(2)`` is atomic within a filesystem, so a reader either
    sees the previous file or the complete new one, never a half-written one.
    The temporary file must share the target's directory for that guarantee to
    hold, since a rename across filesystems is a copy and is not atomic.

    Args:
        payload: JSON-serialisable object to write.
        target: Final path. Its parent directory must already exist.
    """
    file_descriptor, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".part"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def download_schedule(
    season: int,
    *,
    force: bool = False,
    session: requests.Session | None = None,
    limiter: RateLimiter | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Path:
    """Download one season's schedule into the ``pbpstats`` cache.

    Args:
        season: Season start year.
        force: Re-download even when a valid copy is already cached.
        session: Session to reuse. A new one is built when omitted.
        limiter: Rate limiter to pace the request. The process-wide limiter is
            used when omitted.
        timeout: Per-request timeout in seconds.

    Returns:
        Path to the cached schedule file.

    Raises:
        SeasonNotCoveredError: If the season is outside the served range.
        TransientDownloadError: If every retry failed.
        requests.HTTPError: On a 4xx reply.
        ValueError: If the payload arrived but carried no months of games.
    """
    check_season(season)
    cache_root(create=True)
    target = schedule_path(season)
    if target.exists() and not force:
        return target

    owned = session is None
    session = session or build_session()
    limiter = limiter or default_limiter()
    try:
        limiter.wait()
        payload = _retry_policy()(
            _get_json, session, _SCHEDULE_URL.format(season=season), timeout=timeout
        )
    finally:
        if owned:
            session.close()

    if not _is_valid_schedule(payload):
        raise ValueError(f"schedule for {season} arrived with no months of games")
    _write_json_atomically(payload, target)
    return target


def season_game_ids(season: int, *, regular_season_only: bool = True) -> list[str]:
    """Return the game ids for one season, downloading the schedule if needed.

    Args:
        season: Season start year.
        regular_season_only: Keep only ids beginning
            :data:`REGULAR_SEASON_PREFIX`, dropping preseason, All-Star and
            playoff games. RAPM is fitted on the regular season because
            opponent quality is not random in the others.

    Returns:
        Game ids in schedule order.

    Raises:
        SeasonNotCoveredError: If the season is outside the served range.
    """
    path = schedule_path(season)
    if not path.exists():
        download_schedule(season)
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = [
        str(game["gid"])
        for month in payload["lscd"]
        for game in month["mscd"]["g"]
        if "gid" in game
    ]
    if regular_season_only:
        ids = [gid for gid in ids if gid.startswith(REGULAR_SEASON_PREFIX)]
    return ids


def download_game(
    game_id: str,
    season: int,
    *,
    force: bool = False,
    session: requests.Session | None = None,
    limiter: RateLimiter | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> GameDownloadResult:
    """Download one game's play-by-play into the ``pbpstats`` cache.

    A failure is returned rather than raised, so a season-long run reports
    which games are missing instead of stopping at the first bad one.

    Args:
        game_id: NBA game id, such as ``0022300001``.
        season: Season start year, needed to build the URL.
        force: Re-download even when a valid copy is already cached.
        session: Session to reuse across many games.
        limiter: Rate limiter to pace the request.
        timeout: Per-request timeout in seconds.

    Returns:
        A :class:`GameDownloadResult` describing what happened.
    """
    target = game_path(game_id)
    if target.exists() and not force:
        return GameDownloadResult(game_id=game_id, path=target, downloaded=False)

    owned = session is None
    session = session or build_session()
    limiter = limiter or default_limiter()
    try:
        limiter.wait()
        payload = _retry_policy()(
            _get_json,
            session,
            _PBP_URL.format(season=season, game_id=game_id),
            timeout=timeout,
        )
    except (TransientDownloadError, requests.HTTPError) as exc:
        return GameDownloadResult(
            game_id=game_id, path=target, downloaded=False, error=f"download failed: {exc}"
        )
    finally:
        if owned:
            session.close()

    if not _is_valid_pbp(payload):
        return GameDownloadResult(
            game_id=game_id,
            path=target,
            downloaded=False,
            error="payload carried no periods, so the feed has no data for this game",
        )
    _write_json_atomically(payload, target)
    return GameDownloadResult(game_id=game_id, path=target, downloaded=True)


@dataclass(frozen=True)
class SeasonDownloadResult:
    """Outcome of fetching a whole season's play-by-play.

    Attributes:
        season: Season start year.
        requested: How many game ids were considered.
        downloaded: How many games were fetched on this run.
        cached: How many were already present and reused.
        failures: One result per game that could not be fetched.
    """

    season: int
    requested: int
    downloaded: int
    cached: int
    failures: tuple[GameDownloadResult, ...]

    @property
    def ok(self) -> bool:
        """True when every requested game is on disk."""
        return not self.failures

    def summary(self) -> str:
        """Return a one-line description suitable for a log or a CLI."""
        line = (
            f"season {self.season}: {self.requested} games, "
            f"{self.downloaded} downloaded, {self.cached} already present"
        )
        if self.failures:
            line += f", {len(self.failures)} failed"
        return line


def download_season(
    season: int,
    *,
    force: bool = False,
    limit: int | None = None,
    limiter: RateLimiter | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    on_progress: Any = None,
) -> SeasonDownloadResult:
    """Download every regular-season game's play-by-play for one season.

    The loop is bounded by the schedule, which is fetched first, so this
    terminates whether or not individual games succeed. Failures are collected
    and reported at the end rather than aborting the run, because a single
    missing game should not cost the other twelve hundred.

    Args:
        season: Season start year.
        force: Re-download games already cached.
        limit: Stop after this many games. Intended for smoke tests, so a
            caller can prove the path works without spending a full season's
            worth of requests.
        limiter: Rate limiter to pace requests. The process-wide limiter is
            used when omitted, which is what holds the whole run to one
            request per second.
        timeout: Per-request timeout in seconds.
        on_progress: Optional callable invoked with each
            :class:`GameDownloadResult` as it completes, for progress display.

    Returns:
        A :class:`SeasonDownloadResult` counting successes and listing failures.

    Raises:
        SeasonNotCoveredError: If the season is outside the served range.
    """
    check_season(season)
    cache_root(create=True)
    limiter = limiter or default_limiter()
    session = build_session()
    try:
        download_schedule(season, force=force, session=session, limiter=limiter, timeout=timeout)
        game_ids = season_game_ids(season)
        if limit is not None:
            game_ids = game_ids[:limit]

        downloaded = 0
        cached = 0
        failures: list[GameDownloadResult] = []
        for game_id in game_ids:
            result = download_game(
                game_id,
                season,
                force=force,
                session=session,
                limiter=limiter,
                timeout=timeout,
            )
            if not result.ok:
                failures.append(result)
            elif result.downloaded:
                downloaded += 1
            else:
                cached += 1
            if on_progress is not None:
                on_progress(result)
    finally:
        session.close()

    return SeasonDownloadResult(
        season=season,
        requested=len(game_ids),
        downloaded=downloaded,
        cached=cached,
        failures=tuple(failures),
    )
