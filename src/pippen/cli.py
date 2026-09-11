"""Command-line interface for pippen."""

from __future__ import annotations

from typing import Annotated

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from pippen import __version__
from pippen.data import hoopr
from pippen.data import validate as data_validate
from pippen.paths import ENV_VAR, data_root, dataset_file, season_file, stage_dir

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
def rapm(
    seasons: Annotated[str, typer.Option(help="Season range, for example 2015-2024.")],
    window: Annotated[int, typer.Option(help="Number of seasons per RAPM window.")] = 3,
) -> None:
    """Compute regularized adjusted plus-minus over a rolling multi-season window."""
    del seasons, window
    raise typer.Exit(_not_yet("rapm", "week 3-4 of the implementation plan"))


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
