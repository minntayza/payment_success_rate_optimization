"""Chronological, leakage-resistant routing policy evaluation."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from payment_dashboard.routing_config import (
    BENCHMARK_TIMESTAMP_COLUMN,
    DEFAULT_WEIGHT_GRID,
)
from payment_dashboard.routing_models import (
    AllocationResult,
    ObjectiveWeights,
    OptimizationReport,
    PolicyMetrics,
    RoutingBenchmark,
    WeightSelection,
)
from payment_dashboard.routing_optimizer import optimize_routes
from payment_dashboard.routing_policies import (
    route_best_static,
    route_greedy_utility,
    route_random,
    route_round_robin,
)
from payment_dashboard.routing_statistics import block_bootstrap_policy_difference


def chronological_split(contexts: pd.DataFrame) -> dict[str, pd.Index]:
    ordered = contexts.sort_values(
        [BENCHMARK_TIMESTAMP_COLUMN, "Transaction ID"], kind="stable"
    )
    buckets = pd.to_datetime(ordered[BENCHMARK_TIMESTAMP_COLUMN], utc=True).dt.floor(
        "h"
    )
    unique_buckets = buckets.drop_duplicates().reset_index(drop=True)
    if len(unique_buckets) < 3:
        raise ValueError("Routing evaluation requires at least three time buckets")
    first = max(1, int(len(unique_buckets) * 0.6))
    second = max(first + 1, int(len(unique_buckets) * 0.8))
    second = min(second, len(unique_buckets) - 1)
    development_buckets = set(unique_buckets.iloc[:first])
    validation_buckets = set(unique_buckets.iloc[first:second])
    test_buckets = set(unique_buckets.iloc[second:])
    return {
        "development": ordered.index[buckets.isin(development_buckets)],
        "validation": ordered.index[buckets.isin(validation_buckets)],
        "test": ordered.index[buckets.isin(test_buckets)],
    }


def _metrics(
    allocation: AllocationResult,
    outcomes: pd.DataFrame,
    weights: ObjectiveWeights,
) -> tuple[PolicyMetrics, pd.DataFrame]:
    decisions = allocation.decisions
    evaluated = decisions.merge(
        outcomes, on=["transaction_id", "gateway_id"], validate="one_to_one"
    )
    count = len(evaluated)
    successes = int(evaluated["realized_success"].sum())
    total_fee = float(evaluated["expected_fee"].sum())
    expected_utility = float(
        (
            weights.success_value * evaluated["expected_success_probability"]
            - weights.fee_weight * evaluated["expected_fee"]
            - weights.latency_weight * evaluated["expected_latency_ms"]
        ).sum()
    )
    evaluated["realized_utility"] = (
        weights.success_value * evaluated["realized_success"].astype(float)
        - weights.fee_weight * evaluated["expected_fee"]
        - weights.latency_weight * evaluated["expected_latency_ms"]
    )
    evaluated["expected_utility"] = (
        weights.success_value * evaluated["expected_success_probability"]
        - weights.fee_weight * evaluated["expected_fee"]
        - weights.latency_weight * evaluated["expected_latency_ms"]
    )
    usage = evaluated.groupby(["time_bucket", "gateway_id"]).size()
    capacities = evaluated.groupby(["time_bucket", "gateway_id"])["capacity"].first()
    degraded = evaluated.loc[evaluated["is_degraded"]]
    normal = evaluated.loc[~evaluated["is_degraded"]]
    total_count = count + allocation.unassigned_count
    return PolicyMetrics(
        total_count,
        count,
        allocation.unassigned_count,
        successes,
        successes / total_count if total_count else 0.0,
        total_fee,
        total_fee / successes if successes else None,
        float(evaluated["expected_latency_ms"].mean()) if count else 0.0,
        float(evaluated["expected_latency_ms"].quantile(0.95)) if count else 0.0,
        expected_utility,
        float(evaluated["realized_utility"].sum()),
        int((usage > capacities).sum()),
        int((~evaluated["eligible"]).sum()),
        int((~evaluated["available"]).sum()),
        len(allocation.bucket_results) - allocation.infeasible_bucket_count,
        allocation.infeasible_bucket_count,
        len(degraded),
        float(degraded["realized_success"].mean()) if len(degraded) else None,
        float(normal["realized_success"].mean()) if len(normal) else None,
    ), evaluated


def select_objective_weights(
    candidates: pd.DataFrame,
    outcomes: pd.DataFrame,
    grid: tuple[ObjectiveWeights, ...],
) -> WeightSelection:
    """Select weights on expected validation utility using one business score."""
    if not grid:
        raise ValueError("Objective weight grid must not be empty")
    del outcomes
    business_weights = ObjectiveWeights()
    scores: list[tuple[ObjectiveWeights, float]] = []
    for weights in grid:
        result = optimize_routes(candidates, weights)
        evaluated = result.decisions
        score = float(
            (
                business_weights.success_value
                * evaluated["expected_success_probability"]
                - business_weights.fee_weight * evaluated["expected_fee"]
                - business_weights.latency_weight * evaluated["expected_latency_ms"]
            ).sum()
            - result.unassigned_count * business_weights.success_value
        )
        scores.append((weights, score))
    selected = max(enumerate(scores), key=lambda item: (item[1][1], -item[0]))[1][0]
    return WeightSelection(selected, tuple(scores))


def select_static_gateway(
    development: pd.DataFrame,
    weights: ObjectiveWeights,
) -> str:
    """Choose one preferred gateway by mean expected business utility."""
    scored = development.assign(
        _utility=(
            weights.success_value * development["expected_success_probability"]
            - weights.fee_weight * development["expected_fee"]
            - weights.latency_weight * development["expected_latency_ms"]
        )
    )
    return str(scored.groupby("gateway_id")["_utility"].mean().idxmax())


def evaluate_all_policies(
    benchmark: RoutingBenchmark,
    weights: ObjectiveWeights | None = None,
    *,
    weight_grid: tuple[ObjectiveWeights, ...] | None = None,
) -> OptimizationReport:
    split = chronological_split(benchmark.contexts)
    test_ids = set(benchmark.contexts.loc[split["test"], "Transaction ID"].astype(str))
    candidates = benchmark.candidates.loc[
        benchmark.candidates["transaction_id"].isin(test_ids)
    ].copy()
    validation_ids = set(
        benchmark.contexts.loc[split["validation"], "Transaction ID"].astype(str)
    )
    validation_candidates = benchmark.candidates.loc[
        benchmark.candidates["transaction_id"].isin(validation_ids)
    ].copy()
    validation_outcomes = benchmark.potential_outcomes.loc[
        benchmark.potential_outcomes["transaction_id"].isin(validation_ids)
    ].copy()
    configured_grid = weight_grid or tuple(
        ObjectiveWeights(*values) for values in DEFAULT_WEIGHT_GRID
    )
    weight_selection = (
        WeightSelection(weights, ())
        if weights is not None
        else select_objective_weights(
            validation_candidates, validation_outcomes, configured_grid
        )
    )
    selected_weights = weight_selection.selected
    development_ids = set(
        benchmark.contexts.loc[split["development"], "Transaction ID"].astype(str)
    )
    development = benchmark.candidates.loc[
        benchmark.candidates["transaction_id"].isin(development_ids)
    ]
    static_gateway = select_static_gateway(development, selected_weights)
    results = [
        route_random(candidates),
        route_round_robin(candidates),
        route_best_static(candidates, static_gateway),
        route_greedy_utility(candidates, selected_weights),
        optimize_routes(candidates, selected_weights),
    ]
    metrics: dict[str, PolicyMetrics] = {}
    decisions: dict[str, pd.DataFrame] = {}
    for result in results:
        metric, evaluated = _metrics(
            result, benchmark.potential_outcomes, selected_weights
        )
        metrics[result.policy_name] = metric
        decisions[result.policy_name] = evaluated
    comparison = pd.DataFrame(
        [{"policy": name, **asdict(metric)} for name, metric in metrics.items()]
    )
    boundaries = {}
    for name, indices in split.items():
        timestamps = pd.to_datetime(
            benchmark.contexts.loc[indices, BENCHMARK_TIMESTAMP_COLUMN], utc=True
        )
        boundaries[name] = (timestamps.min(), timestamps.max())
    optimizer_result = next(
        result for result in results if result.policy_name == "milp_optimizer"
    )
    confidence_intervals = {
        baseline.policy_name: block_bootstrap_policy_difference(
            decisions["milp_optimizer"],
            decisions[baseline.policy_name],
            "realized_utility",
            seed=42,
        )
        for baseline in results
        if baseline.policy_name != "milp_optimizer"
    }
    return OptimizationReport(
        metrics,
        decisions,
        comparison,
        boundaries,
        selected_weights,
        benchmark.simulation_version,
        optimizer_result.capacity_binding_bucket_count,
        optimizer_result.infeasible_bucket_count,
        optimizer_result.unassigned_count,
        weight_selection,
        confidence_intervals,
    )
