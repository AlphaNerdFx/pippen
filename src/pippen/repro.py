"""Reproducibility helpers.

A published metric that cannot be recomputed is not a measurement, it is an
anecdote. Everything here exists so that a result can be pinned to an exact
value and checked again later, on another machine, by someone else.

Two tools:

* :func:`set_global_seeds` pins every source of randomness the pipeline touches.
* :func:`fingerprint` reduces a table to a short stable string, so a change in
  the numbers is a change in one visible token rather than a silent drift.
"""

from __future__ import annotations

import hashlib
import os
import random
from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Iterable

DEFAULT_SEED: Final = 20260910
_HASH_PREFIX_LENGTH: Final = 16


def set_global_seeds(seed: int = DEFAULT_SEED) -> None:
    """Seed every random number source the pipeline uses.

    Call this before anything that samples, shuffles, or bootstraps. Without it,
    two runs of the same code produce two different answers, and neither can be
    checked against the other.

    Args:
        seed: The seed to apply. Defaults to :data:`DEFAULT_SEED`.
    """
    random.seed(seed)
    np.random.seed(seed)
    # Python hashes strings with a per-process random salt unless told otherwise.
    # Anything that iterates a set of names inherits that randomness.
    os.environ["PYTHONHASHSEED"] = str(seed)


def fingerprint(frame: pd.DataFrame, *, columns: Iterable[str] | None = None) -> str:
    """Return a short stable hash of a table's contents.

    The hash ignores row order and column order, so a reordering that does not
    change the data does not change the fingerprint. It does not ignore dtypes:
    a column silently promoted from int to float is a real change and shows up.

    Args:
        frame: The table to fingerprint.
        columns: Restrict the hash to these columns. Defaults to all of them.

    Returns:
        The first 16 characters of a SHA-256 digest, as hexadecimal.

    Raises:
        KeyError: If a requested column is not present in the frame.
    """
    selected = frame if columns is None else frame[list(columns)]

    ordered = selected.reindex(sorted(selected.columns), axis=1)
    ordered = ordered.sort_values(by=list(ordered.columns), kind="stable")

    digest = hashlib.sha256()
    for name in ordered.columns:
        digest.update(name.encode("utf-8"))
        digest.update(str(ordered[name].dtype).encode("utf-8"))
        hashed = pd.util.hash_pandas_object(ordered[name], index=False)
        digest.update(np.asarray(hashed, dtype="uint64").tobytes())
    return digest.hexdigest()[:_HASH_PREFIX_LENGTH]
