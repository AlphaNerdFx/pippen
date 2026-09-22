"""Streamlit dashboard over the tables that ship inside the pippen wheel.

Reads the package directly rather than the HTTP service. The data is a 228 KB
Parquet file already on disk, so putting a network hop in front of it would add
a failure mode and a deployment dependency to buy nothing.

Four views, and the fourth is the one that matters: a page stating what this
metric cannot tell you, reachable without going looking for it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import pippen
from pippen import seasons

#: Diverging pair. Points per 100 possessions is signed and zero means
#: league-average, so polarity is the job. Blue above, red below, with the
#: chart's own baseline as the neutral midpoint.
ABOVE = "#1c5cab"
BELOW = "#a32d2d"

#: Sequential single hue for reliability, which is a magnitude from 0 to 1.
MAGNITUDE = "#3987e5"

#: More than this and a line chart stops being readable, and the categorical
#: palette runs out of separable hues.
MAX_COMPARE = 5

st.set_page_config(page_title="pippen", page_icon="🏀", layout="wide")


@st.cache_data
def ratings() -> pd.DataFrame:
    """Return the shipped RAPM table with labels a reader can trust.

    Two labels, because they answer different questions. ``window`` is the
    three-season span the ridge fit ran over. ``played`` is the span in which
    this player actually recorded a possession, which for 2,994 of the 5,427
    rows is shorter. Labelling a row by its window implies three seasons of
    evidence where there may be one.

    Both use the project's own season naming, so 2021 reads as 2021-22 rather
    than as a bare year that could mean either convention.
    """
    table = pippen.rapm_ratings().copy()
    table["window"] = [
        f"{seasons.describe(start)} to {seasons.describe(end)}"
        for start, end in zip(table["window_start"], table["window_end"], strict=True)
    ]
    table["played"] = [
        seasons.describe(first)
        if first == last
        else f"{seasons.describe(first)} to {seasons.describe(last)}"
        for first, last in zip(table["first_season"], table["last_season"], strict=True)
    ]
    return table


def _axis_labels(rows: pd.DataFrame) -> list[str]:
    """Return one unique label per row, leading with the seasons played.

    A player who played a single season appears in up to three windows, each
    giving a different estimate of that same season because the fit saw
    different team-mates. Those rows share a ``played`` span, so the window's
    final season disambiguates them rather than letting two bars collapse into
    one.
    """
    repeated = rows["played"].duplicated(keep=False)
    return [
        f"{played} · fit to {seasons.describe(end)}" if is_repeat else played
        for played, end, is_repeat in zip(rows["played"], rows["window_end"], repeated, strict=True)
    ]


@st.cache_data
def reliability() -> pd.DataFrame:
    """Return the measured split-half reliability of each box-score metric."""
    return pippen.metric_reliability()


def _named(table: pd.DataFrame) -> pd.DataFrame:
    """Drop the three rows whose player name the crosswalk could not resolve."""
    return table[table["player"].notna()]


def player_view() -> None:
    """One player across every window they appear in."""
    table = _named(ratings())
    names = sorted(table["player"].unique())
    default = names.index("Nikola Jokić") if "Nikola Jokić" in names else 0
    chosen = st.selectbox("Player", names, index=default)

    rows = table[table["player"] == chosen].sort_values("window_end")
    latest = rows.iloc[-1]

    # A headline number, not a one-bar bar chart.
    left, middle, right = st.columns(3)
    left.metric(f"Total, {latest['window']}", f"{latest['total']:+.2f}")
    middle.metric("Offensive", f"{latest['offensive']:+.2f}")
    right.metric("Defensive", f"{latest['defensive']:+.2f}")
    st.caption("Points per 100 possessions against a league-average replacement. Zero is average.")

    # Split the signed value into two columns so the diverging pair can be named
    # exactly. Streamlit assigns its own scheme when colour comes from a
    # category column, and polarity is too important to leave to a default.
    plot = rows[["total"]].copy()
    plot["span"] = _axis_labels(rows)
    plot["Above average"] = plot["total"].clip(lower=0)
    plot["Below average"] = plot["total"].clip(upper=0)
    st.bar_chart(
        plot,
        x="span",
        y=["Above average", "Below average"],
        color=[ABOVE, BELOW],
        height=320,
    )

    partial = int((rows["seasons_played"] < 3).sum())
    note = (
        f" In {partial} of them they played fewer than the window's three seasons,"
        " so the bar is labelled by the seasons they actually played."
        if partial
        else ""
    )
    st.caption(
        f"{chosen} appears in {len(rows)} fitted windows.{note} Possessions behind each estimate "
        "are in the table below: they are the precision signal, and no interval is published. "
        "See the Limits page."
    )
    st.dataframe(
        rows[
            ["played", "window", "seasons_played", "offensive", "defensive", "total", "possessions"]
        ]
        .rename(columns={"played": "seasons played", "window": "fitted over"})
        .set_index("seasons played"),
        use_container_width=True,
    )


def compare_view() -> None:
    """Several players over the same windows."""
    table = _named(ratings())
    names = sorted(table["player"].unique())
    seeded = [name for name in ("Nikola Jokić", "Stephen Curry", "Chris Paul") if name in names]
    chosen = st.multiselect("Players", names, default=seeded, max_selections=MAX_COMPARE)
    if not chosen:
        st.info("Pick at least one player.")
        return

    rows = table[table["player"].isin(chosen)]
    # Pivoted on the window rather than on seasons played: two players have
    # different tenures, and only the fitted window is a shared axis.
    wide = (
        rows.pivot_table(index=["window_end", "window"], columns="player", values="total")
        .sort_index()
        .droplevel("window_end")
    )
    st.line_chart(wide, height=380)
    st.caption(
        "Each line is one player's total impact per 100 possessions across three-season windows. "
        "Windows overlap, so consecutive points share two of their three seasons and move together "
        "more than independent seasons would."
    )
    st.dataframe(wide.round(2), use_container_width=True)


def reliability_view() -> None:
    """How repeatable each box-score metric was."""
    table = reliability()
    seasons = sorted(table["season"].unique())
    season = st.select_slider("Season", options=seasons, value=seasons[-1])
    rows = table[(table["season"] == season) & (table["rule"] == "random")]
    rows = rows.sort_values("reliability_at_82_games", ascending=False)

    st.bar_chart(
        rows, x="metric", y="reliability_at_82_games", color=MAGNITUDE, horizontal=True, height=420
    )
    st.caption(
        f"Split-half reliability in {season}, corrected to a full 82-game season by "
        "Spearman-Brown. Measured across every player meeting the minutes floor, not assigned."
    )

    st.subheader("Reliability runs against validity")
    st.markdown(
        """
