"""Smoke tests for the Streamlit dashboard.

The dashboard has real logic behind the widgets: a pivot for the comparison
view, a clip either side of zero for the diverging bars, and a filter that drops
the three rows whose player name the crosswalk could not resolve. None of that
is exercised by importing the module, so each view is rendered and checked for
an uncaught exception.

The assertion that matters is the last one. The Limits view is the reason this
dashboard exists rather than a table dump, and a refactor that quietly drops it
should fail here.
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit", reason="the dashboard extra is not installed")

from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest resolves a relative path against the file that calls it, which would
# look for tests/unit/dashboard/app.py.
APP = str(Path(__file__).resolve().parents[2] / "dashboard" / "app.py")
TIMEOUT = 60


def _run(view: str) -> AppTest:
    """Render one view and return the finished app."""
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    app.sidebar.radio[0].set_value(view).run()
    return app


@pytest.mark.parametrize("view", ["Player", "Compare", "Reliability", "Limits"])
def test_every_view_renders_without_raising(view: str) -> None:
    app = _run(view)
    assert not app.exception, f"{view} raised: {[e.value for e in app.exception]}"


def test_the_player_view_leads_with_a_number_not_a_chart() -> None:
    app = _run("Player")
    assert len(app.metric) == 3, "expected total, offensive and defensive as stat tiles"


def test_the_compare_view_refuses_to_plot_nothing() -> None:
    """An empty selection should say so rather than render an empty chart."""
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    app.sidebar.radio[0].set_value("Compare").run()
    app.multiselect[0].set_value([]).run()
    assert app.info, "clearing the selection should leave an explanatory message"


def test_the_limits_view_names_what_the_metric_cannot_do() -> None:
    app = _run("Limits")
    text = " ".join(block.value for block in app.markdown)
    # The three findings this project refuses to bury.
    assert "no error bar" in text or "no interval" in text.lower()
    assert "0.171" in text, "the negative result should be on the page"
    assert "possessions" in text
