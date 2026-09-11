"""Downloader for hoopR's bulk historical NBA data.

hoopR (part of the SportsDataverse project) publishes ESPN-sourced NBA data as
one Parquet file per dataset per season, hosted in the ``hoopR-nba-data``
GitHub repository::

    https://github.com/sportsdataverse/hoopR-nba-data

Attribution and licence
    That repository is licensed CC BY 4.0, which permits redistribution
    with attribution. :data:`ATTRIBUTION` holds the required credit line;
    anything this project publishes that is derived from hoopR data must
    carry it (see ``docs/research/06_data_sources.md``).

Season numbering
    ``season`` throughout this module is the season's *end* year: 2024 means
    the 2023-24 season. This matches ``pippen.paths.season_file``.

Known limitation -- load-bearing for the rest of the pipeline
    hoopR's ``play_by_play`` dataset is ESPN-sourced and records only event
    participants (``athlete_id_1``/``2``/``3`` columns). It has no on-court
    lineup column. RAPM needs the full five-man lineup for every
    possession, so it cannot be built from this dataset alone; that requires
    ``pbpstats`` running against NBA API data instead. This module only
    downloads the file -- it makes no claim about what can be computed from
    its contents.

File layout
    Most datasets nest their Parquet files under a ``parquet/``
    subdirectory (``nba/{dataset}/parquet/{dataset}_{season}.parquet``); at
    least one does not. Rather than hard-coding one guess, every download
    probes both layouts with a HEAD request and uses whichever one answers.

    One dataset's *directory* name diverges from its file-name prefix:
    ``play_by_play`` is published under ``nba/pbp/parquet/``, not
    ``nba/play_by_play/parquet/``, even though the files inside it are still
    named ``play_by_play_{season}.parquet``. Confirmed live against the
    repository on 2026-09-10 -- the URL pattern in the project's own data
    source notes does not account for this, and probing alone cannot recover
    it, since ``nba/play_by_play/`` simply does not exist. See
    :data:`_REMOTE_DIRECTORY`.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import requests
from pyarrow.lib import ArrowInvalid  # type: ignore[import-untyped]
from rich.console import Console
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from pippen.paths import dataset_file, season_file

if TYPE_CHECKING:
    from collections.abc import Iterable

ATTRIBUTION: Final = (
    "Data from hoopR-nba-data (https://github.com/sportsdataverse/hoopR-nba-data), "
    "SportsDataverse contributors, licensed CC BY 4.0."
)

_RAW_BASE: Final = "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/nba"

# Every dataset name currently published under nba/ in hoopR-nba-data. Kept as
# an explicit allow-list so a typo in a dataset name fails immediately with a
# readable message, instead of silently probing URLs that can never exist.
DATASETS: Final = frozenset(
    {
        "play_by_play",
        "player_box",
        "team_box",
        "schedules",
        "rosters",
        "game_rosters",
        "shots",
        "standings",
        "player_season_stats",
        "team_season_stats",
        "draft",
        "officials",
        "betting_lines",
        "crosswalk",
        "player_core",
    }
)

PLAY_BY_PLAY_FIRST_SEASON: Final = 2002
PLAY_BY_PLAY_LAST_SEASON: Final = 2026
# Convenience default for the common case: every published play-by-play season.
PLAY_BY_PLAY_SEASONS: Final = range(PLAY_BY_PLAY_FIRST_SEASON, PLAY_BY_PLAY_LAST_SEASON + 1)

# Probed in this order: the parquet/ subdirectory is the documented layout for
# play_by_play and is right for most datasets, so trying it first saves a
# request in the common case.
_LAYOUTS: Final = (
    "{directory}/parquet/{dataset}_{season}.parquet",
    "{directory}/{dataset}_{season}.parquet",
)

# hoopR's remote directory names usually match the dataset name, but not
# always. Verified live on 2026-09-10: play_by_play's directory is `pbp`
# while its files keep the `play_by_play_` prefix, and no other dataset in
# `DATASETS` has this split. Any dataset not listed here probes under its own
# name, which is correct for every other known dataset as of that check.
_REMOTE_DIRECTORY: Final = {"play_by_play": "pbp"}

# Datasets published as one file covering every season rather than one file per
# season. Confirmed against the live repository: nba/schedules holds a master
# table spanning 2002 to 2027, alongside 42 numbered files far too small to be
# seasons. Asking for a per-season schedule returns a 404, which is what the
# first version of this module did on every call.
_MASTER_FILES: Final = {"schedules": "nba_schedule_master"}

_DEFAULT_TIMEOUT_SECONDS: Final = 30.0
_CHUNK_BYTES: Final = 1024 * 1024

# Retry policy for transient network failures. Read fresh on every call (see
# `_retry_policy`) rather than baked into a decorator, so a test can shrink
# these and see the effect immediately instead of sleeping through real
# exponential delays.
_MAX_ATTEMPTS: Final = 4
_BACKOFF_INITIAL_SECONDS: Final = 1.0
_BACKOFF_MAX_SECONDS: Final = 20.0

DownloadStatus = Literal["downloaded", "skipped", "failed"]


class TransientDownloadError(Exception):
    """A network failure worth retrying: timeout, connection reset, or 5xx.

    Anything else -- a 404, a malformed URL, a disk error while writing -- is
    treated as permanent for the attempt and is not retried.
    """


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of trying to get one season of one dataset onto disk.

    Attributes:
        dataset: The hoopR dataset name.
        season: Season end year, e.g. 2024 for the 2023-24 season.
        status: ``"downloaded"`` if fetched this run, ``"skipped"`` if a
            valid file already existed, or ``"failed"`` (see ``reason``).
        path: Where the file ended up on disk. Set for ``"downloaded"`` and
            ``"skipped"``, ``None`` for ``"failed"``.
        reason: Human-readable cause of failure. Set only when ``status`` is
            ``"failed"``.
    """

    dataset: str
    season: int
    status: DownloadStatus
    path: Path | None = None
    reason: str | None = None


