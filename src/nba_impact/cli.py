"""Command-line interface for nba-impact."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from nba_impact import __version__
from nba_impact.paths import ENV_VAR, data_root, stage_dir

app = typer.Typer(
    name="nba-impact",
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
    """Show where nba-impact reads and writes data on this machine."""
    table = Table(title="nba-impact data layout")
    table.add_column("Stage", style="bold")
    table.add_column("Path")
    table.add_column("Exists", justify="center")

    table.add_row("root", str(data_root()), "yes" if data_root().is_dir() else "no")
    for stage in ("raw", "interim", "processed", "sources"):
        path = stage_dir(stage)
        table.add_row(stage, str(path), "yes" if path.is_dir() else "no")

    console.print(table)
    console.print(f"\nOverride the root by setting [bold]{ENV_VAR}[/bold].")


@app.command()
def fetch(
    seasons: Annotated[
        str,
        typer.Option(help="Season range as END_YEAR-END_YEAR, for example 2015-2024."),
    ],
) -> None:
    """Download play-by-play and box scores for a range of seasons."""
    del seasons
    raise typer.Exit(_not_yet("fetch", "week 1-2 of the implementation plan"))


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
    """Compare RAIM against every input metric on next-season team net rating."""
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
