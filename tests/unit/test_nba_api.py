"""Tests for the stats.nba.com client.

Nothing here touches the network. The rate limiter is tested against an
injected clock rather than by sleeping, so the suite stays fast and the
assertions are exact instead of timing-dependent.

The limiter gets the most attention because its failure mode is the worst one
available to this module. A downloader that is too slow wastes time. A limiter
that lets two requests through at once risks stats.nba.com blocking every user
of this package, not only this process.
"""

from __future__ import annotations

import builtins
import threading
from typing import Any, ClassVar

import pandas as pd
import pytest
import requests

from pippen.data import nba_api
from pippen.errors import MissingDependencyError


class _FakeClock:
    """A monotonic clock a test drives by hand."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeEndpoint:
    """Stands in for an nba_api endpoint class, which requests on construction."""

    calls: ClassVar[list[dict[str, Any]]] = []
    frames: ClassVar[list[pd.DataFrame]] = []
    raises: ClassVar[list[BaseException | None]] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).calls.append(kwargs)
        if type(self).raises:
            error = type(self).raises.pop(0)
            if error is not None:
                raise error

    def get_data_frames(self) -> list[pd.DataFrame]:
        return type(self).frames


@pytest.fixture(autouse=True)
def _reset_fake_endpoint() -> None:
    _FakeEndpoint.calls = []
    _FakeEndpoint.frames = [pd.DataFrame({"a": [1]})]
    _FakeEndpoint.raises = []


@pytest.fixture
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the retry budget so bounded behaviour is provable in milliseconds."""
    monkeypatch.setattr(nba_api, "_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(nba_api, "_BACKOFF_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(nba_api, "_BACKOFF_MAX_SECONDS", 0.0)


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=response)


# -------------------------------------------------------------------- limiter


def test_the_first_call_never_waits() -> None:
    clock = _FakeClock()
    nba_api.RateLimiter(1.0, clock=clock.time, sleep=clock.sleep).wait()
    assert clock.slept == []


def test_a_second_call_waits_out_the_remainder() -> None:
    clock = _FakeClock()
    limiter = nba_api.RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)
    limiter.wait()
    clock.advance(0.25)
    limiter.wait()
    assert clock.slept == [pytest.approx(0.75)]


def test_no_wait_when_the_interval_has_already_elapsed() -> None:
    clock = _FakeClock()
    limiter = nba_api.RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)
    limiter.wait()
    clock.advance(5.0)
    limiter.wait()
    assert clock.slept == []


def test_a_zero_interval_never_waits() -> None:
    clock = _FakeClock()
    limiter = nba_api.RateLimiter(0.0, clock=clock.time, sleep=clock.sleep)
    for _ in range(5):
        limiter.wait()
    assert clock.slept == []


def test_a_negative_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        nba_api.RateLimiter(-1.0)


def test_repeated_calls_are_paced_at_the_configured_interval() -> None:
    clock = _FakeClock()
    limiter = nba_api.RateLimiter(2.0, clock=clock.time, sleep=clock.sleep)
    for _ in range(4):
        limiter.wait()
    # Three waits after the first, each a full interval because no time passes
    # between them other than the sleeps themselves.
    assert clock.slept == [pytest.approx(2.0)] * 3


def test_concurrent_callers_are_serialised_not_all_let_through() -> None:
    # The race this exists to prevent: several threads read the same "last call"
    # timestamp, each decides no wait is needed, and all proceed at once. With
    # the lock held across the whole read-decide-sleep sequence, every thread
    # after the first must wait a full interval.
    clock = _FakeClock()
    lock = threading.Lock()

    def sleep(seconds: float) -> None:
        with lock:
            clock.slept.append(seconds)
            clock.now += seconds

    limiter = nba_api.RateLimiter(1.0, clock=clock.time, sleep=sleep)
    threads = [threading.Thread(target=limiter.wait) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert len(clock.slept) == 7
    assert all(seconds == pytest.approx(1.0) for seconds in clock.slept)


# ---------------------------------------------------------------- configuration


def test_the_rate_limit_defaults_to_one_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    # The project's compliance rule. A default that drifted would breach it
    # silently for anyone who never sets the variable.
    monkeypatch.delenv(nba_api.RATE_LIMIT_ENV_VAR, raising=False)
    assert nba_api._rate_limit_seconds() == 1.0
    assert nba_api.DEFAULT_RATE_LIMIT_SECONDS == 1.0


def test_the_rate_limit_can_be_raised_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(nba_api.RATE_LIMIT_ENV_VAR, "2.5")
    assert nba_api._rate_limit_seconds() == 2.5


def test_an_unparseable_rate_limit_says_what_to_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(nba_api.RATE_LIMIT_ENV_VAR, "one second")
    with pytest.raises(ValueError, match="is not a number") as caught:
        nba_api._rate_limit_seconds()
    message = str(caught.value)
    assert nba_api.RATE_LIMIT_ENV_VAR in message
    assert "for example" in message


def test_the_default_user_agent_identifies_the_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(nba_api.USER_AGENT_ENV_VAR, raising=False)
    assert "pippen" in nba_api._user_agent()


def test_the_user_agent_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(nba_api.USER_AGENT_ENV_VAR, "custom/1.0")
    assert nba_api._user_agent() == "custom/1.0"


def test_merging_headers_keeps_every_other_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # nba_api's defaults carry Host, Accept and Referer, which stats.nba.com
    # also checks. Replacing the mapping instead of merging would drop them.
    monkeypatch.setenv(nba_api.USER_AGENT_ENV_VAR, "custom/1.0")
    base = {"Host": "stats.nba.com", "Referer": "https://www.nba.com/", "User-Agent": "old"}
    merged = nba_api._merge_user_agent(base)
    assert merged["Host"] == "stats.nba.com"
    assert merged["Referer"] == "https://www.nba.com/"
    assert merged["User-Agent"] == "custom/1.0"


def test_merging_headers_does_not_mutate_the_input() -> None:
    base = {"User-Agent": "original"}
    nba_api._merge_user_agent(base)
    assert base["User-Agent"] == "original"


def test_the_shared_limiter_is_built_once() -> None:
    # A limiter rebuilt per call would forget when the last request went out,
    # which is the entire state it exists to hold.
    assert nba_api.default_limiter() is nba_api.default_limiter()


# ------------------------------------------------------------------- the hook


@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_the_response_hook_raises_on_an_error_status(status: int) -> None:
    response = requests.Response()
    response.status_code = status
    response.url = "https://stats.nba.com/stats/commonallplayers"
    with pytest.raises(requests.HTTPError):
        nba_api._raise_for_status_hook(response)


@pytest.mark.parametrize("status", [200, 204])
def test_the_response_hook_passes_a_success_through(status: int) -> None:
    response = requests.Response()
    response.status_code = status
    # The behaviour under test is that this does not raise. pytest fails the
    # test if it does, so no assertion on the return value is needed.
    nba_api._raise_for_status_hook(response)


# ------------------------------------------------------------- call_endpoint


def test_a_successful_call_returns_the_frame() -> None:
    frame = pd.DataFrame({"PERSON_ID": [203999]})
    _FakeEndpoint.frames = [frame]
    result = nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))
    assert result.equals(frame)