def download_season(
    dataset: str,
    season: int,
    *,
    force: bool = False,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> DownloadResult:
    """Download one season of one hoopR dataset into the ``raw`` data stage.

    The file is streamed to a temporary path beside the destination and only
    moved into place after it passes an integrity check, so a crash or a
    truncated transfer never leaves a half-written file at the final path.

    Args:
        dataset: hoopR dataset name, e.g. ``"play_by_play"``. Must be a
            member of :data:`DATASETS`.
        season: Season end year, e.g. 2024 for the 2023-24 season.
        force: When true, re-download even if a valid file already exists at
            the destination. When false (the default), an existing file that
            passes the integrity check is left alone.
        timeout: Per-request timeout in seconds, applied to every HTTP call
            this makes.
        session: HTTP session to issue requests on. A short-lived session is
            created and closed automatically when omitted; callers doing many
            downloads should pass one in to reuse connections (see
            :func:`download_seasons`).

    Returns:
        A :class:`DownloadResult` describing what happened to this one file.

    Raises:
        ValueError: If ``dataset`` is not a recognised hoopR dataset name.
    """
    _validate_dataset(dataset)
    target = season_file("raw", dataset, season, create=True)

    if not force and target.exists() and _is_valid_parquet(target):
        return DownloadResult(dataset=dataset, season=season, status="skipped", path=target)

    if session is not None:
        return _fetch_one(session, dataset, season, target, timeout=timeout)
    with requests.Session() as owned_session:
        return _fetch_one(owned_session, dataset, season, target, timeout=timeout)


def download_seasons(
    dataset: str,
    seasons: Iterable[int],
    *,
    force: bool = False,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    console: Console | None = None,
) -> list[DownloadResult]:
    """Download a range of seasons of one hoopR dataset, reporting progress.

    A single HTTP session is reused across the whole range, so the underlying
    TCP/TLS connection to GitHub is kept warm instead of renegotiated for
    every file. One season failing does not stop the rest: each season gets
    its own :class:`DownloadResult`, so a caller can see exactly which ones
    need a retry later.

    Args:
        dataset: hoopR dataset name, e.g. ``"play_by_play"``. Must be a
            member of :data:`DATASETS`.
        seasons: Season end years to fetch, e.g. ``range(2015, 2025)`` or
            :data:`PLAY_BY_PLAY_SEASONS`.
        force: When true, re-download every season even if a valid file
            already exists.
        timeout: Per-request timeout in seconds, applied to every HTTP call.
        console: Where to print progress. Defaults to a new
            :class:`rich.console.Console`.

    Returns:
        One :class:`DownloadResult` per season, in the order ``seasons`` was
        iterated.

    Raises:
        ValueError: If ``dataset`` is not a recognised hoopR dataset name.
    """
    _validate_dataset(dataset)
    out = console if console is not None else Console()

    results: list[DownloadResult] = []
    with requests.Session() as session:
        for season in seasons:
            result = download_season(dataset, season, force=force, timeout=timeout, session=session)
            results.append(result)
            out.print(_progress_line(result))
    return results


def is_master_dataset(dataset: str) -> bool:
    """Whether a dataset is published as one file rather than one per season.

    Args:
        dataset: hoopR dataset name.

    Returns:
        True if the dataset has a single master file covering every season.
    """
    return dataset in _MASTER_FILES


def download_master(
    dataset: str,
    *,
    force: bool = False,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> DownloadResult:
    """Download a dataset published as one file covering every season.

    Args:
        dataset: hoopR dataset name, which must be a master dataset. Use
            :func:`is_master_dataset` to check.
        force: Re-download even when a valid file is already present.
        timeout: Per-request timeout in seconds.
        session: HTTP session to reuse. A new one is created if omitted.

    Returns:
        A :class:`DownloadResult`. Its ``season`` is 0, since the file covers
        every season and belongs to none of them.

    Raises:
        ValueError: If ``dataset`` is not a master dataset.
    """
    if dataset not in _MASTER_FILES:
        known = ", ".join(sorted(_MASTER_FILES))
        raise ValueError(f"{dataset!r} is not published as a master file. Master datasets: {known}")

    stem = _MASTER_FILES[dataset]
    target = dataset_file("raw", dataset, stem, create=True)
    if not force and _is_valid_parquet(target):
        return DownloadResult(dataset=dataset, season=0, status="skipped", path=target)

    url = f"{_RAW_BASE}/{dataset}/{stem}.parquet"
    owned = session is None
    active = session if session is not None else requests.Session()
    try:
        failure = _download_atomically(active, url, target, timeout=timeout)
    finally:
        if owned:
            active.close()

    if failure is not None:
        return DownloadResult(dataset=dataset, season=0, status="failed", reason=failure)
    return DownloadResult(dataset=dataset, season=0, status="downloaded", path=target)


def _validate_dataset(dataset: str) -> None:
    """Raise ``ValueError`` if ``dataset`` is not a recognised hoopR dataset name.

    Args:
        dataset: The dataset name to check.

    Raises:
        ValueError: If ``dataset`` is not a member of :data:`DATASETS`.
    """
    if dataset not in DATASETS:
        valid = ", ".join(sorted(DATASETS))
        raise ValueError(f"unknown hoopR dataset {dataset!r}; expected one of: {valid}")


def _progress_line(result: DownloadResult) -> str:
    """Render one Rich-markup progress line for a single download result."""
    if result.status == "downloaded":
        return f"[green]downloaded[/green] {result.dataset} {result.season}"
    if result.status == "skipped":
        return f"[dim]skipped[/dim]    {result.dataset} {result.season} (already present)"
    return f"[red]failed[/red]     {result.dataset} {result.season}: {result.reason}"


def _fetch_one(
    session: requests.Session,
    dataset: str,
    season: int,
    target: Path,
    *,
    timeout: float,
) -> DownloadResult:
    """Resolve, download and validate one file, given a session and destination.

    Args:
        session: HTTP session to issue requests on.
        dataset: hoopR dataset name.
        season: Season end year.
        target: Final destination path for the Parquet file.
        timeout: Per-request timeout in seconds.

    Returns:
        A :class:`DownloadResult` for this dataset and season.
    """
    url = _resolve_url(session, dataset, season, timeout=timeout)
    if url is None:
        candidates = ", ".join(_candidate_urls(dataset, season))
        return DownloadResult(
            dataset=dataset,
            season=season,
            status="failed",
            reason=f"no known hoopR-nba-data layout exists for this file; tried: {candidates}",
        )

    failure = _download_atomically(session, url, target, timeout=timeout)
    if failure is not None:
        return DownloadResult(dataset=dataset, season=season, status="failed", reason=failure)
    return DownloadResult(dataset=dataset, season=season, status="downloaded", path=target)


def _download_atomically(
    session: requests.Session, url: str, target: Path, *, timeout: float
) -> str | None:
    """Download one URL to ``target``, leaving nothing behind on failure.

    The file is written to a temporary sibling and only moved into place once
    it has been read back as valid Parquet. A crash or a truncated response
    therefore cannot leave a partial file at the final path, where the next run
    would skip it as already present and every calculation downstream would
    inherit it.

    Args:
        session: HTTP session to issue the request on.
        url: URL to fetch.
        target: Final destination path.
        timeout: Per-request timeout in seconds.

    Returns:
        None on success, or a human-readable reason the download failed.
    """
    # Same filesystem as the destination, so the final move is an atomic rename
    # rather than a copy that could itself be interrupted.
    file_descriptor, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".part"
    )
    os.close(file_descriptor)
    tmp_path = Path(tmp_name)

    try:
        _download(session, url, tmp_path, timeout=timeout)
    except (TransientDownloadError, requests.HTTPError) as exc:
        tmp_path.unlink(missing_ok=True)
        return f"download failed: {exc}"

    if not _is_valid_parquet(tmp_path):
        tmp_path.unlink(missing_ok=True)
        return "downloaded file failed the parquet integrity check (likely truncated)"

    tmp_path.replace(target)
    return None


def _candidate_urls(dataset: str, season: int) -> list[str]:
    """Return the URLs worth probing for one dataset and season, most likely first.

    Args:
        dataset: hoopR dataset name.
        season: Season end year.

    Returns:
        Candidate URLs under both known ``hoopR-nba-data`` layouts. The
        remote directory segment is looked up in :data:`_REMOTE_DIRECTORY`
        and falls back to ``dataset`` itself, since only one known dataset
        diverges.
    """
    directory = _REMOTE_DIRECTORY.get(dataset, dataset)
    return [
        f"{_RAW_BASE}/{layout.format(directory=directory, dataset=dataset, season=season)}"
        for layout in _LAYOUTS
    ]


def _resolve_url(
    session: requests.Session, dataset: str, season: int, *, timeout: float
) -> str | None:
    """Find which known ``hoopR-nba-data`` URL layout actually serves this file.

    Args:
        session: HTTP session to issue HEAD requests on.
        dataset: hoopR dataset name.
        season: Season end year.
        timeout: Per-request timeout in seconds.

    Returns:
        The first candidate URL that answers HEAD with 200, or ``None`` if
        neither known layout does.
    """
    for url in _candidate_urls(dataset, season):
        if _head(session, url, timeout=timeout).status_code == 200:
            return url
    return None


def _retry_policy() -> Retrying:
    """Build the bounded exponential-backoff policy used for every network call.

    Built fresh on each use (rather than fixed into a decorator at import
    time) so :data:`_MAX_ATTEMPTS` and the backoff constants can be shrunk in
    tests and take effect immediately.

    Returns:
        A :class:`tenacity.Retrying` controller: it retries only
        :class:`TransientDownloadError`, waits with exponential backoff
        capped at :data:`_BACKOFF_MAX_SECONDS`, gives up after
        :data:`_MAX_ATTEMPTS` attempts, and re-raises the last error rather
        than wrapping it -- so a caller catching ``TransientDownloadError``
        still sees a bounded, terminating call.
    """
    return Retrying(
        retry=retry_if_exception_type(TransientDownloadError),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=_BACKOFF_INITIAL_SECONDS, max=_BACKOFF_MAX_SECONDS),
        reraise=True,
    )


