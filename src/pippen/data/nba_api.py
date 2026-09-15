"""Rate-limited, retrying client for the NBA stats endpoints at stats.nba.com.

stats.nba.com is undocumented and reverse-engineered; it rate limits aggressively
and, when pushed too hard, degrades rather than failing cleanly. This module is
the one place in the pipeline allowed to talk to it, and it exists to make two
guarantees to every caller: no more than one request per second leaves this
process, and a transient failure is retried a bounded number of times instead
of either giving up on the first hiccup or hammering the endpoint forever.

Verified against ``nba_api`` 1.11.4 (the version pinned by this project's
``sources`` extra), two things worth recording because they are easy to get
wrong from the package's public documentation alone:

Status codes are invisible by default
    ``nba_api``'s HTTP layer (``nba_api.stats.library.http.NBAStatsHTTP.
    send_api_request``) never calls ``response.raise_for_status()``, and the
    status code it does capture has no public getter anywhere in the package.
    A 429 does not raise; it is stored, then the endpoint tries to parse the
    rate-limit page as the expected JSON result set and fails confusingly
    several calls later. :func:`_prepare_stats_session` fixes this by
    attaching a ``requests`` response hook to the session ``nba_api`` already
    shares across every endpoint call, so a non-2xx response raises
    ``requests.HTTPError`` at the moment it arrives, exactly where this
    module's retry logic expects it.

Passing ``headers=`` replaces nba_api's defaults, it does not merge with them
    Every endpoint constructor does ``if headers is not None: self.headers =
    headers``, a plain assignment. ``nba_api``'s own default headers
    (``STATS_HEADERS``) carry more than a User-Agent: Host, Accept, Referer
    and others that stats.nba.com also checks. Sending a bare
    ``{"User-Agent": ...}`` mapping would silently drop the rest and likely
    reproduce the exact stall a custom User-Agent is meant to avoid.
    :func:`_default_headers` starts from ``STATS_HEADERS`` and overrides only
    the one key this project needs to control.

Compliance
    NBA API calls stay at one request per second (see ``CLAUDE.md``). This is
    not a suggestion: pushing past it risks the endpoint being blocked for
    every user of this package, not only this one process.
"""

from __future__ import annotations

import os
import threading
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final, Protocol

import pandas as pd
import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from pippen import __version__
from pippen.errors import MissingDependencyError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

RATE_LIMIT_ENV_VAR: Final = "NBA_API_RATE_LIMIT_SECONDS"
USER_AGENT_ENV_VAR: Final = "PIPPEN_USER_AGENT"

DEFAULT_RATE_LIMIT_SECONDS: Final = 1.0
_DEFAULT_TIMEOUT_SECONDS: Final = 30.0
_DEFAULT_USER_AGENT_TEMPLATE: Final = "pippen/{version} (+https://github.com/AlphaNerdFx/pippen)"

HTTP_TOO_MANY_REQUESTS: Final = 429

# Retry policy for transient failures. Read fresh on every call (see
# `_retry_policy`) rather than baked into a decorator, so a test can shrink
# these and see the effect immediately instead of sleeping through real
# exponential delays.
_MAX_ATTEMPTS: Final = 5
_BACKOFF_INITIAL_SECONDS: Final = 1.0
_BACKOFF_MAX_SECONDS: Final = 30.0

_MISSING_DEPENDENCY_MESSAGE: Final = (
    "nba_api is not installed. Install it with the 'sources' extra: "
    "run `uv sync --extra sources` in a checkout, or `pip install 'pippen[sources]'` "
    "for an installed copy."
)


class RateLimitedError(Exception):
    """stats.nba.com answered with HTTP 429: too many requests.

    Worth a bounded retry with backoff. Repeated 429s after the retry budget
    is exhausted mean the configured rate limit is still too aggressive for
    the current traffic, not that this one call was unlucky.
    """


class TransientAPIError(Exception):
    """A network failure worth retrying: timeout, connection reset, or 5xx.

    Anything else, a 4xx other than 429, a malformed URL, is treated as
    permanent for the attempt and is not retried: retrying an unchanged
    request will not fix a request that was wrong to begin with.
    """


class _StatsEndpoint(Protocol):
    """Structural shape every ``nba_api`` stats endpoint instance satisfies.

    Every endpoint under ``nba_api.stats.endpoints`` builds and sends its
    request from inside ``__init__`` and exposes the parsed result through
    ``get_data_frames``. Naming that shape here lets :func:`call_endpoint` be
    typed against "any nba_api endpoint class" without importing ``nba_api``
    at module level.
    """

    def get_data_frames(self) -> list[pd.DataFrame]: ...


