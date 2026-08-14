from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from payment_dashboard.routing_evaluation import (
    chronological_split,
    evaluate_all_policies,
    select_objective_weights,
    select_static_gateway,
)
from payment_dashboard.routing_models import ObjectiveWeights, RoutingBenchmark
from payment_dashboard.routing_optimizer import optimize_routes
from payment_dashboard.routing_policies import route_greedy_utility
from payment_dashboard.routing_repository import PandasRoutingRepository
from payment_dashboard.routing_simulation import generate_routing_benchmark


@pytest.fixture
def contexts() -> pd.DataFrame:
    count = 400
    return pd.DataFrame(
        {
            "Transaction ID": [f"T{i:02d}" for i in range(count)],
            "Timestamp": pd.date_range("2025-01-01", periods=count, freq="h"),
            "Transaction Amount": [50 + (i % 20) * 100 for i in range(count)],
            "Transaction Type": [
                ("Transfer", "Deposit", "Withdrawal", "Transfer")[i % 4]
                for i in range(count)
            ],
            "Device Used": [("Mobile", "Desktop")[i % 2] for i in range(count)],
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


def test_benchmark_adds_stable_timeline_without_rewriting_source_time(
    contexts: pd.DataFrame,
) -> None:
    source_by_id = contexts.set_index("Transaction ID")["Timestamp"].sort_index()
    shuffled = contexts.sample(frac=1, random_state=7)

    first = generate_routing_benchmark(contexts)
    second = generate_routing_benchmark(shuffled)

    first_times = first.contexts.set_index("Transaction ID")[
        "Benchmark Timestamp"
    ].sort_index()
    second_times = second.contexts.set_index("Transaction ID")[
        "Benchmark Timestamp"
    ].sort_index()
    pd.testing.assert_series_equal(first_times, second_times)
    pd.testing.assert_series_equal(
        first.contexts.set_index("Transaction ID")["Timestamp"].sort_index(),
        pd.to_datetime(source_by_id, utc=True),
    )
    assert str(first_times.dt.tz) == "UTC"
    benchmark_nanoseconds = first_times.sort_values().astype("int64")
    assert benchmark_nanoseconds.diff().dropna().eq(60_000_000_000).all()
    assert {
        "timestamp",
        "source_timestamp",
    }.issubset(first.candidates.columns)
    assert first.candidates["timestamp"].ne(first.candidates["source_timestamp"]).any()


def test_existing_counterfactual_outcomes_survive_earlier_row_insertion(
    contexts: pd.DataFrame,
) -> None:
    original = contexts.iloc[:12].copy()
    original["Timestamp"] = pd.to_datetime(original["Timestamp"], utc=True)
    earlier = original.iloc[[0]].copy()
    earlier["Transaction ID"] = "EARLIER"
    earlier["Timestamp"] = pd.Timestamp("2024-12-01T00:00:00Z")

    before = generate_routing_benchmark(original, seed=17).potential_outcomes
    after = generate_routing_benchmark(
        pd.concat([earlier, original], ignore_index=True), seed=17
    ).potential_outcomes
    keys = ["transaction_id", "gateway_id"]

    pd.testing.assert_frame_equal(
        before.sort_values(keys).reset_index(drop=True),
        after.loc[after["transaction_id"].ne("EARLIER")]
        .sort_values(keys)
        .reset_index(drop=True),
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
    split = chronological_split(benchmark.contexts)
    assert [len(split[name]) for name in ("development", "validation", "test")] == [
        240,
        60,
        100,
    ]
    report = evaluate_all_policies(benchmark, ObjectiveWeights())
    assert set(report.metrics) == {
        "uniform_random",
        "round_robin",
        "best_static",
        "greedy_utility",
        "milp_optimizer",
    }
    assert report.simulation_version
    assert all(metric.transaction_count == 100 for metric in report.metrics.values())


def test_chronological_split_returns_labels_for_shuffled_reset_input() -> None:
    timestamps = pd.to_datetime(
        [
            "2025-01-01T00:00:00Z",
            "2025-01-01T00:00:30Z",
            "2025-01-01T01:00:00Z",
            "2025-01-01T01:00:30Z",
            "2025-01-01T02:00:00Z",
            "2025-01-01T02:00:30Z",
            "2025-01-01T03:00:00Z",
            "2025-01-01T03:00:30Z",
            "2025-01-01T04:00:00Z",
            "2025-01-01T04:00:30Z",
        ]
    )
    ordered = pd.DataFrame(
        {
            "Transaction ID": [f"T{index}" for index in range(10)],
            "Benchmark Timestamp": timestamps,
        }
    )
    shuffled = ordered.sample(frac=1, random_state=17).reset_index(drop=True)

    split = chronological_split(shuffled)

    assert set(shuffled.loc[split["development"], "Transaction ID"]) == {
        "T0",
        "T1",
        "T2",
        "T3",
        "T4",
        "T5",
    }
    assert set(shuffled.loc[split["validation"], "Transaction ID"]) == {"T6", "T7"}
    assert set(shuffled.loc[split["test"], "Transaction ID"]) == {"T8", "T9"}


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


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("expected_success_probability", np.nan, "success probabilities"),
        ("expected_success_probability", np.inf, "success probabilities"),
        ("expected_fee", np.nan, "fees"),
        ("expected_fee", np.inf, "fees"),
        ("expected_latency_ms", -np.inf, "latency"),
        ("capacity", np.inf, "capacity"),
        ("capacity", 1.5, "capacity"),
        ("capacity", 0, "capacity"),
    ],
)
def test_benchmark_rejects_invalid_solver_numeric_inputs(
    contexts: pd.DataFrame,
    column: str,
    value: float,
    message: str,
) -> None:
    benchmark = generate_routing_benchmark(contexts.iloc[:4])
    candidates = benchmark.candidates.copy()
    candidates[column] = candidates[column].astype(float)
    candidates.loc[candidates.index[0], column] = value

    with pytest.raises(ValueError, match=message):
        RoutingBenchmark(
            benchmark.contexts,
            candidates,
            benchmark.potential_outcomes,
            benchmark.simulation_version,
        )


@pytest.mark.parametrize(("column", "value"), [("eligible", pd.NA), ("available", 1)])
def test_benchmark_rejects_non_boolean_routing_flags(
    contexts: pd.DataFrame, column: str, value: object
) -> None:
    benchmark = generate_routing_benchmark(contexts.iloc[:4])
    candidates = benchmark.candidates.copy()
    candidates[column] = candidates[column].astype(object)
    candidates.loc[candidates.index[0], column] = value

    with pytest.raises(ValueError, match="boolean"):
        RoutingBenchmark(
            benchmark.contexts,
            candidates,
            benchmark.potential_outcomes,
            benchmark.simulation_version,
        )


def test_probability_sensitivity_reroutes_policies(tmp_path, contexts) -> None:
    report = PandasRoutingRepository(tmp_path).build_report(contexts)
    probability_rows = report.sensitivity_evidence.loc[
        report.sensitivity_evidence["scenario_type"].eq("probability_reroute")
    ]

    assert probability_rows["milp_changed_routes"].notna().all()
    assert probability_rows["greedy_changed_routes"].notna().all()
    assert set(probability_rows["scenario"]) == {
        "probability_shift_-0.03",
        "probability_shift_+0.03",
    }
    outcome_rows = report.sensitivity_evidence.loc[
        report.sensitivity_evidence["scenario_type"].eq("outcome_redraw")
    ]
    assert len(outcome_rows) == 3


def test_probability_sensitivity_keeps_unassigned_test_transactions(contexts) -> None:
    benchmark = generate_routing_benchmark(contexts)
    split = chronological_split(benchmark.contexts)
    unrouteable_id = str(
        benchmark.contexts.loc[split["test"], "Transaction ID"].iloc[0]
    )
    candidates = benchmark.candidates.copy()
    candidates.loc[candidates["transaction_id"].eq(unrouteable_id), "available"] = False
    changed = RoutingBenchmark(
        benchmark.contexts,
        candidates,
        benchmark.potential_outcomes,
        benchmark.simulation_version,
    )
    report = evaluate_all_policies(changed, ObjectiveWeights())

    evidence = PandasRoutingRepository._sensitivity_evidence(
        contexts,
        candidates,
        report,
        report.weights,
        42,
    )
    probability_rows = evidence.loc[evidence["scenario_type"].eq("probability_reroute")]

    assert report.metrics["milp_optimizer"].unassigned_count > 0
    assert (
        probability_rows["transaction_count"]
        .eq(report.metrics["milp_optimizer"].transaction_count)
        .all()
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


def test_unrouteable_transaction_keeps_earlier_decision_in_same_bucket() -> None:
    candidates = _optimizer_candidates()
    candidates["time_bucket"] = candidates["time_bucket"].min()
    candidates.loc[candidates["transaction_id"].eq("T2"), "available"] = False

    result = route_greedy_utility(candidates, ObjectiveWeights())

    assert result.decisions["transaction_id"].tolist() == ["T1"]
    assert result.bucket_results[0].unassigned_ids == ("T2",)


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


def test_weight_selection_scores_do_not_depend_on_realized_validation_draw(
    contexts: pd.DataFrame,
) -> None:
    benchmark = generate_routing_benchmark(contexts)
    split = chronological_split(benchmark.contexts)
    validation_ids = set(
        benchmark.contexts.loc[split["validation"], "Transaction ID"].astype(str)
    )
    candidates = benchmark.candidates.loc[
        benchmark.candidates["transaction_id"].isin(validation_ids)
    ]
    outcomes = benchmark.potential_outcomes.loc[
        benchmark.potential_outcomes["transaction_id"].isin(validation_ids)
    ]
    grid = (
        ObjectiveWeights(100.0, 0.5, 0.005),
        ObjectiveWeights(100.0, 2.0, 0.02),
    )

    successes = outcomes.assign(realized_success=True)
    failures = outcomes.assign(realized_success=False)

    assert select_objective_weights(candidates, successes, grid) == (
        select_objective_weights(candidates, failures, grid)
    )


def test_static_gateway_uses_complete_selected_objective() -> None:
    candidates = pd.DataFrame(
        {
            "gateway_id": ["Gateway A", "Gateway B"],
            "expected_success_probability": [0.95, 0.90],
            "expected_fee": [20.0, 0.0],
            "expected_latency_ms": [10.0, 10.0],
        }
    )

    assert select_static_gateway(candidates, ObjectiveWeights()) == "Gateway B"


def test_repository_selects_default_weights_on_validation(contexts, tmp_path) -> None:
    report = PandasRoutingRepository(tmp_path).build_report(contexts)
    assert report.weight_selection is not None
    assert len(report.weight_selection.validation_scores) >= 2


def test_repository_reports_seed_and_probability_sensitivity(
    contexts, tmp_path
) -> None:
    report = PandasRoutingRepository(tmp_path).build_report(contexts)

    assert set(report.sensitivity_evidence["scenario"]) == {
        "outcome_seed_42",
        "outcome_seed_43",
        "outcome_seed_44",
        "probability_shift_-0.03",
        "probability_shift_+0.03",
    }
    assert {
        "milp_expected_utility",
        "greedy_expected_utility",
        "expected_utility_advantage",
        "milp_realized_utility",
        "greedy_realized_utility",
    }.issubset(report.sensitivity_evidence.columns)
