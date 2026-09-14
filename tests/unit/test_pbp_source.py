"""Tests for the play-by-play download layer.

Nothing here touches the network. Every HTTP call goes through a fake
`requests.Session` whose `get` returns a scripted response, so the behaviour
that matters can be exercised deterministically: that an empty-but-successful
payload is refused rather than cached, that a partial write cannot replace a
good file, and that seasons outside the served range fail with a reason rather
than a bare bound.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
import requests

from pippen import paths
from pippen.data.nba_api import RateLimiter
from pippen.rapm import pbp_source

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point pippen's data root at an isolated directory for this test."""
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    return tmp_path


@pytest.fixture
def instant_limiter() -> RateLimiter:
    """A limiter that never waits, so tests do not spend real seconds sleeping."""
    return RateLimiter(0.0)


# ------------------------------------------------------------------ fakes


class _FakeResponse:
    """Stands in for `requests.Response` for the parts pbp_source.py touches."""

    def __init__(self, status_code: int, payload: Any = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)  # type: ignore[arg-type]

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON object could be decoded")
        return self._payload


class _FakeSession:
    """Returns scripted responses and records the URLs it was asked for."""

    def __init__(self, *responses: Any) -> None:
        self._responses = list(responses)
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> Any:
        del kwargs
        self.urls.append(url)
        outcome = self._responses.pop(0) if self._responses else _FakeResponse(200, {})
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed = True


def _pbp_payload(periods: int = 4) -> dict[str, Any]:
    """A play-by-play payload shaped like data.nba.com's, with real periods."""
    return {"g": {"gid": "0022300001", "pd": [{"p": n + 1, "pla": []} for n in range(periods)]}}


# ------------------------------------------------------------------ user agent


def test_user_agent_carries_the_package_name_by_default() -> None:
    agent = pbp_source.user_agent()
    assert agent.startswith("Mozilla/")
    assert "pippen/" in agent


def test_user_agent_never_contains_a_url_by_default() -> None:
    # data.nba.com answers 403 to any User-Agent containing a URL, so the
    # default must not carry one. This is the check that stops someone
    # "improving" the default into a 403.
    assert "http" not in pbp_source.user_agent().lower()


def test_user_agent_honours_the_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pbp_source.USER_AGENT_ENV_VAR, "custom/9.9")
    assert pbp_source.user_agent() == "custom/9.9"


# ------------------------------------------------------------------ coverage


@pytest.mark.parametrize("season", [2002, 2010, 2015])
def test_seasons_before_coverage_are_refused_with_a_reason(season: int) -> None:
    with pytest.raises(pbp_source.SeasonNotCoveredError, match="403"):
        pbp_source.check_season(season)


@pytest.mark.parametrize("season", [2025, 2026])
def test_seasons_after_coverage_are_refused_with_a_reason(season: int) -> None:
    with pytest.raises(pbp_source.SeasonNotCoveredError, match="empty period array"):
        pbp_source.check_season(season)


@pytest.mark.parametrize("season", [2016, 2020, 2024])
def test_covered_seasons_pass(season: int) -> None:
    pbp_source.check_season(season)


# ------------------------------------------------------------------ validity


def test_a_payload_with_periods_is_valid() -> None:
    assert pbp_source._is_valid_pbp(_pbp_payload()) is True


def test_the_empty_stub_data_nba_returns_for_dead_seasons_is_invalid() -> None:
    # This is the exact shape data.nba.com returns for 2025-26: HTTP 200, a
    # real game id, and no periods. Status code alone would cache it.
    assert pbp_source._is_valid_pbp({"g": {"gid": "0022500001", "pd": []}}) is False


@pytest.mark.parametrize("payload", [None, {}, {"g": {}}, [], "text"])
def test_malformed_payloads_are_invalid(payload: Any) -> None:
    assert pbp_source._is_valid_pbp(payload) is False


def test_a_schedule_needs_at_least_one_month() -> None:
    assert pbp_source._is_valid_schedule({"lscd": [{"mscd": {"g": []}}]}) is True
    assert pbp_source._is_valid_schedule({"lscd": []}) is False


# ------------------------------------------------------------------ atomic write


