"""Judge-level acceptance tests for the synthetic routing benchmark."""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from payment_dashboard.routing_evaluation import (
    chronological_split,
    evaluate_all_policies,
)
from payment_dashboard.routing_models import ObjectiveWeights
from payment_dashboard.routing_simulation import generate_routing_benchmark


@pytest.fixture
def hourly_contexts() -> pd.DataFrame:
    loads = pd.read_csv(
        Path(__file__).parent / "fixtures" / "routing_hourly_contexts.csv"
    )
    records: list[dict[str, object]] = []
    sequence = 0
    for load in loads.itertuples(index=False):
        bucket = pd.Timestamp(load[0]).as_unit("ns")
        for offset in range(int(load[1])):
            records.append(
                {
                    "Transaction ID": f"H{bucket.hour:02d}-T{offset:04d}",
                    "Timestamp": bucket + timedelta(seconds=int(offset)),
                    "Transaction Amount": float(25 + sequence % 3_000),
                    "Transaction Type": ("Transfer", "Deposit", "Withdrawal")[
                        sequence % 3
                    ],
                    "Device Used": ("Mobile", "Desktop")[sequence % 2],
                    "Fraud Flag": False,
                    "Latency (ms)": 20.0,
                }
            )
            sequence += 1
    return pd.DataFrame.from_records(records)


def test_split_never_divides_an_hourly_bucket(hourly_contexts: pd.DataFrame) -> None:
    split = chronological_split(hourly_contexts)
    bucket_sets = {
        name: set(
            pd.to_datetime(hourly_contexts.loc[index, "Timestamp"], utc=True).dt.floor(
                "h"
            )
        )
        for name, index in split.items()
    }
    assert bucket_sets["development"].isdisjoint(bucket_sets["validation"])
    assert bucket_sets["development"].isdisjoint(bucket_sets["test"])
    assert bucket_sets["validation"].isdisjoint(bucket_sets["test"])


def test_report_preserves_binding_and_infeasible_bucket_evidence(
    hourly_contexts: pd.DataFrame,
) -> None:
    report = evaluate_all_policies(
        generate_routing_benchmark(hourly_contexts), ObjectiveWeights()
    )
    assert report.capacity_binding_bucket_count >= 1
    assert report.infeasible_bucket_count >= 1
    optimizer_utility = report.metrics["milp_optimizer"].expected_utility
    baseline_utilities = [
        metric.expected_utility
        for name, metric in report.metrics.items()
        if name != "milp_optimizer"
    ]
    assert optimizer_utility > min(baseline_utilities)


def test_gateway_state_is_constant_within_hourly_bucket(
    hourly_contexts: pd.DataFrame,
) -> None:
    candidates = generate_routing_benchmark(hourly_contexts).candidates
    for _, rows in candidates.groupby(["time_bucket", "gateway_id"]):
        assert rows["available"].nunique() == 1
        assert rows["capacity"].nunique() == 1
        assert rows["is_degraded"].nunique() == 1
        assert rows["state_version"].nunique() == 1


def test_inserting_earlier_transaction_does_not_shift_gateway_incidents(
    hourly_contexts: pd.DataFrame,
) -> None:
    contexts = hourly_contexts.iloc[:50].copy()
    inserted = contexts.iloc[:1].copy()
    inserted["Transaction ID"] = "EARLIER"
    inserted["Timestamp"] = pd.Timestamp("2024-12-31T23:59:59Z")
    before = generate_routing_benchmark(contexts).candidates
    after = generate_routing_benchmark(pd.concat([inserted, contexts])).candidates
    keys = ["transaction_id", "gateway_id"]
    state = [
        "available",
        "capacity",
        "expected_success_probability",
        "expected_latency_ms",
        "is_degraded",
    ]
    shared_after = after.loc[after["transaction_id"].ne("EARLIER")]
    pd.testing.assert_frame_equal(
        before[keys + state].sort_values(keys).reset_index(drop=True),
        shared_after[keys + state].sort_values(keys).reset_index(drop=True),
    )