def test_the_requested_result_set_is_returned() -> None:
    # A few endpoints return several tables and the caller must say which.
    _FakeEndpoint.frames = [pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]})]
    result = nba_api.call_endpoint(
        _FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0), result_set=1
    )
    assert list(result.columns) == ["b"]


def test_parameters_are_forwarded_to_the_endpoint() -> None:
    nba_api.call_endpoint(
        _FakeEndpoint,
        headers={},
        limiter=nba_api.RateLimiter(0.0),
        season="2024-25",
        league_id="00",
    )
    assert _FakeEndpoint.calls[0]["season"] == "2024-25"
    assert _FakeEndpoint.calls[0]["league_id"] == "00"


def test_every_call_goes_through_the_limiter() -> None:
    clock = _FakeClock()
    limiter = nba_api.RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)
    nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=limiter)
    nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=limiter)
    assert clock.slept == [pytest.approx(1.0)]


def test_a_429_is_retried_then_reported_as_rate_limited(fast_retries: None) -> None:
    _FakeEndpoint.raises = [_http_error(429)] * 3
    with pytest.raises(nba_api.RateLimitedError) as caught:
        nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))
    assert nba_api.RATE_LIMIT_ENV_VAR in str(caught.value)
    assert len(_FakeEndpoint.calls) == 3


def test_a_429_that_clears_succeeds_without_raising(fast_retries: None) -> None:
    _FakeEndpoint.raises = [_http_error(429), None]
    result = nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))
    assert len(result) == 1
    assert len(_FakeEndpoint.calls) == 2


@pytest.mark.parametrize("status", [500, 503])
def test_a_server_error_is_transient(fast_retries: None, status: int) -> None:
    _FakeEndpoint.raises = [_http_error(status)] * 3
    with pytest.raises(nba_api.TransientAPIError):
        nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))


@pytest.mark.parametrize("status", [400, 403, 404])
def test_a_client_error_is_permanent_and_not_retried(fast_retries: None, status: int) -> None:
    # Retrying an unchanged request cannot fix a request that was wrong.
    _FakeEndpoint.raises = [_http_error(status)] * 3
    with pytest.raises(requests.HTTPError):
        nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))
    assert len(_FakeEndpoint.calls) == 1


@pytest.mark.parametrize("error", [requests.ConnectionError("reset"), requests.Timeout("slow")])
def test_a_connection_failure_is_transient(fast_retries: None, error: Exception) -> None:
    _FakeEndpoint.raises = [error] * 3
    with pytest.raises(nba_api.TransientAPIError):
        nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))


def test_retrying_gives_up_rather_than_looping_forever(fast_retries: None) -> None:
    # Bounded means bounded. An unbounded retry on a persistently failing
    # endpoint is indistinguishable from a hang.
    _FakeEndpoint.raises = [_http_error(429)] * 50
    with pytest.raises(nba_api.RateLimitedError):
        nba_api.call_endpoint(_FakeEndpoint, headers={}, limiter=nba_api.RateLimiter(0.0))
    assert len(_FakeEndpoint.calls) == 3


# ------------------------------------------------------------- missing extra


def test_a_missing_dependency_names_the_extra_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_nba_api(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("nba_api"):
            raise ImportError(f"No module named {name!r}")
        return original(name, *args, **kwargs)

    original = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", _no_nba_api)

    with pytest.raises(MissingDependencyError) as caught:
        nba_api.fetch_all_players("2024-25")
    message = str(caught.value)
    assert "sources" in message
    assert "uv sync" in message or "pip install" in message