def test_writing_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    target = tmp_path / "game.json"
    pbp_source._write_json_atomically({"a": 1}, target)
    assert json.loads(target.read_text()) == {"a": 1}
    assert list(tmp_path.iterdir()) == [target]


def test_a_failed_write_leaves_the_existing_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "game.json"
    target.write_text('{"original": true}')

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr("pippen.rapm.pbp_source.json.dump", explode)
    with pytest.raises(RuntimeError):
        pbp_source._write_json_atomically({"new": True}, target)

    assert json.loads(target.read_text()) == {"original": True}
    assert list(tmp_path.iterdir()) == [target]


# ------------------------------------------------------------------ fetching


def test_a_five_hundred_is_transient_and_a_four_hundred_is_not() -> None:
    session = _FakeSession(_FakeResponse(503))
    with pytest.raises(pbp_source.TransientDownloadError):
        pbp_source._get_json(cast(requests.Session, session), "http://example", timeout=1.0)

    session = _FakeSession(_FakeResponse(404))
    with pytest.raises(requests.HTTPError):
        pbp_source._get_json(cast(requests.Session, session), "http://example", timeout=1.0)


def test_a_body_that_is_not_json_is_treated_as_transient() -> None:
    # The usual cause is a truncated response, which a retry fixes.
    session = _FakeSession(_FakeResponse(200, payload=None, text="<html>"))
    with pytest.raises(pbp_source.TransientDownloadError, match="not valid JSON"):
        pbp_source._get_json(cast(requests.Session, session), "http://example", timeout=1.0)


def test_an_empty_payload_is_reported_and_never_written(
    data_root: Path, instant_limiter: RateLimiter
) -> None:
    session = _FakeSession(_FakeResponse(200, {"g": {"gid": "0022400001", "pd": []}}))
    result = pbp_source.download_game(
        "0022400001", 2024, session=cast(requests.Session, session), limiter=instant_limiter
    )
    assert not result.ok
    assert "no periods" in str(result.error)
    assert not result.path.exists()


def test_a_valid_payload_is_written_and_reported_ok(
    data_root: Path, instant_limiter: RateLimiter
) -> None:
    session = _FakeSession(_FakeResponse(200, _pbp_payload()))
    result = pbp_source.download_game(
        "0022300001", 2023, session=cast(requests.Session, session), limiter=instant_limiter
    )
    assert result.ok
    assert result.downloaded
    assert json.loads(result.path.read_text())["g"]["gid"] == "0022300001"


def test_an_already_cached_game_makes_no_request(
    data_root: Path, instant_limiter: RateLimiter
) -> None:
    pbp_source.cache_root(create=True)
    target = pbp_source.game_path("0022300001")
    target.write_text(json.dumps(_pbp_payload()))

    session = _FakeSession()
    result = pbp_source.download_game(
        "0022300001", 2023, session=cast(requests.Session, session), limiter=instant_limiter
    )
    assert result.ok
    assert not result.downloaded
    assert session.urls == []


def test_download_failures_are_returned_rather_than_raised(
    data_root: Path, instant_limiter: RateLimiter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A season run must survive one bad game, so the failure is a value.
    monkeypatch.setattr(pbp_source, "_MAX_ATTEMPTS", 1)
    session = _FakeSession(_FakeResponse(404))
    result = pbp_source.download_game(
        "0022300001", 2023, session=cast(requests.Session, session), limiter=instant_limiter
    )
    assert not result.ok
    assert "download failed" in str(result.error)


# ------------------------------------------------------------------ schedule


def test_season_game_ids_keeps_only_regular_season_games(data_root: Path) -> None:
    pbp_source.cache_root(create=True)
    schedule = {
        "lscd": [
            {
                "mscd": {
                    "g": [
                        {"gid": "0021600001"},  # regular season
                        {"gid": "0011600002"},  # preseason
                        {"gid": "0041600003"},  # playoffs
                        {"gid": "0021600004"},  # regular season
                    ]
                }
            }
        ]
    }
    pbp_source.schedule_path(2016).write_text(json.dumps(schedule))

    assert pbp_source.season_game_ids(2016) == ["0021600001", "0021600004"]
    assert len(pbp_source.season_game_ids(2016, regular_season_only=False)) == 4
