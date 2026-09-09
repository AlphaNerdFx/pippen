"""Resolution of on-disk locations for cached data and build artifacts.

Layout, relative to the data root::

    raw/         unmodified downloads, exactly as retrieved
    interim/     intermediate tables produced during processing
    processed/   analysis-ready tables published in dataset releases
    sources/     archived bibliography

The data root is chosen in this order:

1. the ``PIPPEN_DATA_DIR`` environment variable, if set;
2. a ``data/`` directory beside the repository root, when running from a checkout;
3. the platform user-cache directory, for installed copies of the package.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from platformdirs import user_cache_dir

ENV_VAR: Final = "PIPPEN_DATA_DIR"
_STAGES: Final = ("raw", "interim", "processed", "sources")


def _repo_data_dir() -> Path | None:
    """Return the checkout's ``data`` directory, or None when not in a checkout."""
    # paths.py -> pippen -> src -> repository root
    candidate = Path(__file__).resolve().parents[2] / "data"
    return candidate if candidate.is_dir() else None


def data_root() -> Path:
    """Return the root directory for cached data.

    Returns:
        The resolved data root. The directory is not created by this call.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    repo = _repo_data_dir()
    if repo is not None:
        return repo

    return Path(user_cache_dir("pippen", appauthor=False))


def stage_dir(stage: str, *, create: bool = False) -> Path:
    """Return the directory for one pipeline stage.

    Args:
        stage: One of ``raw``, ``interim``, ``processed`` or ``sources``.
        create: When true, create the directory and its parents if missing.

    Returns:
        The resolved stage directory.

    Raises:
        ValueError: If ``stage`` is not a recognised stage name.
    """
    if stage not in _STAGES:
        valid = ", ".join(_STAGES)
        raise ValueError(f"unknown stage {stage!r}; expected one of: {valid}")

    path = data_root() / stage
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def season_file(stage: str, dataset: str, season: int, *, create: bool = False) -> Path:
    """Return the Parquet path for one dataset and one season.

    Args:
        stage: Pipeline stage, as accepted by :func:`stage_dir`.
        dataset: Dataset name, for example ``play_by_play``.
        season: Season end year, for example 2024 for the 2023-24 season.
        create: When true, create the parent directory if missing.

    Returns:
        The full path to the season's Parquet file.
    """
    directory = stage_dir(stage) / dataset
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{dataset}_{season}.parquet"
