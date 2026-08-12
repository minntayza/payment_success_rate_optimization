from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from payment_dashboard.routing_evaluation import (
    chronological_split,
    evaluate_all_policies,
)
from payment_dashboard.routing_models import ObjectiveWeights, RoutingBenchmark
from payment_dashboard.routing_optimizer import optimize_routes
from payment_dashboard.routing_repository import PandasRoutingRepository
from payment_dashboard.routing_simulation import generate_routing_benchmark


@pytest.fixture
def contexts() -> pd.DataFrame:
    count = 20
    return pd.DataFrame(
        {
            "Transaction ID": [f"T{i:02d}" for i in range(count)],
            "Timestamp": pd.date_range("2025-01-01", periods=count, freq="h"),
            "Transaction Amount": [50 + i * 100 for i in range(count)],
            "Transaction Type": ["Transfer", "Deposit", "Withdrawal", "Transfer"] * 5,
            "Device Used": ["Mobile", "Desktop"] * 10,
            "Fraud Flag": [False] * count,
            "Latency (ms)": [20] * count,
        }
    )


def test_objective_weights_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ObjectiveWeights(fee_weight=-1)


def test_benchmark_is_deterministic_and_separates_hidden_outcomes(contexts) -> None:
    first = generate_routing_benchmark(contexts, seed=7)
    second = generate_routing_benchmark(contexts, seed=7)
    pd.testing.assert_frame_equal(first.candidates, second.candidates)
    assert len(first.candidates) == len(contexts) * 4
    assert "realized_success" not in first.candidates
    assert len(first.potential_outcomes) == len(contexts) * 4
    assert (
        first.candidates.groupby("transaction_id")["gateway_id"].nunique().eq(4).all()
    )


def test_gateway_tradeoffs_create_different_context_winners(contexts) -> None:
    candidates = generate_routing_benchmark(contexts).candidates
    winners = candidates.loc[
        candidates.groupby("transaction_id")["expected_success_probability"].idxmax(),
        "gateway_id",
    ]
    assert winners.nunique() >= 3


def test_optimizer_respects_one_choice_eligibility_and_capacity(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    result = optimize_routes(benchmark.candidates, ObjectiveWeights())
    assert result.is_feasible
    assert result.decisions["transaction_id"].is_unique
    assert result.decisions["eligible"].all()
    usage = result.decisions.groupby(["time_bucket", "gateway_id"]).size()
    capacity = result.decisions.groupby(["time_bucket", "gateway_id"])[
        "capacity"
    ].first()
    assert usage.le(capacity).all()


def test_chronological_evaluation_compares_optimizer_with_four_baselines(
    contexts,
) -> None:
    benchmark = generate_routing_benchmark(contexts)
    split = chronological_split(contexts)
    assert [len(split[name]) for name in ("development", "validation", "test")] == [
        12,
        4,
        4,
    ]
    report = evaluate_all_policies(benchmark, ObjectiveWeights())
    assert set(report.metrics) == {
        "uniform_random",
        "round_robin",
        "best_static",
        "greedy_success",
        "milp_optimizer",
    }
    assert report.simulation_version
    assert all(metric.transaction_count == 4 for metric in report.metrics.values())


def test_benchmark_rejects_realized_outcomes_in_policy_candidates(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    leaking = benchmark.candidates.assign(realized_success=True)
    with pytest.raises(ValueError, match="realized_success"):
        RoutingBenchmark(
            benchmark.contexts,
            leaking,
            benchmark.potential_outcomes,
            benchmark.simulation_version,
        )


def test_benchmark_rejects_duplicate_candidate_keys(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    duplicated = pd.concat([benchmark.candidates, benchmark.candidates.iloc[:1]])
    with pytest.raises(ValueError, match="candidate keys"):
        RoutingBenchmark(
            benchmark.contexts,
            duplicated,
            benchmark.potential_outcomes,
            benchmark.simulation_version,
        )


def test_benchmark_rejects_duplicate_outcome_keys(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    duplicated = pd.concat(
        [benchmark.potential_outcomes, benchmark.potential_outcomes.iloc[:1]]
    )
    with pytest.raises(ValueError, match="outcome keys"):
        RoutingBenchmark(
            benchmark.contexts,
            benchmark.candidates,
            duplicated,
            benchmark.simulation_version,
        )


def _optimizer_candidates() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    origin = pd.Timestamp("2025-01-01", tz="UTC").as_unit("ns")
    for hour, transaction_id in enumerate(("T1", "T2")):
        for gateway_id, probability in (("Gateway A", 0.9), ("Gateway B", 0.8)):
            records.append(
                {
                    "transaction_id": transaction_id,
                    "timestamp": origin + timedelta(hours=hour),
                    "time_bucket": origin + timedelta(hours=hour),
                    "gateway_id": gateway_id,
                    "eligible": True,
                    "available": True,
                    "capacity": 1,
                    "expected_success_probability": probability,
                    "expected_fee": 0.75,
                    "expected_latency_ms": 20.0,
                    "is_degraded": False,
                    "state_version": "test-state-v1",
                    "simulation_version": "test-v1",
                }
            )
    return pd.DataFrame.from_records(records)


def test_fee_ceiling_is_enforced_independently_per_bucket() -> None:
    result = optimize_routes(
        _optimizer_candidates(), ObjectiveWeights(), fee_ceiling=1.0
    )
    assert result.is_feasible
    assert len(result.decisions) == 2
    fees = result.decisions.groupby("time_bucket")["expected_fee"].sum()
    assert fees.le(1.0).all()


def test_infeasible_bucket_does_not_discard_feasible_bucket() -> None:
    candidates = _optimizer_candidates()
    second_bucket = candidates["transaction_id"].eq("T2")
    candidates.loc[second_bucket, "available"] = False
    result = optimize_routes(candidates, ObjectiveWeights())
    assert result.decisions["transaction_id"].tolist() == ["T1"]
    assert result.infeasible_bucket_count == 1
    assert result.unassigned_count == 1


def test_weight_selection_does_not_read_test_outcomes(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    grid = (
        ObjectiveWeights(100.0, 0.5, 0.005),
        ObjectiveWeights(100.0, 1.0, 0.01),
        ObjectiveWeights(100.0, 2.0, 0.02),
    )
    first = evaluate_all_policies(benchmark, weight_grid=grid)
    split = chronological_split(benchmark.contexts)
    test_ids = set(benchmark.contexts.loc[split["test"], "Transaction ID"].astype(str))
    changed_outcomes = benchmark.potential_outcomes.copy()
    changed_outcomes.loc[
        changed_outcomes["transaction_id"].isin(test_ids), "realized_success"
    ] = ~changed_outcomes.loc[
        changed_outcomes["transaction_id"].isin(test_ids), "realized_success"
    ]
    changed = RoutingBenchmark(
        benchmark.contexts,
        benchmark.candidates,
        changed_outcomes,
        benchmark.simulation_version,
    )
    second = evaluate_all_policies(changed, weight_grid=grid)
    assert first.weight_selection.selected == second.weight_selection.selected
    assert first.weight_selection.validation_scores


def test_repository_selects_default_weights_on_validation(contexts, tmp_path) -> None:
    report = PandasRoutingRepository(tmp_path).build_report(contexts)
    assert report.weight_selection is not None
    assert len(report.weight_selection.validation_scores) >= 2
