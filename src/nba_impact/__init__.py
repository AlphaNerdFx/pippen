"""Reliability-adjusted NBA player impact estimates with calibrated uncertainty.

This package computes player impact from public play-by-play data. It treats
existing public impact metrics as noisy measurements of one unobserved quantity,
measures how reliable each measurement is, and fuses them by inverse-variance
weighting to produce RAIM (Reliability-Adjusted Impact Metric).

See the project documentation for the method and its limitations.
"""

from __future__ import annotations

__version__ = "0.0.0"

__all__ = ["__version__"]
