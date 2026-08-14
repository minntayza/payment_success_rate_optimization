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


def test_moving_blocks_preserve_adjacent_alternating_differences() -> None:
    optimized = _evaluated([("A", 10.0), ("B", 0.0), ("C", 10.0), ("D", 0.0)])
    baseline = _evaluated([("A", 0.0), ("B", 10.0), ("C", 0.0), ("D", 10.0)])

    interval = block_bootstrap_policy_difference(
        optimized,
        baseline,
        "realized_utility",
        seed=23,
        samples=500,
        block_length=2,
    )

    assert interval.estimate == 0.0
    assert interval.lower == 0.0
    assert interval.upper == 0.0


def test_bootstrap_aligns_policy_union_when_bucket_sets_differ() -> None:
    optimized = _evaluated([("A", 5.0), ("B", 8.0)])
    baseline = _evaluated([("B", 3.0), ("C", 2.0)])

    interval = block_bootstrap_policy_difference(
        optimized,
        baseline,
        "realized_utility",
        seed=29,
        samples=500,
        block_length=1,
    )

    assert interval.estimate == 8.0
