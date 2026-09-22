"""HTTP service over the tables shipped inside the wheel.

Every response is a filtered read of a packaged Parquet file. Nothing is fitted,
loaded or computed per request, which is what keeps a free-tier cold start down
to process boot rather than numpyro importing jax.

No endpoint returns a per-player interval. The shipped ratings carry none, and
the one candidate this project had was withdrawn after Phase 2 measured that a
bootstrap standard error on a ridge coefficient rises with possessions rather
than falling. See
docs/architecture/decisions/0007-the-api-serves-shipped-tables-and-no-interval.md.
"""

from __future__ import annotations

from typing import Annotated, Any, Final

import pandas as pd
from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

import pippen

#: Measured split-half reliability of RAPM, from src/pippen/model/study.py.
#: A population figure, reported so a caller knows how much of the spread is
#: signal. It is not a per-player standard error and must not be used as one.
RAPM_RELIABILITY: Final = 0.796

#: Largest page a caller may request. Bounds response size on a free tier.
MAX_LIMIT: Final = 500

app = FastAPI(
    title="pippen",
    version=pippen.__version__,
    summary="Player impact from pooled priors and estimated noise.",
    description=(
        "Regularized Adjusted Plus-Minus for NBA 2016-17 to 2024-25, computed "
        "from public play-by-play and validated at Spearman 0.914 against an "
        "independently built stint dataset.\n\n"
        "**No endpoint returns a per-player interval.** The project withdrew "
        "its only candidate after measuring that a bootstrap standard error on "
        "a penalised coefficient tracks shrinkage rather than information. Use "
        "`possessions` as the per-player precision signal and `reliability` as "
        "the population one."
    ),
)


class Rating(BaseModel):
    """One player's impact over one multi-season window."""

    player_id: int
    #: Null for 3 of 5,427 shipped rows, where the ESPN to NBA crosswalk found
    #: no name for the id. All three sit under 20 possessions. The rows are
    #: returned rather than dropped so the gap is visible to a caller instead of
    #: silently changing the row count.
    player: str | None
    window_start: int = Field(description="First season of the window, NBA labelling.")
    window_end: int = Field(description="Last season of the window, NBA labelling.")
    offensive: float = Field(description="Points per 100 possessions added on offence.")
    defensive: float = Field(description="Points per 100 possessions prevented on defence.")
    total: float = Field(description="Offensive plus defensive.")
    possessions: float = Field(description="Possessions behind the estimate. The precision signal.")
    reliability: float = Field(
        default=RAPM_RELIABILITY,
        description=(
            "Measured split-half reliability of RAPM across the population. "
            "Not a per-player standard error."
        ),
    )


class Reliability(BaseModel):
    """How repeatable one box-score metric was in one season."""

    metric: str
    season: int = Field(description="hoopR label, naming the year the season ends.")
    rho_half: float = Field(description="Correlation between the two halves.")
    reliability_at_82_games: float = Field(
        description="Half correlation extended to a full season by Spearman-Brown."
    )
    players: int
    rule: str = Field(description="How the halves were split: random or odd_even.")


class Coefficient(BaseModel):
    """The measured share of free throw attempts that consume a possession."""

    season: int
    coefficient: float = Field(description="Measured value. The convention is 0.44.")
    convention: float = 0.44


class Health(BaseModel):
    """Liveness, and what data the process is serving."""

    status: str
    version: str
    first_season: int
    last_season: int
    ratings_rows: int


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Return a DataFrame as plain records the response models can validate."""
    # pandas types record keys as Hashable. They are column names, so they are
    # strings, and the models need that stated rather than assumed.
    return [
        {str(key): value for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


@app.get("/health", response_model=Health, tags=["meta"])
def health() -> Health:
    """Report that the process is up and which data it has."""
    return Health(
        status="ok",
        version=pippen.__version__,
        first_season=pippen.FIRST_RAPM_SEASON,
        last_season=pippen.LAST_RAPM_SEASON,
        ratings_rows=len(pippen.rapm_ratings()),
    )


@app.get("/ratings", response_model=list[Rating], tags=["ratings"])
def ratings(
    window_end: Annotated[
        int | None, Query(description="Last season of the window. Every window when omitted.")
    ] = None,
    min_possessions: Annotated[
        float, Query(ge=0, description="Drop players below this many possessions.")
    ] = 0.0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Maximum rows.")] = 50,
) -> list[Rating]:
    """Return players ranked by total impact per 100 possessions."""
    try:
        table = pippen.rapm_ratings(window_end=window_end, min_possessions=min_possessions)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    ranked = table.sort_values("total", ascending=False).head(limit)
    return [Rating.model_validate(row) for row in _rows(ranked)]


@app.get("/ratings/{player_id}", response_model=list[Rating], tags=["ratings"])
def ratings_for_player(
    player_id: Annotated[int, Path(description="NBA player id, as used by stats.nba.com.")],
) -> list[Rating]:
    """Return one player's impact across every window they appear in."""
    table = pippen.rapm_ratings()
    found = table[table["player_id"] == player_id]
    if found.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no player with id {player_id} in seasons "
                f"{pippen.FIRST_RAPM_SEASON} to {pippen.LAST_RAPM_SEASON}"
            ),
        )
    ordered = found.sort_values("window_end")
    return [Rating.model_validate(row) for row in _rows(ordered)]


@app.get("/reliability", response_model=list[Reliability], tags=["reliability"])
def reliability(
    season: Annotated[
        int | None, Query(description="hoopR season label. Every season when omitted.")
    ] = None,
    rule: Annotated[str, Query(description="random or odd_even.")] = "random",
) -> list[Reliability]:
    """Return the measured split-half reliability of each box-score metric.

    Reliability bounds how much of a metric is signal. It is never a weight:
    across this metric set it correlates -0.564 with correlation against RAPM.
    """
    try:
        table = pippen.metric_reliability(season=season, rule=rule)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    columns = list(Reliability.model_fields)
    return [Reliability.model_validate(row) for row in _rows(table[columns])]


@app.get("/possession-coefficient/{season}", response_model=Coefficient, tags=["reliability"])
def possession_coefficient(
    season: Annotated[int, Path(description="hoopR season label.")],
) -> Coefficient:
    """Return the measured free throw possession coefficient for one season.

    Every one of 25 measured seasons came out below the conventional 0.44,
    pooling at 0.4178.
    """
    return Coefficient(season=season, coefficient=pippen.possession_coefficient(season))
