"""Tests for the hoopR bulk-data downloader.

None of these hit the network: every HTTP call goes through a fake
`requests.Session` whose `head`/`get` are replaced with scripted outcomes, so
retry, truncation and layout-probing behaviour can be exercised deterministically
and instantly. The one real-network test is marked `@pytest.mark.network` and
excluded from the default run.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import requests
from rich.console import Console

from pippen import paths
from pippen.data import hoopr

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point pippen's data root at an isolated directory for this test."""
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    return tmp_path


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero out retry sleep time without changing how many attempts happen."""
    monkeypatch.setattr(hoopr, "_BACKOFF_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(hoopr, "_BACKOFF_MAX_SECONDS", 0.0)


# ------------------------------------------------------------------ fakes


class _FakeResponse:
    """Stands in for `requests.Response` for the parts hoopr.py touches."""

    def __init__(self, status_code: int, chunks: Sequence[bytes] = ()) -> None:
        self.status_code = status_code
        self._chunks = list(chunks)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def iter_content(self, chunk_size: int) -> Sequence[bytes]:
        del chunk_size
        return self._chunks


class _PartialThenDropped:
    """A response whose body starts streaming, then the connection drops.

    Used to prove a retried download starts the destination file from zero
    bytes rather than appending to whatever the failed attempt already wrote.
    """

    def __init__(self, first_chunk: bytes) -> None:
        self.status_code = 200
        self._first_chunk = first_chunk

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        del chunk_size
        yield self._first_chunk
        raise requests.exceptions.ChunkedEncodingError("connection dropped mid-stream")


class _Scripted:
    """Replays a fixed, ordered sequence of outcomes; raises/returns them in turn.

    Running out of scripted outcomes raises `IndexError` rather than repeating
    the last one. That is deliberate: if retry logic were ever unbounded, this
    turns a hang into an immediate, readable test failure instead of masking it.
    """

    def __init__(self, outcomes: Sequence[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, url: str, **kwargs: object) -> object:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _forbid(verb: str) -> Callable[..., object]:
    """Return a stand-in that fails the test loudly instead of hitting the network."""

    def _forbidden(url: str, **kwargs: object) -> object:
        raise AssertionError(f"unexpected {verb} to {url}")

    return _forbidden


def _no_network_session(monkeypatch: pytest.MonkeyPatch) -> requests.Session:
    """A session where any request at all fails the test."""
    return _scripted_session(monkeypatch)


def _scripted_session(
    monkeypatch: pytest.MonkeyPatch, *, head: _Scripted | None = None, get: _Scripted | None = None
) -> requests.Session:
    """A real Session whose head/get are replaced with scripted outcomes.

    Anything left unscripted is replaced with a refusal rather than left as the
    real method. A test that scripts only HEAD is asserting that GET never
    happens, and that assertion should fail loudly rather than quietly reach
    the network.
    """
    session = requests.Session()
    monkeypatch.setattr(session, "head", head if head is not None else _forbid("HEAD"))
    monkeypatch.setattr(session, "get", get if get is not None else _forbid("GET"))
    return session


def _valid_parquet_bytes(tmp_path: Path, tag: str, value: int = 1) -> bytes:
    """Build the raw bytes of a small, well-formed, non-empty Parquet file."""
    scratch = tmp_path / f"_scratch_{tag}.parquet"
    pd.DataFrame({"a": [value, value + 1, value + 2]}).to_parquet(scratch)
    data = scratch.read_bytes()
    scratch.unlink()
    return data


# ------------------------------------------------------------------ module-level guards


def test_attribution_names_the_source_and_licence() -> None:
    # This string is what makes redistribution lawful under CC BY 4.0. If it
    # regresses, nothing downstream will notice -- so pin its content here.
    assert "hoopR-nba-data" in hoopr.ATTRIBUTION
    assert "CC BY 4.0" in hoopr.ATTRIBUTION


def test_module_docstring_states_the_lineup_limitation() -> None:
    doc = hoopr.__doc__ or ""
    assert "ESPN" in doc
    assert "lineup" in doc.lower()


def test_datasets_matches_the_verified_list() -> None:
    expected = {
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
    assert expected == hoopr.DATASETS


def test_play_by_play_season_range_matches_the_verified_coverage() -> None:
    assert hoopr.PLAY_BY_PLAY_FIRST_SEASON == 2002
    assert hoopr.PLAY_BY_PLAY_LAST_SEASON == 2026
    assert next(iter(hoopr.PLAY_BY_PLAY_SEASONS)) == 2002
    assert hoopr.PLAY_BY_PLAY_SEASONS[-1] == 2026


# ------------------------------------------------------------------ DownloadResult


def test_download_result_is_frozen() -> None:
    result = hoopr.DownloadResult(dataset="play_by_play", season=2024, status="skipped")
    with pytest.raises(AttributeError):
        result.status = "failed"  # type: ignore[misc]


# ------------------------------------------------------------------ dataset validation


def test_download_season_rejects_unknown_dataset() -> None:
    with pytest.raises(ValueError, match="unknown hoopR dataset"):
        hoopr.download_season("not_a_real_dataset", 2024)


def test_unknown_dataset_error_lists_the_valid_ones() -> None:
    with pytest.raises(ValueError, match="expected one of") as caught:
        hoopr.download_season("not_a_real_dataset", 2024)
    assert "play_by_play" in str(caught.value)


def test_download_seasons_rejects_unknown_dataset_before_touching_the_network() -> None:
    # No session is even constructed here: validation must happen first.
    with pytest.raises(ValueError, match="unknown hoopR dataset"):
        hoopr.download_seasons("not_a_real_dataset", [2024])


# ------------------------------------------------------------------ _candidate_urls / _resolve_url


def test_candidate_urls_tries_the_parquet_subdirectory_layout_first() -> None:
    urls = hoopr._candidate_urls("player_box", 2024)
    assert urls == [
        "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/nba/"
        "player_box/parquet/player_box_2024.parquet",
        "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/nba/"
        "player_box/player_box_2024.parquet",
    ]


def test_candidate_urls_uses_pbp_as_play_by_plays_remote_directory() -> None:
    # Verified live against the repository: nba/play_by_play/ does not exist,
    # the real directory is nba/pbp/, though files keep the play_by_play_
    # filename prefix. See `_REMOTE_DIRECTORY`.
    urls = hoopr._candidate_urls("play_by_play", 2024)
    assert urls == [
        "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/nba/"
        "pbp/parquet/play_by_play_2024.parquet",
        "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/nba/"
        "pbp/play_by_play_2024.parquet",
    ]


def test_resolve_url_falls_back_to_the_second_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    head = _Scripted([SimpleNamespace(status_code=404), SimpleNamespace(status_code=200)])
    session = _scripted_session(monkeypatch, head=head)
    url = hoopr._resolve_url(session, "shots", 2024, timeout=5)
    assert url == hoopr._candidate_urls("shots", 2024)[1]


def test_resolve_url_returns_none_when_no_layout_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    head = _Scripted([SimpleNamespace(status_code=404), SimpleNamespace(status_code=404)])
    session = _scripted_session(monkeypatch, head=head)
    assert hoopr._resolve_url(session, "shots", 2024, timeout=5) is None


# ------------------------------------------------------------------ _head / _head_once


def test_head_once_treats_404_as_an_ordinary_response(monkeypatch: pytest.MonkeyPatch) -> None:
    head = _Scripted([SimpleNamespace(status_code=404)])
    session = _scripted_session(monkeypatch, head=head)
    response = hoopr._head_once(session, "https://example.invalid/x", timeout=5)
    assert response.status_code == 404


def test_head_once_treats_server_error_as_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    head = _Scripted([SimpleNamespace(status_code=500)])
    session = _scripted_session(monkeypatch, head=head)
    with pytest.raises(hoopr.TransientDownloadError):
        hoopr._head_once(session, "https://example.invalid/x", timeout=5)


@pytest.mark.usefixtures("no_backoff")
def test_head_retries_and_recovers_from_a_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = _Scripted(
        [requests.ConnectionError("boom"), SimpleNamespace(status_code=200)],
    )
    session = _scripted_session(monkeypatch, head=head)
    response = hoopr._head(session, "https://example.invalid/x", timeout=5)
    assert response.status_code == 200
    assert head.calls == 2


@pytest.mark.usefixtures("no_backoff")
def test_head_gives_up_after_the_bounded_number_of_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes = [requests.ConnectionError("boom")] * hoopr._MAX_ATTEMPTS
    head = _Scripted(outcomes)
    session = _scripted_session(monkeypatch, head=head)
    with pytest.raises(hoopr.TransientDownloadError):
        hoopr._head(session, "https://example.invalid/x", timeout=5)
    # Exactly the bounded number of attempts: never fewer, never unbounded.
    assert head.calls == hoopr._MAX_ATTEMPTS


# ------------------------------------------------------------------ _download / _download_once


def test_download_once_reraises_permanent_client_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = _Scripted([_FakeResponse(404)])
    session = _scripted_session(monkeypatch, get=get)
    with pytest.raises(requests.HTTPError):
        hoopr._download_once(session, "https://example.invalid/x", Path("/dev/null"), timeout=5)


def test_download_once_wraps_server_errors_as_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = _Scripted([_FakeResponse(500)])
    session = _scripted_session(monkeypatch, get=get)
    with pytest.raises(hoopr.TransientDownloadError):
        hoopr._download_once(session, "https://example.invalid/x", Path("/dev/null"), timeout=5)


@pytest.mark.usefixtures("no_backoff")
def test_download_retries_after_a_partial_stream_and_does_not_append(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    full = _valid_parquet_bytes(tmp_path, "full")
    get = _Scripted([_PartialThenDropped(b"garbage-partial-bytes"), _FakeResponse(200, [full])])
    session = _scripted_session(monkeypatch, get=get)
    destination = tmp_path / "out.parquet"

    hoopr._download(session, "https://example.invalid/x", destination, timeout=5)

    # If the retry had appended instead of truncating, this would be longer
    # than `full` and would fail the parquet integrity check besides.
    assert destination.read_bytes() == full
    assert get.calls == 2


# ------------------------------------------------------------------ _is_valid_parquet


def test_is_valid_parquet_accepts_a_well_formed_file(tmp_path: Path) -> None:
    path = tmp_path / "ok.parquet"
    path.write_bytes(_valid_parquet_bytes(tmp_path, "ok"))
    assert hoopr._is_valid_parquet(path) is True


def test_is_valid_parquet_rejects_a_missing_file(tmp_path: Path) -> None:
    assert hoopr._is_valid_parquet(tmp_path / "does_not_exist.parquet") is False


def test_is_valid_parquet_rejects_a_zero_byte_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.parquet"
    path.write_bytes(b"")
    assert hoopr._is_valid_parquet(path) is False


def test_is_valid_parquet_rejects_truncated_content(tmp_path: Path) -> None:
    full = _valid_parquet_bytes(tmp_path, "trunc")
    path = tmp_path / "trunc.parquet"
    path.write_bytes(full[: len(full) // 2])
    assert hoopr._is_valid_parquet(path) is False


def test_is_valid_parquet_rejects_a_zero_row_file(tmp_path: Path) -> None:
    path = tmp_path / "zero_rows.parquet"
    pd.DataFrame({"a": pd.Series([], dtype="int64")}).to_parquet(path)
    assert hoopr._is_valid_parquet(path) is False


# ------------------------------------------------------------------ download_season


def test_download_season_skips_an_existing_valid_file(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = paths.season_file("raw", "play_by_play", 2024, create=True)
    target.write_bytes(_valid_parquet_bytes(data_root, "existing"))

    session = _no_network_session(monkeypatch)
    result = hoopr.download_season("play_by_play", 2024, session=session)

    assert result == hoopr.DownloadResult(
        dataset="play_by_play", season=2024, status="skipped", path=target
    )


def test_download_season_fetches_a_new_file(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _valid_parquet_bytes(data_root, "new")
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(200, [data])])
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, session=session, timeout=5)

    target = paths.season_file("raw", "play_by_play", 2024)
    assert result.status == "downloaded"
    assert result.path == target
    assert target.read_bytes() == data
    # No stray temp file left behind beside the finished download.
    assert list(target.parent.glob("*.part")) == []


def test_download_season_force_redownloads_a_valid_existing_file(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = paths.season_file("raw", "play_by_play", 2024, create=True)
    target.write_bytes(_valid_parquet_bytes(data_root, "old"))

    new_data = _valid_parquet_bytes(data_root, "replacement", value=99)
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(200, [new_data])])
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, force=True, session=session, timeout=5)

    assert result.status == "downloaded"
    assert target.read_bytes() == new_data


def test_download_season_reports_no_known_layout(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _Scripted([SimpleNamespace(status_code=404), SimpleNamespace(status_code=404)])
    session = _scripted_session(monkeypatch, head=head)

    result = hoopr.download_season("shots", 2024, session=session, timeout=5)

    assert result.status == "failed"
    assert result.path is None
    assert result.reason is not None
    for url in hoopr._candidate_urls("shots", 2024):
        assert url in result.reason
    target = paths.season_file("raw", "shots", 2024)
    assert not target.exists()
    assert list(target.parent.glob("*.part")) == []


def test_download_season_reports_a_truncated_download_and_cleans_up(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(200, [b"this is not a parquet file"])])
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, session=session, timeout=5)

    assert result.status == "failed"
    assert result.reason is not None
    assert "integrity check" in result.reason
    target = paths.season_file("raw", "play_by_play", 2024)
    assert not target.exists()
    assert list(target.parent.glob("*.part")) == []


def test_download_season_does_not_retry_a_permanent_client_error(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(404)])
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, session=session, timeout=5)

    assert result.status == "failed"
    assert get.calls == 1


@pytest.mark.usefixtures("no_backoff")
def test_download_season_gives_up_on_persistent_server_errors(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(500)] * hoopr._MAX_ATTEMPTS)
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, session=session, timeout=5)

    assert result.status == "failed"
    assert get.calls == hoopr._MAX_ATTEMPTS
    target = paths.season_file("raw", "play_by_play", 2024)
    assert not target.exists()


@pytest.mark.usefixtures("no_backoff")
def test_download_season_recovers_after_transient_server_errors(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _valid_parquet_bytes(data_root, "recovered")
    head = _Scripted([SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(500), _FakeResponse(500), _FakeResponse(200, [data])])
    session = _scripted_session(monkeypatch, head=head, get=get)

    result = hoopr.download_season("play_by_play", 2024, session=session, timeout=5)

    assert result.status == "downloaded"
    assert get.calls == 3


# ------------------------------------------------------------------ download_seasons


def test_download_seasons_reports_one_result_per_season_in_order(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _valid_parquet_bytes(data_root, "bulk")
    # season 2023: both layouts 404 -> failed, no GET.
    # season 2024: first layout 200 -> one GET, succeeds.
    head = _Scripted(
        [
            SimpleNamespace(status_code=404),
            SimpleNamespace(status_code=404),
            SimpleNamespace(status_code=200),
        ]
    )
    get = _Scripted([_FakeResponse(200, [data])])
    session = _scripted_session(monkeypatch, head=head, get=get)
    monkeypatch.setattr(requests, "Session", lambda: session)

    buffer = io.StringIO()
    console = Console(file=buffer, width=120)
    results = hoopr.download_seasons("play_by_play", [2023, 2024], timeout=5, console=console)

    assert [(r.season, r.status) for r in results] == [(2023, "failed"), (2024, "downloaded")]
    # Check the status landed on the right season's line. Asserting only that
    # both numbers appear somewhere would pass even if the statuses were swapped.
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    line_for = {season: next(ln for ln in lines if str(season) in ln) for season in (2023, 2024)}
    assert "failed" in line_for[2023]
    assert "downloaded" in line_for[2024]
    assert "downloaded" not in line_for[2023]


def test_download_seasons_uses_a_single_session_for_the_whole_range(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _valid_parquet_bytes(data_root, "shared-session")
    head = _Scripted([SimpleNamespace(status_code=200), SimpleNamespace(status_code=200)])
    get = _Scripted([_FakeResponse(200, [data]), _FakeResponse(200, [data])])
    session = _scripted_session(monkeypatch, head=head, get=get)
    monkeypatch.setattr(requests, "Session", lambda: session)

    results = hoopr.download_seasons(
        "play_by_play", [2023, 2024], timeout=5, console=Console(file=io.StringIO())
    )

    assert [r.status for r in results] == ["downloaded", "downloaded"]
    assert head.calls == 2
    assert get.calls == 2


# ------------------------------------------------------------------ real network (excluded by default)


@pytest.mark.network
def test_resolve_url_finds_a_real_play_by_play_season(
    data_root: Path,
) -> None:
    # Purely a HEAD probe against the real repository -- no file is written to
    # `data_root`, and `data_root` is redirected away from the real checkout's
    # `data/` directory regardless, in line with the project's data policy.
    with requests.Session() as session:
        url = hoopr._resolve_url(session, "play_by_play", 2024, timeout=30)
    assert url == hoopr._candidate_urls("play_by_play", 2024)[0]
