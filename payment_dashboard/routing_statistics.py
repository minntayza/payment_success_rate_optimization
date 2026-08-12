"""Bucket-aware uncertainty calculations for routing comparisons."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    estimate: float
    lower: float
    upper: float
    contains_zero: bool


def block_bootstrap_policy_difference(
    optimized: pd.DataFrame,
    baseline: pd.DataFrame,
    metric: str,
    *,
    seed: int,
    samples: int = 2_000,
) -> ConfidenceInterval:
    """Estimate a paired difference by resampling complete time buckets."""
    if samples <= 0:
        raise ValueError("Bootstrap samples must be positive")
    optimized_buckets = optimized.groupby("time_bucket")[metric].sum()
    baseline_buckets = baseline.groupby("time_bucket")[metric].sum()
    if set(optimized_buckets.index) != set(baseline_buckets.index):
        raise ValueError("Policies must contain identical time buckets")
    differences = (
        optimized_buckets.sort_index() - baseline_buckets.sort_index()
    ).to_numpy(float)
    if not len(differences):
        return ConfidenceInterval(0.0, 0.0, 0.0, True)
    rng = np.random.default_rng(seed)
    draws = rng.choice(differences, size=(samples, len(differences)), replace=True)
    distribution = draws.sum(axis=1)
    estimate = float(differences.sum())
    lower, upper = np.quantile(distribution, [0.025, 0.975])
    return ConfidenceInterval(
        estimate,
        float(lower),
        float(upper),
        bool(lower <= 0 <= upper),
    )
