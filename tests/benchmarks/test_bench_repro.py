"""Performance guards.

These do not assert correctness. They record how long an operation takes so that
continuous integration can say "this change made it slower" as a number rather
than as a hunch. The fingerprint runs over every published table, so it sits on
the path that gets slow first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

from pippen.repro import fingerprint, set_global_seeds

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

ROWS = 50_000


@pytest.fixture(scope="module")
def wide_frame() -> pd.DataFrame:
    """A table roughly the shape of one season of stint-level data."""
    set_global_seeds()
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "player_id": rng.integers(1_000, 2_000_000, ROWS),
            "season": rng.integers(2002, 2027, ROWS),
            "possessions": rng.integers(1, 40, ROWS),
            "margin": rng.normal(0, 12, ROWS),
            "minutes": rng.normal(24, 8, ROWS),
        }
    )


@pytest.mark.benchmark
def test_fingerprint_speed(benchmark: BenchmarkFixture, wide_frame: pd.DataFrame) -> None:
    result = benchmark(fingerprint, wide_frame)
    assert len(result) == 16
