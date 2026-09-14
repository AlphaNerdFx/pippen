"""Command-line interface for pippen."""

from __future__ import annotations

from typing import Annotated

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from pippen import __version__
from pippen.data import hoopr, possession_coefficient
from pippen.data import validate as data_validate
from pippen.paths import ENV_VAR, data_root, dataset_file, season_file, stage_dir
from pippen.rapm import design as rapm_design
from pippen.rapm import pbp_source
from pippen.rapm import possessions as rapm_possessions
from pippen.rapm import ridge as rapm_ridge

app = typer.Typer(
    name="pippen",
    help="Reliability-adjusted NBA player impact estimates.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print the installed package version."""
    console.print(__version__)


@app.command()
def paths() -> None:
    """Show where pippen reads and writes data on this machine."""
    table = Table(title="pippen data layout")
    table.add_column("Stage", style="bold")
    table.add_column("Path")
    table.add_column("Exists", justify="center")

    table.add_row("root", str(data_root()), "yes" if data_root().is_dir() else "no")
    for stage in ("raw", "interim", "processed", "sources"):
        path = stage_dir(stage)
        table.add_row(stage, str(path), "yes" if path.is_dir() else "no")

    console.print(table)
    console.print(f"\nOverride the root by setting [bold]{ENV_VAR}[/bold].")


def _parse_seasons(spec: str) -> list[int]:
    """Turn a season specification into the list of season end years it names.

    Args:
        spec: Either a single season, ``"2024"``, or an inclusive range,
            ``"2015-2024"``. A season is its end year, so 2024 means 2023-24.

    Returns:
        Every season end year in the range, ascending.

    Raises:
        typer.BadParameter: If the specification does not parse, or names a
            range that runs backwards, or falls outside the seasons hoopR
            publishes.
    """
    parts = spec.split("-")
    try:
        bounds = [int(part) for part in parts]
    except ValueError:
        raise typer.BadParameter(
            f"{spec!r} is not a season or a season range. Use 2024, or 2015-2024."
        ) from None

    if len(bounds) == 1:
        first = last = bounds[0]
    elif len(bounds) == 2:
        first, last = bounds
    else:
        raise typer.BadParameter(f"{spec!r} has too many parts. Use 2024, or 2015-2024.")

    if first > last:
        raise typer.BadParameter(f"{spec!r} runs backwards. Put the earlier season first.")

    available = range(hoopr.PLAY_BY_PLAY_FIRST_SEASON, hoopr.PLAY_BY_PLAY_LAST_SEASON + 1)
    if first < available.start or last > available.stop - 1:
        raise typer.BadParameter(
            f"{spec!r} falls outside {available.start}-{available.stop - 1}, "
            "which is what hoopR publishes."
        )
    return list(range(first, last + 1))


@app.command()
def fetch(
    seasons: Annotated[
        str,
        typer.Option(help="A season, 2024, or an inclusive range, 2015-2024."),
    ],
    dataset: Annotated[
        str,
        typer.Option(help="Which hoopR table to download."),
    ] = "play_by_play",
    force: Annotated[
        bool,
        typer.Option(help="Re-download even when a valid file is already present."),
    ] = False,
) -> None:
    """Download one hoopR table for a range of seasons.

    Files already present and readable are skipped unless --force is given, so
    re-running after an interruption costs only the seasons that are missing.
    """
    wanted = _parse_seasons(seasons)
    if dataset not in hoopr.DATASETS:
        known = ", ".join(sorted(hoopr.DATASETS))
        console.print(f"[red]unknown dataset[/red] {dataset!r}. Known datasets: {known}")
        raise typer.Exit(code=2)

    if hoopr.is_master_dataset(dataset):
        # Published as one file covering every season, so the requested range
        # selects nothing. Downloading it once per season would store the same
        # file repeatedly.
        console.print(f"{dataset} is published as one file covering every season")
        results = [hoopr.download_master(dataset, force=force)]
        console.print(f"{results[0].status} {dataset}")
    else:
        results = hoopr.download_seasons(dataset, wanted, force=force, console=console)

    failed = [r for r in results if r.status == "failed"]
    downloaded = sum(1 for r in results if r.status == "downloaded")
    skipped = sum(1 for r in results if r.status == "skipped")
    console.print(
        f"\n{len(results)} season(s): {downloaded} downloaded, "
        f"{skipped} already present, {len(failed)} failed"
    )
    if failed:
        raise typer.Exit(code=1)


def _season_schedule(season: int) -> pd.DataFrame | None:
    """Return one season's rows from the master schedule, if it is on disk.

    The schedule is published as one table covering every season, so it is
    filtered here rather than stored per season.

    Args:
        season: Season end year.

    Returns:
        The season's schedule rows, or None if the master file has not been
        downloaded or carries no rows for that season.
    """
    path = dataset_file("raw", "schedules", "nba_schedule_master")
    if not path.exists():
        return None
    master = pd.read_parquet(path)
    if "season" not in master.columns:
        return None
    rows = master.loc[master["season"] == season]
    return rows if not rows.empty else None


@app.command()
def validate(
    seasons: Annotated[
        str,
        typer.Option(help="A season, 2024, or an inclusive range, 2015-2024."),
    ],
) -> None:
    """Check downloaded tables against each other, one season at a time.

    Reports every check for every season rather than stopping at the first
    failure, so a season's files can be fixed in one pass. Exits non-zero if
    any check failed. A skipped check does not fail the run, because a missing
    optional table is not the same as a wrong one, but it is reported so it
    cannot be mistaken for a pass.
    """
    any_failed = False
    for season in _parse_seasons(seasons):
        tables: dict[str, pd.DataFrame | None] = {}
        for dataset in ("play_by_play", "player_box", "team_box"):
            path = season_file("raw", dataset, season)
            tables[dataset] = pd.read_parquet(path) if path.exists() else None
        tables["schedules"] = _season_schedule(season)

        results = data_validate.validate_season(season, tables)
        console.print(f"\n[bold]{season}[/bold]")
        console.print(data_validate.summarise(results))
        any_failed = any_failed or any(r.status == "failed" for r in results)

    if any_failed:
        raise typer.Exit(code=1)


@app.command()
def coefficient(
    seasons: Annotated[
        str,
        typer.Option(help="A season, 2024, or an inclusive range, 2002-2026."),
    ],
) -> None:
    """Measure the possession coefficient per season from downloaded play-by-play.

    Possessions are conventionally estimated as FGA + 0.44 * FTA + TOV. The
    0.44 estimates what fraction of free throw attempts consume a possession.
    This measures that fraction instead of assuming it, one season at a time,
    so drift across rule eras is visible rather than averaged away.

    Seasons with no downloaded file are skipped with a note rather than
    treated as zero.
    """
    wanted = _parse_seasons(seasons)
    frames: dict[int, pd.DataFrame] = {}
    missing: list[int] = []
    for season in wanted:
        path = season_file("raw", "play_by_play", season)
        if path.exists():
            # Five columns of sixty-seven. Reading the whole file for every
            # season at once is several gigabytes of mostly unused data, and
            # Parquet is columnar so the rest is never touched on disk either.
            frames[season] = pd.read_parquet(
                path, columns=list(possession_coefficient._REQUIRED_COLUMNS)
            )
        else:
            missing.append(season)

    if missing:
        console.print(f"[yellow]no play-by-play on disk for:[/yellow] {_compact(missing)}")
    if not frames:
        console.print("Nothing to measure. Run [bold]pippen fetch[/bold] first.")
        raise typer.Exit(code=1)

    measured = possession_coefficient.estimate_coefficients_by_season(frames)

    table = Table(title="Possession coefficient by season")
    table.add_column("Season", justify="right")
    table.add_column("Measured", justify="right")
    table.add_column("vs 0.44", justify="right")
    table.add_column("Trips", justify="right")
    table.add_column("Attempts", justify="right")
    table.add_column("Unresolved", justify="right")
    for row in measured.itertuples():
        table.add_row(
            str(row.season),
            f"{row.coefficient:.4f}",
            f"{row.diff_from_conventional:+.4f}",
            f"{row.possession_ending_trips:,}",
            f"{row.free_throw_attempts:,}",
            str(row.excluded_unresolved),
        )
    console.print(table)

    values = measured["coefficient"]
    console.print(
        f"\nAcross {len(measured)} season(s): "
        f"min {values.min():.4f}, max {values.max():.4f}, "
        f"spread {values.max() - values.min():.4f}, mean {values.mean():.4f}"
    )
    console.print(
        "A spread near zero means 0.44 is simply the wrong constant. A spread "
        "that tracks rule changes means no single constant is right."
    )


def _compact(seasons: list[int]) -> str:
    """Render a list of seasons as contiguous ranges, so a gap is visible.

    Args:
        seasons: Season end years, ascending.

    Returns:
        A comma-separated list where runs are collapsed, for example
        ``2002-2005, 2009``.
    """
    if not seasons:
        return ""
    runs: list[tuple[int, int]] = [(seasons[0], seasons[0])]
    for season in seasons[1:]:
        first, last = runs[-1]
        if season == last + 1:
            runs[-1] = (first, season)
        else:
            runs.append((season, season))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


@app.command()
def possessions(
    seasons: Annotated[
        str,
        typer.Option(help="A season, 2024, or an inclusive range, 2016-2024."),
    ],
    force: Annotated[
        bool,
        typer.Option(help="Re-download even when a valid file is already present."),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(help="Stop after this many games per season. 0 means no limit."),
    ] = 0,
) -> None:
    """Download play-by-play with on-court lineups, the input to RAPM.

    This is the slow path. Unlike the hoopR bulk tables, which arrive as whole
    seasons in one file, possessions come one game at a time at one request per
    second, so a full season costs about twenty minutes and the nine covered
    seasons about three hours. Games already downloaded are skipped, so an
    interrupted run resumes where it stopped.
    """
    wanted = _parse_seasons(seasons)
    outside = [s for s in wanted if not pbp_source.FIRST_SEASON <= s <= pbp_source.LAST_SEASON]
    if outside:
        console.print(
            f"[red]not covered[/red]: {_compact(outside)}. data.nba.com serves "
            f"{pbp_source.FIRST_SEASON} to {pbp_source.LAST_SEASON}; see "
            f"docs/methodology/data-quirks.md"
        )
        raise typer.Exit(code=2)

    failures = 0
    for season in wanted:
        result = pbp_source.download_season(season, force=force, limit=limit if limit > 0 else None)
        console.print(result.summary())
        failures += len(result.failures)
        for failed in result.failures[:5]:
            console.print(f"  [yellow]{failed.game_id}[/yellow] {failed.error}")

    if failures:
        raise typer.Exit(code=1)


@app.command()
def stints(
    seasons: Annotated[str, typer.Option(help="Season range, for example 2016-2024.")],
) -> None:
    """Extract stints from downloaded play-by-play and cache them.

    Parsing is the expensive part of every later step, so the result is written
    to the interim stage once and read back by `rapm`.
    """
    for season in _parse_seasons(seasons):
        result = rapm_possessions.season_stints(season)
        path = rapm_possessions.write_season_stints(result)
        console.print(f"{result.summary()} -> {path.name}")
        if result.failures:
            console.print(f"  [yellow]{len(result.failures)} games failed to parse[/yellow]")


@app.command()
def rapm(
    seasons: Annotated[str, typer.Option(help="Season range, for example 2016-2024.")],
    window: Annotated[int, typer.Option(help="Number of seasons per RAPM window.")] = 3,
    top: Annotated[int, typer.Option(help="How many players to print.")] = 20,
) -> None:
    """Compute regularized adjusted plus-minus over a rolling multi-season window.

    Windows are pooled rather than fitted per season because a single season is
    too few possessions to separate teammates who rarely sit apart. A window of
    1 is allowed and is what the sensitivity check uses, not what gets
    published.
    """
    wanted = _parse_seasons(seasons)
    if window < 1:
        console.print("[red]window must be at least 1[/red]")
        raise typer.Exit(code=2)
    if window > len(wanted):
        console.print(f"[red]window {window} is longer than the {len(wanted)} seasons given[/red]")
        raise typer.Exit(code=2)

    frames = []
    for season in wanted:
        try:
            frames.append(rapm_possessions.read_season_stints(season))
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from exc

    for start in range(0, len(wanted) - window + 1):
        span = wanted[start : start + window]
        pooled = pd.concat(frames[start : start + window], ignore_index=True)
        design = rapm_design.build_design(pooled)
        console.print(f"\n[bold]{_compact(span)}[/bold]  {design.describe()}")
        if design.dropped_rows:
            console.print(f"  dropped {design.dropped_rows:,} stints with malformed lineups")

        fit, table = rapm_ridge.solve(design)
        best = table["weighted_mse"].min()
        console.print(f"  alpha {fit.alpha:,.0f}  intercept {fit.intercept:.2f}  cv mse {best:.1f}")

        ratings = fit.ratings().head(top)
        rendered = Table(title=f"top {top} by impact per 100 possessions, {_compact(span)}")
        rendered.add_column("player_id", justify="right")
        for name in ("offensive", "defensive", "total"):
            rendered.add_column(name, justify="right")
        for row in ratings.itertuples(index=False):
            rendered.add_row(
                str(row.player_id),
                f"{row.offensive:+.2f}",
                f"{row.defensive:+.2f}",
                f"{row.total:+.2f}",
            )
        console.print(rendered)


@app.command()
def train() -> None:
    """Fit the reliability-weighted measurement model."""
    raise typer.Exit(_not_yet("train", "week 5-7 of the implementation plan"))


@app.command()
def evaluate() -> None:
    """Compare PIPPEN against every input metric on next-season team net rating."""
    raise typer.Exit(_not_yet("evaluate", "week 5-7 of the implementation plan"))


def _not_yet(command: str, when: str) -> int:
    """Report that a command is scheduled but not yet implemented.

    Args:
        command: The command name.
        when: Human-readable description of when it lands.

    Returns:
        The process exit code to use.
    """
    console.print(f"[yellow]{command}[/yellow] is not implemented yet. It lands in {when}.")
    return 2
