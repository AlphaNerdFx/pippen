"""Tests for the command-line interface."""

from __future__ import annotations

from typer.testing import CliRunner

from pippen import __version__
from pippen.cli import app

runner = CliRunner()


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_bare_invocation_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Reliability-adjusted NBA player impact" in result.stdout


def test_paths_lists_every_stage() -> None:
    result = runner.invoke(app, ["paths"])
    assert result.exit_code == 0
    for stage in ("raw", "interim", "processed", "sources"):
        assert stage in result.stdout


def test_unimplemented_commands_exit_nonzero() -> None:
    for argv in (["train"], ["evaluate"], ["rapm", "--seasons", "2015-2024"]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 2, argv