def _head(session: requests.Session, url: str, *, timeout: float) -> requests.Response:
    """HEAD a URL, retrying only on transient network failures.

    Args:
        session: HTTP session to issue the request on.
        url: URL to probe.
        timeout: Per-request timeout in seconds.

    Returns:
        The response. A 404 comes back as an ordinary response, not an
        exception: it means this URL layout is wrong for this dataset, which
        is routine, not a network fault.

    Raises:
        TransientDownloadError: If every retry attempt hits a connection
            failure, timeout, or 5xx response.
    """
    return _retry_policy()(_head_once, session, url, timeout=timeout)


def _head_once(session: requests.Session, url: str, *, timeout: float) -> requests.Response:
    """Issue a single HEAD request, translating transient failures for the retry policy.

    Args:
        session: The HTTP session to issue the request on.
        url: The URL to probe.
        timeout: Seconds to wait before treating the request as failed.

    Returns:
        The response, including 4xx responses, which the caller inspects.

    Raises:
        TransientDownloadError: On a connection failure, a timeout, or a 5xx
            response, all of which the retry policy should try again.
    """
    try:
        response = session.head(url, timeout=timeout, allow_redirects=True)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise TransientDownloadError(f"HEAD {url} failed: {exc}") from exc
    if response.status_code >= 500:
        raise TransientDownloadError(f"HEAD {url} returned {response.status_code}")
    return response


