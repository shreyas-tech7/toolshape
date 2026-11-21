"""Intervals. Wilson for pass rates, a seeded bootstrap for means and paired differences."""

from __future__ import annotations

import math
import random
from statistics import fmean

Z95 = 1.959963984540054
BOOT_N = 2000
BOOT_SEED = 7


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def _percentiles(vals: list[float]) -> tuple[float, float]:
    vals = sorted(vals)
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(math.ceil(0.975 * (len(vals) - 1)))]
    return (lo, hi)


def bootstrap_mean(values: list[float], n: int = BOOT_N, seed: int = BOOT_SEED) -> tuple[float, float, float]:
    """Mean and a 95% percentile interval from resampling the values (here: tasks)."""
    if not values:
        return (float("nan"), float("nan"), float("nan"))
    rng = random.Random(seed)  # noqa: S311 - seeded, for statistics or synthetic data
    m = len(values)
    means = [fmean(rng.choices(values, k=m)) for _ in range(n)]
    lo, hi = _percentiles(means)
    return (fmean(values), lo, hi)


def paired_diff(a: list[float], b: list[float], n: int = BOOT_N, seed: int = BOOT_SEED) -> tuple[float, float, float]:
    """Mean of b - a over paired items, with a bootstrap interval that resamples the pairs."""
    if len(a) != len(b):
        raise ValueError("paired lists differ in length")
    return bootstrap_mean([y - x for x, y in zip(a, b, strict=True)], n, seed)
