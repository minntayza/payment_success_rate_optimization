"""Judge-level acceptance tests for the synthetic routing benchmark."""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from payment_dashboard.demo_data import generate_demo_transactions
from payment_dashboard.routing_config import BENCHMARK_TIMESTAMP_COLUMN, gateway_state
from payment_dashboard.routing_evaluation import (
    chronological_split,
    evaluate_all_policies,
)
from payment_dashboard.routing_models import ObjectiveWeights
from payment_dashboard.routing_repository import PandasRoutingRepository
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
    contexts = generate_routing_benchmark(hourly_contexts).contexts.sample(
        frac=1, random_state=11
    )
    split = chronological_split(contexts)
    bucket_sets = {
        name: set(
            pd.to_datetime(
                contexts.loc[index, BENCHMARK_TIMESTAMP_COLUMN], utc=True
            ).dt.floor("h")
        )
        for name, index in split.items()
    }
    assert bucket_sets["development"].isdisjoint(bucket_sets["validation"])
    assert bucket_sets["development"].isdisjoint(bucket_sets["test"])
    assert bucket_sets["validation"].isdisjoint(bucket_sets["test"])
    assert max(bucket_sets["development"]) < min(bucket_sets["validation"])
    assert max(bucket_sets["validation"]) < min(bucket_sets["test"])


def test_report_preserves_binding_capacity_evidence(
    hourly_contexts: pd.DataFrame,
) -> None:
    report = evaluate_all_policies(
        generate_routing_benchmark(hourly_contexts), ObjectiveWeights()
    )
    assert report.capacity_binding_bucket_count >= 1
    optimizer_utility = report.metrics["milp_optimizer"].expected_utility
    baseline_utilities = [
        metric.expected_utility
        for name, metric in report.metrics.items()
        if name != "milp_optimizer"
    ]
    assert optimizer_utility > min(baseline_utilities)


def test_builtin_demo_milp_improves_on_greedy_global_allocation(
    tmp_path: Path,
) -> None:
    report = PandasRoutingRepository(tmp_path).build_report(
        generate_demo_transactions(),
    )
    greedy = report.metrics["greedy_utility"]
    optimizer = report.metrics["milp_optimizer"]
    greedy_routes = set(
        map(
            tuple,
            report.decisions["greedy_utility"][["transaction_id", "gateway_id"]]
            .astype(str)
            .to_numpy(),
        )
    )
    optimizer_routes = set(
        map(
            tuple,
            report.decisions["milp_optimizer"][["transaction_id", "gateway_id"]]
            .astype(str)
            .to_numpy(),
        )
    )

    assert optimizer.assigned_count == greedy.assigned_count
    assert report.capacity_binding_bucket_count >= 1
    assert optimizer.expected_utility > greedy.expected_utility
    assert optimizer_routes != greedy_routes
    assert optimizer.degraded_transaction_count > 0
    assert optimizer.degraded_success_rate is not None


def test_gateway_state_is_constant_within_hourly_bucket(
    hourly_contexts: pd.DataFrame,
) -> None:
    candidates = generate_routing_benchmark(hourly_contexts).candidates
    for _, rows in candidates.groupby(["time_bucket", "gateway_id"]):
        assert rows["available"].nunique() == 1
        assert rows["capacity"].nunique() == 1
        assert rows["is_degraded"].nunique() == 1
        assert rows["state_version"].nunique() == 1


def test_gateway_state_distinguishes_routable_degradation_from_outage() -> None:
    degraded = gateway_state(pd.Timestamp("2025-01-01T15:00:00Z"), "Gateway A")
    unavailable = gateway_state(pd.Timestamp("2025-01-01T16:00:00Z"), "Gateway A")

    assert degraded.operational_state == "degraded"
    assert degraded.available is True
    assert 0 < degraded.capacity < 25
    assert degraded.success_adjustment < 0
    assert degraded.latency_multiplier > 1
    assert unavailable.operational_state == "unavailable"
    assert unavailable.available is False
    assert unavailable.capacity == 0


def test_shuffling_fixed_snapshot_does_not_shift_gateway_incidents(
    hourly_contexts: pd.DataFrame,
) -> None:
    contexts = hourly_contexts.iloc[:130].copy()
    before = generate_routing_benchmark(contexts).candidates
    after = generate_routing_benchmark(
        contexts.sample(frac=1, random_state=19)
    ).candidates
    keys = ["transaction_id", "gateway_id"]
    state = [
        "available",
        "capacity",
        "expected_success_probability",
        "expected_latency_ms",
        "is_degraded",
    ]
    pd.testing.assert_frame_equal(
        before[keys + state].sort_values(keys).reset_index(drop=True),
        after[keys + state].sort_values(keys).reset_index(drop=True),
    )


def test_two_source_hour_dataset_builds_multi_hour_benchmark(tmp_path: Path) -> None:
    count = 1_000
    source_timestamps = pd.date_range("2025-01-17T10:01:00Z", periods=count, freq="4s")
    contexts = pd.DataFrame(
        {
            "Transaction ID": [f"SOURCE-{index:04d}" for index in range(count)],
            "Timestamp": source_timestamps,
            "Transaction Amount": [100.0 + index % 2_500 for index in range(count)],
            "Transaction Type": [
                ("Transfer", "Deposit", "Withdrawal")[index % 3]
                for index in range(count)
            ],
            "Device Used": [("Mobile", "Desktop")[index % 2] for index in range(count)],
            "Fraud Flag": [False] * count,
            "Latency (ms)": [20.0] * count,
        }
    )

    report = PandasRoutingRepository(tmp_path).build_report(contexts)
    benchmark = generate_routing_benchmark(contexts)
    source_bucket_count = contexts["Timestamp"].dt.floor("h").nunique()
    benchmark_bucket_count = (
        benchmark.contexts[BENCHMARK_TIMESTAMP_COLUMN].dt.floor("h").nunique()
    )

    assert source_bucket_count == 2
    split = chronological_split(benchmark.contexts)
    test_bucket_count = (
        benchmark.contexts.loc[split["test"], BENCHMARK_TIMESTAMP_COLUMN]
        .dt.floor("h")
        .nunique()
    )

    assert benchmark_bucket_count >= 10
    assert test_bucket_count >= 4
    assert (
        report.split_boundaries["development"][1]
        < report.split_boundaries["validation"][0]
    )
    assert report.split_boundaries["validation"][1] < report.split_boundaries["test"][0]
    assert report.capacity_binding_bucket_count >= 1
    assert report.infeasible_bucket_count == 0