Across this metric set, reliability correlates **-0.564** with correlation
against RAPM. The most repeatable metrics are the least related to winning.
Three-point rate is the most reliable metric here and one of the least related
to impact: a player who takes threes takes threes, consistently, whether or not
it helps.

This is why nothing in this codebase turns reliability into a weight. It is used
as a bound on how much of a metric a measurement-error model may attribute to
the latent quantity, and never as a multiplier.
See [ADR 0004](https://alphanerdfx.github.io/pippen/architecture/decisions/0004-reliability-bounds-never-weights/).

The scatter behind that -0.564 is not drawn here, because the per-metric
correlation against RAPM is not one of the columns that ships. Plotting it would
mean inventing the x-axis. Adding a `correlation_with_rapm` column to
`metric_reliability.parquet` is what would make the chart honest.
        """
    )
    st.dataframe(
        rows[["metric", "rho_half", "reliability_at_82_games", "players", "games_per_half"]]
        .set_index("metric")
        .round(3),
        use_container_width=True,
    )


def limits_view() -> None:
    """What this metric cannot tell you."""
    st.header("What this metric cannot tell you")
    st.markdown(
        """
### There is no interval, and that is deliberate

Every player page shows a number and no error bar. The project had one candidate
for an interval and withdrew it. A bootstrap standard error on a ridge
coefficient measures how much the penalty is pulling, not how much the data
knows: measured against this dataset, the standard error **rises** with
possessions, correlation +0.79. The narrowest bars would have sat on the
least-supported players, which inverts what a reader expects an error bar to
mean.

Use **possessions** instead. It is the sample size behind the estimate, it needs
no modelling assumption, and it moves the right way.

### The fusion did not work, and the project says so

The claim under test was that combining public metrics, weighted by how reliable
each one is, would predict next-season team net rating better than RAPM alone.
It does not, and it is not statistically distinguishable from RAPM
(p = 0.171). Ridge and a tuned LightGBM over every available metric land in the
same place, so the ceiling belongs to these inputs rather than to the method
used to combine them.

### Defence is the weak half

Box-score metrics capture defence badly. This is a property of the inputs, not
of this model, and it is why DBPM and PER are excluded entirely.

### A one-factor model of box-score metrics recovers player size

Fit a single latent factor to these metrics and it comes back as position, not
impact. Rebounds and blocks load together because tall players do both. That
finding is why the fusion model pins an anchor rather than letting the factor
float.

### Windows overlap

Ratings are computed over three-season windows, so consecutive windows share two
of their three seasons. Two adjacent points are not independent observations and
should not be read as a year-on-year change.
        """
    )

    st.subheader("Precision, shown rather than asserted")
    table = _named(ratings())
    st.scatter_chart(table, x="possessions", y="total", color=MAGNITUDE, height=400)
    st.caption(
        "Every shipped rating. The funnel is the precision story: estimates spread widely at low "
        "possession counts and converge as the sample grows. That spread is real and no interval "
        "is drawn over it."
    )


PAGES = {
    "Player": player_view,
    "Compare": compare_view,
    "Reliability": reliability_view,
    "Limits": limits_view,
}


def main() -> None:
    """Render the dashboard."""
    st.title("pippen")
    st.caption(
        "Player impact from pooled priors and estimated noise. "
        "RAPM computed from public play-by-play for NBA 2016-17 to 2024-25, validated at "
        "Spearman 0.914 against an independently built stint dataset."
    )
    choice = st.sidebar.radio("View", list(PAGES))
    st.sidebar.caption(f"pippen {pippen.__version__}")
    st.sidebar.markdown(
        "[Docs](https://alphanerdfx.github.io/pippen/) · "
        "[Source](https://github.com/AlphaNerdFx/pippen)"
    )
    PAGES[choice]()


if __name__ == "__main__":
    main()
