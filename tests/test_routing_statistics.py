"""Statistical evidence tests for routing policy comparisons."""

import pandas as pd

from payment_dashboard.routing_statistics import block_bootstrap_policy_difference


def _evaluated(values: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_bucket": [bucket for bucket, _ in values],
            "realized_utility": [value for _, value in values],
        }
    )


def test_constant_bucket_difference_has_collapsed_interval() -> None:
    optimized = _evaluated([("A", 5.0), ("B", 8.0)])
    baseline = _evaluated([("A", 3.0), ("B", 6.0)])
    interval = block_bootstrap_policy_difference(
        optimized, baseline, "realized_utility", seed=7, samples=500
    )
    assert interval.estimate == 4.0
    assert interval.lower == 4.0
    assert interval.upper == 4.0


def test_bucket_bootstrap_is_deterministic_for_fixed_seed() -> None:
    optimized = _evaluated([("A", 5.0), ("B", 9.0), ("C", 4.0)])
    baseline = _evaluated([("A", 4.0), ("B", 3.0), ("C", 5.0)])
    first = block_bootstrap_policy_difference(
        optimized, baseline, "realized_utility", seed=19, samples=500
    )
    second = block_bootstrap_policy_difference(
        optimized, baseline, "realized_utility", seed=19, samples=500
    )
    assert first == second