class RateLimiter:
    """Enforces a minimum wall-clock interval between the calls it guards.

    Thread safety
        A single ``threading.Lock`` serialises the whole read-decide-sleep
        sequence in :meth:`wait`, and the lock is held for the sleep itself,
        not released around it. Without that, two threads racing to enter
        :meth:`wait` could each read the same "last call was N seconds ago"
        timestamp, each independently decide no wait is needed, and both
        proceed immediately, exactly the double-request this class exists to
        prevent (a classic check-then-act race). Holding the lock across the
        full sequence, including the sleep, makes it atomic: only one thread
        at a time can be inside :meth:`wait`, so calls through this limiter
        are paced at the configured interval regardless of how many threads
        share it. The cost is that a blocked thread waits on the lock for the
        remainder of another thread's sleep rather than doing useful work,
        which is the correct trade for a limiter whose entire job is to make
        callers wait.
    """

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create a rate limiter.

        Args:
            min_interval_seconds: Minimum time that must elapse between the
                start of one call and the start of the next.
            clock: Source of the current time. Defaults to
                :func:`time.monotonic`, which cannot go backwards under a
                system clock adjustment. Overridable so tests can inject a
                fake clock instead of sleeping in real time.
            sleep: Function used to wait out the remaining interval. Defaults
                to :func:`time.sleep`. Overridable for the same reason as
                ``clock``.

        Raises:
            ValueError: If ``min_interval_seconds`` is negative.
        """
        if min_interval_seconds < 0:
            raise ValueError(f"min_interval_seconds must be >= 0, got {min_interval_seconds!r}")
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_call: float | None = None

    def wait(self) -> None:
        """Block, if needed, until the minimum interval has elapsed since the last call.

        The first call never waits. Every call after that blocks for whatever
        is left of ``min_interval_seconds`` since the previous call returned.
        """
        with self._lock:
            now = self._clock()
            if self._last_call is not None:
                remaining = self._min_interval - (now - self._last_call)
                if remaining > 0:
                    self._sleep(remaining)
                    now = self._clock()
            self._last_call = now


@lru_cache(maxsize=1)
def default_limiter() -> RateLimiter:
    """Return the process-wide rate limiter shared by calls that don't pass their own.

    Built once, on first use, and cached: a rate limiter only works if its
    state (the last call time) persists across calls, so unlike this module's
    other lazily-rebuilt policies it cannot be reconstructed fresh each time.
    The environment is read once, at that first use; changing
    ``NBA_API_RATE_LIMIT_SECONDS`` afterwards has no effect on this process.
    A caller that needs a different interval mid-process should build and
    pass its own :class:`RateLimiter` rather than rely on this one.

    Returns:
        A :class:`RateLimiter` configured from :data:`RATE_LIMIT_ENV_VAR`,
        defaulting to :data:`DEFAULT_RATE_LIMIT_SECONDS`.

    Raises:
        ValueError: If :data:`RATE_LIMIT_ENV_VAR` is set to something that
            does not parse as a number.
    """
    return RateLimiter(_rate_limit_seconds())


def _rate_limit_seconds() -> float:
    """Read the configured minimum request interval from the environment.

    Returns:
        The value of :data:`RATE_LIMIT_ENV_VAR`, or
        :data:`DEFAULT_RATE_LIMIT_SECONDS` if it is unset.

    Raises:
        ValueError: If the environment variable is set but not a valid float.
    """
    raw = os.environ.get(RATE_LIMIT_ENV_VAR)
    if raw is None:
        return DEFAULT_RATE_LIMIT_SECONDS
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"{RATE_LIMIT_ENV_VAR}={raw!r} is not a number. "
            "Set it to a decimal number of seconds, for example 1.0."
        ) from exc


def _user_agent() -> str:
    """Return the User-Agent string to send with every stats.nba.com request.

    Returns:
        The value of :data:`USER_AGENT_ENV_VAR` if set, otherwise a
        self-identifying default built from this package's version.
    """
    override = os.environ.get(USER_AGENT_ENV_VAR)
    return override if override else _DEFAULT_USER_AGENT_TEMPLATE.format(version=__version__)


def _merge_user_agent(base_headers: Mapping[str, str]) -> dict[str, str]:
    """Copy ``base_headers``, overriding only the ``User-Agent`` key.

    Split out from :func:`_default_headers` so the merge itself, the part
    worth getting right, can be unit-tested without needing ``nba_api``
    installed to supply the base mapping.

    Args:
        base_headers: Header mapping to start from, typically ``nba_api``'s
            own defaults. That is why this overrides one key instead of
            replacing the mapping outright: the other keys matter too.

    Returns:
        A new dict equal to ``base_headers`` except for ``User-Agent``.
    """
    merged = dict(base_headers)
    merged["User-Agent"] = _user_agent()
    return merged


def _default_headers() -> dict[str, str]:
    """Build the header mapping for a real stats.nba.com request.

    Starts from ``nba_api``'s own default headers rather than a bare
    User-Agent mapping; see the module docstring for why sending only
    ``{"User-Agent": ...}`` would drop headers stats.nba.com also checks.

    Returns:
        A copy of ``nba_api``'s default headers with ``User-Agent``
        overridden to this project's configured value.

    Raises:
        MissingDependencyError: If ``nba_api`` is not installed.
    """
    try:
        from nba_api.stats.library.http import STATS_HEADERS
    except ImportError as exc:
        raise MissingDependencyError(_MISSING_DEPENDENCY_MESSAGE) from exc
    return _merge_user_agent(STATS_HEADERS)


_session_setup_lock = threading.Lock()


def _raise_for_status_hook(response: Any, *args: Any, **kwargs: Any) -> None:
    """``requests`` response hook: turn a non-2xx reply into ``HTTPError`` immediately.

    Args:
        response: The ``requests.Response`` just received.
        *args: Unused. ``requests`` calls response hooks with extra
            positional arguments that this hook does not need.
        **kwargs: Unused, for the same reason as ``*args``.

    Raises:
        requests.HTTPError: If the response status is 4xx or 5xx.
    """
    response.raise_for_status()


def _prepare_stats_session() -> None:
    """Install the status-code-detection hook on nba_api's shared HTTP session.

    ``nba_api`` caches one ``requests.Session`` per HTTP client class and
    reuses it for every endpoint call, so installing the hook once here makes
    it apply everywhere this module calls through ``nba_api``. Safe to call
    on every attempt: the hook is only appended if it is not already present.

    Does nothing if ``nba_api`` is not installed. The endpoint construction
    that follows raises :class:`MissingDependencyError` in that case, which
    is the clearer place for that message to come from.
    """
    try:
        from nba_api.stats.library.http import NBAStatsHTTP
    except ImportError:
        return
    with _session_setup_lock:
        hooks = NBAStatsHTTP.get_session().hooks.setdefault("response", [])
        if _raise_for_status_hook not in hooks:
            hooks.append(_raise_for_status_hook)


def _retry_policy() -> Retrying:
    """Build the bounded exponential-backoff policy used for every endpoint call.

    Built fresh on each use, rather than fixed into a decorator at import
    time, so :data:`_MAX_ATTEMPTS` and the backoff constants can be shrunk in
    tests and take effect immediately.

    Returns:
        A :class:`tenacity.Retrying` controller: it retries only
        :class:`RateLimitedError` and :class:`TransientAPIError`, waits with
        exponential backoff capped at :data:`_BACKOFF_MAX_SECONDS`, gives up
        after :data:`_MAX_ATTEMPTS` attempts, and re-raises the last error
        rather than wrapping it, so a caller catching either exception still
        sees a bounded, terminating call.
    """
    return Retrying(
        retry=retry_if_exception_type((RateLimitedError, TransientAPIError)),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=_BACKOFF_INITIAL_SECONDS, max=_BACKOFF_MAX_SECONDS),
        reraise=True,
    )


def call_endpoint(
    endpoint_cls: Callable[..., _StatsEndpoint],
    *,
    limiter: RateLimiter | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    result_set: int = 0,
    **params: Any,
) -> pd.DataFrame:
    """Call one ``nba_api`` stats endpoint, throttled and retried, as a DataFrame.

    This is the one path every wrapper in this module (and, later, every
    endpoint this pipeline adds) should call through. It does not know
    anything about a specific endpoint's parameters; it only guarantees the
    call is paced by ``limiter`` and retried with bounded backoff on a 429 or
    a transient connection failure.

    Args:
        endpoint_cls: An ``nba_api`` stats endpoint class, for example
            ``nba_api.stats.endpoints.commonallplayers.CommonAllPlayers``.
            Constructing it with ``params`` issues the request; this
            function does not call it, ``nba_api``'s own constructors do.
        limiter: Rate limiter to pace this call through. Defaults to
            :func:`default_limiter`, the process-wide shared limiter.
        headers: HTTP headers to send. Defaults to :func:`_default_headers`,
            which requires ``nba_api`` to be installed; pass an explicit
            mapping (even an empty one) to avoid that requirement, which is
            how this module's own tests exercise this function with a fake
            endpoint class and no ``nba_api`` installed at all.
        timeout: Per-request timeout in seconds, passed through to the
            endpoint constructor.
        result_set: Index into the list ``get_data_frames()`` returns. Most
            stats.nba.com endpoints return exactly one meaningful table, at
            index 0; a few (for example ``boxscoretraditionalv3``) return
            several, and the caller must say which one it wants.
        **params: Endpoint-specific request parameters, forwarded to
            ``endpoint_cls`` unchanged, for example ``season="2024-25"``.

    Returns:
        The requested result set as a pandas DataFrame.

    Raises:
        MissingDependencyError: If ``headers`` is omitted and ``nba_api`` is
            not installed.
        RateLimitedError: If every retry attempt still comes back HTTP 429.
        TransientAPIError: If every retry attempt hits a connection failure,
            timeout, or 5xx response.
    """
    active_limiter = limiter if limiter is not None else default_limiter()
    request_headers: dict[str, str] = dict(headers) if headers is not None else _default_headers()

    def _once() -> pd.DataFrame:
        active_limiter.wait()
        _prepare_stats_session()
        try:
            instance = endpoint_cls(headers=request_headers, timeout=timeout, **params)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == HTTP_TOO_MANY_REQUESTS:
                raise RateLimitedError(
                    f"stats.nba.com rate-limited {endpoint_cls.__name__} (HTTP 429). "
                    f"Retrying with backoff; if this keeps happening, raise "
                    f"{RATE_LIMIT_ENV_VAR} above its current setting."
                ) from exc
            if status is not None and status >= 500:
                raise TransientAPIError(
                    f"stats.nba.com returned HTTP {status} for {endpoint_cls.__name__}."
                ) from exc
            raise
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise TransientAPIError(
                f"connection failure calling {endpoint_cls.__name__}: {exc}. "
                "Usually transient; if it persists, check network access to stats.nba.com."
            ) from exc
        return instance.get_data_frames()[result_set]

    return _retry_policy()(_once)


def fetch_all_players(
    season: str,
    *,
    limiter: RateLimiter | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> pd.DataFrame:
    """Fetch the league's full player master list: one row per player, all history.

    This is the smallest useful call this module can make, one request, no
    per-season loop, and a good proof that throttling and retry work end to
    end. Every other endpoint this project adds later (play-by-play, box
    scores, shot logs) is keyed by the ``PERSON_ID`` this table returns, so it
    is also the first table the rest of the pipeline needs: a name-and-ID
    lookup that every downstream join can rely on.

    Args:
        season: Season string in the format ``"YYYY-YY"``, for example
            ``"2024-25"``. The endpoint requires it even though, with
            ``is_only_current_season=0`` (what this function always passes),
            the returned roster spans every season, not just this one.
        limiter: Rate limiter to throttle this call through. Defaults to
            :func:`default_limiter`.
        timeout: Per-request timeout in seconds.

    Returns:
        One row per player, with at least ``PERSON_ID``,
        ``DISPLAY_FIRST_LAST``, ``FROM_YEAR`` and ``TO_YEAR`` columns, as
        returned by the ``commonallplayers`` endpoint.

    Raises:
        MissingDependencyError: If ``nba_api`` is not installed.
        RateLimitedError: If every retry attempt still comes back HTTP 429.
        TransientAPIError: If every retry attempt hits a connection failure,
            timeout, or 5xx response.
    """
    try:
        from nba_api.stats.endpoints import commonallplayers
    except ImportError as exc:
        raise MissingDependencyError(_MISSING_DEPENDENCY_MESSAGE) from exc

    return call_endpoint(
        commonallplayers.CommonAllPlayers,
        limiter=limiter,
        timeout=timeout,
        is_only_current_season=0,
        league_id="00",
        season=season,
    )