def _download(session: requests.Session, url: str, destination: Path, *, timeout: float) -> None:
    """GET a URL and stream its body to ``destination``, retrying transient failures.

    Args:
        session: HTTP session to issue the request on.
        url: URL to download.
        destination: File path to write the response body to. Reopened in
            truncate mode on every attempt, so a retry after a partial write
            starts from zero bytes rather than appending to a truncated file.
        timeout: Per-request timeout in seconds.

    Raises:
        TransientDownloadError: If every retry attempt hits a connection
            failure, timeout, mid-stream drop, or 5xx response.
        requests.HTTPError: On a permanent (4xx) HTTP error. Not retried.
    """
    _retry_policy()(_download_once, session, url, destination, timeout=timeout)


def _download_once(
    session: requests.Session, url: str, destination: Path, *, timeout: float
) -> None:
    """Issue a single GET request and stream its body to ``destination``.

    Args:
        session: The HTTP session to issue the request on.
        url: The URL to fetch.
        destination: Path to stream the body into. Expected to be a temporary
            path, never the final one, so a failure here cannot leave a partial
            file where a later run would mistake it for a complete download.
        timeout: Seconds to wait before treating the request as failed.

    Raises:
        TransientDownloadError: On a connection failure, a timeout, or a 5xx
            response, all of which the retry policy should try again.
        requests.HTTPError: On a 4xx response, which is permanent and is not
            retried.
    """
    try:
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
                handle.write(chunk)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status is not None and status >= 500:
            raise TransientDownloadError(f"GET {url} returned {status}") from exc
        raise
    except (
        requests.ConnectionError,
        requests.Timeout,
        requests.exceptions.ChunkedEncodingError,
    ) as exc:
        raise TransientDownloadError(f"GET {url} failed: {exc}") from exc


def _is_valid_parquet(path: Path) -> bool:
    """Check that a Parquet file opens cleanly and has at least one row.

    Only the file's footer metadata is read, not its row data, so this is
    cheap even for a full season of play-by-play.

    Args:
        path: File to check.

    Returns:
        ``False`` for a missing file, a zero-byte file, a file pyarrow
        cannot parse (the signature of a truncated download), or a file with
        zero rows. ``True`` otherwise.
    """
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        metadata = pq.ParquetFile(path).metadata
    except (OSError, ArrowInvalid):
        return False
    return bool(int(metadata.num_rows) > 0)
