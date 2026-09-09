"""Tests for the reproducibility helpers."""

from __future__ import annotations

import os
import random

import numpy as np
import pandas as pd
import pytest

from pippen.repro import DEFAULT_SEED, fingerprint, set_global_seeds


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [203999, 201939, 1628369],
            "rapm": [4.25, 6.10, 3.75],
            "minutes": [2400, 2210, 2530],
        }
    )


def test_fingerprint_is_stable_across_calls(frame: pd.DataFrame) -> None:
    assert fingerprint(frame) == fingerprint(frame)


def test_fingerprint_ignores_row_order(frame: pd.DataFrame) -> None:
    shuffled = frame.iloc[::-1].reset_index(drop=True)
    assert fingerprint(shuffled) == fingerprint(frame)


def test_fingerprint_ignores_column_order(frame: pd.DataFrame) -> None:
    reordered = frame[["minutes", "rapm", "player_id"]]
    assert fingerprint(reordered) == fingerprint(frame)


def test_fingerprint_detects_a_changed_value(frame: pd.DataFrame) -> None:
    changed = frame.copy()
    changed.loc[0, "rapm"] = 4.26
    assert fingerprint(changed) != fingerprint(frame)


def test_fingerprint_detects_a_dtype_promotion(frame: pd.DataFrame) -> None:
    promoted = frame.astype({"minutes": "float64"})
    assert fingerprint(promoted) != fingerprint(frame)


def test_fingerprint_can_restrict_to_columns(frame: pd.DataFrame) -> None:
    assert fingerprint(frame, columns=["rapm"]) != fingerprint(frame)


def test_fingerprint_rejects_an_unknown_column(frame: pd.DataFrame) -> None:
    with pytest.raises(KeyError):
        fingerprint(frame, columns=["not_a_column"])


def test_fingerprint_is_short_hex(frame: pd.DataFrame) -> None:
    value = fingerprint(frame)
    assert len(value) == 16
    assert set(value) <= set("0123456789abcdef")


@pytest.mark.determinism
def test_seeding_makes_sampling_repeatable() -> None:
    set_global_seeds(DEFAULT_SEED)
    first = (random.random(), float(np.random.rand()))

    set_global_seeds(DEFAULT_SEED)
    second = (random.random(), float(np.random.rand()))

    assert first == second


@pytest.mark.determinism
def test_seeding_pins_the_string_hash_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    # Python salts string hashing per process unless PYTHONHASHSEED is set.
    # Anything iterating a set of player names inherits that randomness.
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    set_global_seeds(4242)
    assert os.environ["PYTHONHASHSEED"] == "4242"


@pytest.mark.determinism
def test_different_seeds_give_different_draws() -> None:
    set_global_seeds(1)
    first = float(np.random.rand())
    set_global_seeds(2)
    assert first != float(np.random.rand())
