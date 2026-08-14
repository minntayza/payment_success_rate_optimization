"""Bucket-aware uncertainty calculations for routing comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt

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
    block_length: int | None = None,
) -> ConfidenceInterval:
    """Estimate a paired difference with circular contiguous bucket blocks."""
    if samples <= 0:
        raise ValueError("Bootstrap samples must be positive")
    optimized_buckets = optimized.groupby("time_bucket")[metric].sum()
    baseline_buckets = baseline.groupby("time_bucket")[metric].sum()
    all_buckets = optimized_buckets.index.union(baseline_buckets.index).sort_values()
    differences = (
        optimized_buckets.reindex(all_buckets, fill_value=0.0)
        - baseline_buckets.reindex(all_buckets, fill_value=0.0)
    ).to_numpy(float)
    if not len(differences):
        return ConfidenceInterval(0.0, 0.0, 0.0, True)
    selected_block_length = block_length or max(1, ceil(sqrt(len(differences))))
    if not 1 <= selected_block_length <= len(differences):
        raise ValueError("Block length must be between 1 and the bucket count")
    rng = np.random.default_rng(seed)
    blocks_per_draw = ceil(len(differences) / selected_block_length)
    starts = rng.integers(
        0,
        len(differences),
        size=(samples, blocks_per_draw),
    )
    offsets = np.arange(selected_block_length)
    indices = (starts[..., np.newaxis] + offsets) % len(differences)
    draws = differences[indices].reshape(samples, -1)[:, : len(differences)]
    distribution = draws.sum(axis=1)
    estimate = float(differences.sum())
    lower, upper = np.quantile(distribution, [0.025, 0.975])
    return ConfidenceInterval(
        estimate,
        float(lower),
        float(upper),
        bool(lower <= 0 <= upper),
    )
