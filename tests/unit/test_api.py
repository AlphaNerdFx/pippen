"""Tests for the HTTP service.

The service is a read layer over tables that ship inside the wheel, so the
interesting failures are not arithmetic. They are a filter that silently returns
everything, an unknown key that answers 200 with an empty list instead of 404,
and the response schema quietly growing a field this project decided not to
publish.

That last one has teeth. ADR 0007 records why no per-player interval ships: the
only candidate was a bootstrap standard error on a ridge coefficient, which
Phase 2 measured to rise with possessions rather than fall. A test asserts the
absence so a future contributor adding an `interval` field has to read the ADR
rather than discover the reasoning after publishing it.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="the api extra is not installed")

from fastapi.testclient import TestClient

import pippen
from pippen.api.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the app, sharing the module's cached tables."""
    return TestClient(app)


def test_health_reports_the_data_it_is_serving(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["version"] == pippen.__version__
    assert body["first_season"] == pippen.FIRST_RAPM_SEASON
    assert body["last_season"] == pippen.LAST_RAPM_SEASON
    assert body["ratings_rows"] == len(pippen.rapm_ratings())


def test_ratings_come_back_ranked_by_total(client: TestClient) -> None:
    rows = client.get("/ratings?limit=25").json()
    totals = [row["total"] for row in rows]
    assert totals == sorted(totals, reverse=True)


def test_the_limit_actually_limits(client: TestClient) -> None:
    assert len(client.get("/ratings?limit=3").json()) == 3


def test_a_limit_above_the_cap_is_refused(client: TestClient) -> None:
    """Unbounded paging is the one way this endpoint can return 5,427 rows."""
    assert client.get("/ratings?limit=99999").status_code == 422


def test_the_possession_floor_only_removes_rows(client: TestClient) -> None:
    everyone = client.get("/ratings?window_end=2024&limit=500").json()
    regulars = client.get("/ratings?window_end=2024&min_possessions=5000&limit=500").json()
    assert len(regulars) < len(everyone)
    assert all(row["possessions"] >= 5000 for row in regulars)


def test_a_window_that_was_not_computed_is_a_404(client: TestClient) -> None:
    response = client.get("/ratings?window_end=1999")
    assert response.status_code == 404
    assert "available windows end in" in response.json()["detail"]


def test_one_player_comes_back_in_window_order(client: TestClient) -> None:
    rows = client.get("/ratings/201939").json()
    assert rows, "Stephen Curry should appear in the shipped ratings"
    assert {row["player"] for row in rows} == {"Stephen Curry"}
    ends = [row["window_end"] for row in rows]
    assert ends == sorted(ends)


def test_an_unknown_player_is_a_404_naming_the_range(client: TestClient) -> None:
    response = client.get("/ratings/999999")
    assert response.status_code == 404
    assert str(pippen.FIRST_RAPM_SEASON) in response.json()["detail"]


def test_no_rating_response_carries_an_interval(client: TestClient) -> None:
    """ADR 0007. The absence is a decision, so it is pinned by a test."""
    forbidden = {"interval", "lower", "upper", "ci", "credible_interval", "standard_error", "se"}
    for url in ("/ratings?limit=1", "/ratings/201939"):
        for row in client.get(url).json():
            assert forbidden.isdisjoint(row), f"{url} published an interval field"


def test_a_rating_carries_the_population_reliability(client: TestClient) -> None:
    row = client.get("/ratings?limit=1").json()[0]
    assert row["reliability"] == pytest.approx(0.796)
    assert row["possessions"] > 0


def test_reliability_filters_by_season_and_rule(client: TestClient) -> None:
    rows = client.get("/reliability?season=2024&rule=random").json()
    assert rows
    assert {row["season"] for row in rows} == {2024}
    assert {row["rule"] for row in rows} == {"random"}


def test_an_unknown_rule_is_a_404(client: TestClient) -> None:
    response = client.get("/reliability?rule=nope")
    assert response.status_code == 404
    assert "unknown rule" in response.json()["detail"]


def test_the_possession_coefficient_is_below_the_convention(client: TestClient) -> None:
    body = client.get("/possession-coefficient/2024").json()
    assert body["convention"] == 0.44
    assert body["coefficient"] < body["convention"]


def test_the_openapi_schema_says_there_is_no_interval(client: TestClient) -> None:
    """A caller reading the docs should learn the limitation without asking."""
    description = client.get("/openapi.json").json()["info"]["description"]
    assert "per-player interval" in description
