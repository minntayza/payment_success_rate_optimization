"""Facade for building an optimization report from transaction contexts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from payment_dashboard.routing_config import (
    BENCHMARK_TIMELINE_FREQUENCY,
    BENCHMARK_TIMELINE_START,
    BENCHMARK_TIMESTAMP_COLUMN,
    ROUTING_STATE_VERSION,
    ROUTING_TIMELINE_VERSION,
)
from payment_dashboard.routing_evaluation import evaluate_all_policies
from payment_dashboard.routing_models import (
    ObjectiveWeights,
    OptimizationReport,
)
from payment_dashboard.routing_optimizer import optimize_routes
from payment_dashboard.routing_policies import route_greedy_utility
from payment_dashboard.routing_run_store import RoutingRunStore
from payment_dashboard.routing_simulation import generate_routing_benchmark

PERSISTED_CONTEXT_COLUMNS = [
    "Transaction ID",
    "Timestamp",
    BENCHMARK_TIMESTAMP_COLUMN,
    "Transaction Amount",
    "Transaction Type",
    "Device Used",
]


class PandasRoutingRepository:
    def __init__(self, run_root: Path | None = None) -> None:
        self.run_store = RoutingRunStore(
            run_root or Path("data/processed/routing_runs")
        )

    def build_report(
        self,
        contexts: pd.DataFrame,
        weights: ObjectiveWeights | None = None,
        seed: int = 42,
        *,
        source_label: str = "synthetic temporally expanded benchmark",
    ) -> OptimizationReport:
        benchmark = generate_routing_benchmark(contexts, seed=seed)
        report = evaluate_all_policies(benchmark, weights)
        selected_weights = report.weights
        sensitivity_evidence = self._sensitivity_evidence(
            contexts,
            benchmark.candidates,
            report,
            selected_weights,
            seed,
        )
        manifest = self.run_store.save(
            contexts=benchmark.contexts[PERSISTED_CONTEXT_COLUMNS].copy(),
            candidates=benchmark.candidates,
            outcomes=benchmark.potential_outcomes,
            report=report.comparison,
            configuration={
                "seed": seed,
                "context_source": source_label,
                "simulation_version": benchmark.simulation_version,
                "state_version": ROUTING_STATE_VERSION,
                "context_columns": PERSISTED_CONTEXT_COLUMNS,
                "timeline": {
                    "version": ROUTING_TIMELINE_VERSION,
                    "start": BENCHMARK_TIMELINE_START,
                    "frequency": BENCHMARK_TIMELINE_FREQUENCY,
                },
                "split_boundaries": {
                    name: [str(start), str(end)]
                    for name, (start, end) in report.split_boundaries.items()
                },
                "weights": {
                    "success_value": selected_weights.success_value,
                    "fee_weight": selected_weights.fee_weight,
                    "latency_weight": selected_weights.latency_weight,
                },
            },
        )
        return replace(
            report,
            run_id=manifest.run_id,
            source_label=source_label,
            sensitivity_evidence=sensitivity_evidence,
        )

    @staticmethod
    def _sensitivity_evidence(
        contexts: pd.DataFrame,
        candidates: pd.DataFrame,
        report: OptimizationReport,
        weights: ObjectiveWeights,
        seed: int,
    ) -> pd.DataFrame:
        policy_frames = {
            name: report.decisions[name]
            for name in ("milp_optimizer", "greedy_utility")
        }

        def expected_utility(frame: pd.DataFrame) -> float:
            probabilities = frame["expected_success_probability"]
            return float(
                (
                    weights.success_value * probabilities
                    - weights.fee_weight * frame["expected_fee"]
                    - weights.latency_weight * frame["expected_latency_ms"]
                ).sum()
            )

        def realized_utility(frame: pd.DataFrame, outcomes: pd.DataFrame) -> float:
            evaluated = frame.drop(columns="realized_success").merge(
                outcomes,
                on=["transaction_id", "gateway_id"],
                validate="one_to_one",
            )
            return float(
                (
                    weights.success_value * evaluated["realized_success"].astype(float)
                    - weights.fee_weight * evaluated["expected_fee"]
                    - weights.latency_weight * evaluated["expected_latency_ms"]
                ).sum()
            )

        records: list[dict[str, object]] = []
        test_start, test_end = report.split_boundaries["test"]
        candidate_timestamps = pd.to_datetime(candidates["timestamp"], utc=True)
        test_candidates = candidates.loc[
            candidate_timestamps.between(test_start, test_end, inclusive="both")
        ].copy()
        transaction_count = int(test_candidates["transaction_id"].nunique())
        for outcome_seed in range(seed, seed + 3):
            outcomes = generate_routing_benchmark(
                contexts,
                seed=outcome_seed,
            ).potential_outcomes
            optimizer_frame = policy_frames["milp_optimizer"]
            greedy_frame = policy_frames["greedy_utility"]
            records.append(
                {
                    "scenario": f"outcome_seed_{outcome_seed}",
                    "scenario_type": "outcome_redraw",
                    "transaction_count": transaction_count,
                    "milp_expected_utility": expected_utility(optimizer_frame),
                    "greedy_expected_utility": expected_utility(greedy_frame),
                    "expected_utility_advantage": (
                        expected_utility(optimizer_frame)
                        - expected_utility(greedy_frame)
                    ),
                    "milp_realized_utility": realized_utility(
                        optimizer_frame,
                        outcomes,
                    ),
                    "greedy_realized_utility": realized_utility(
                        greedy_frame,
                        outcomes,
                    ),
                    "milp_changed_routes": 0,
                    "greedy_changed_routes": 0,
                }
            )

        def route_changes(original: pd.DataFrame, shifted: pd.DataFrame) -> int:
            before = original.set_index("transaction_id")["gateway_id"]
            after = shifted.set_index("transaction_id")["gateway_id"]
            aligned = before.index.union(after.index)
            return int(before.reindex(aligned).ne(after.reindex(aligned)).sum())

        for shift in (-0.03, 0.03):
            shifted = test_candidates.copy()
            shifted["expected_success_probability"] = (
                shifted["expected_success_probability"].add(shift).clip(0.50, 0.99)
            )
            optimizer_frame = optimize_routes(shifted, weights).decisions
            greedy_frame = route_greedy_utility(shifted, weights).decisions
            optimizer_expected = expected_utility(optimizer_frame)
            greedy_expected = expected_utility(greedy_frame)
            records.append(
                {
                    "scenario": f"probability_shift_{shift:+.2f}",
                    "scenario_type": "probability_reroute",
                    "transaction_count": transaction_count,
                    "milp_expected_utility": optimizer_expected,
                    "greedy_expected_utility": greedy_expected,
                    "expected_utility_advantage": (
                        optimizer_expected - greedy_expected
                    ),
                    "milp_realized_utility": report.metrics[
                        "milp_optimizer"
                    ].realized_utility,
                    "greedy_realized_utility": report.metrics[
                        "greedy_utility"
                    ].realized_utility,
                    "milp_changed_routes": route_changes(
                        policy_frames["milp_optimizer"], optimizer_frame
                    ),
                    "greedy_changed_routes": route_changes(
                        policy_frames["greedy_utility"], greedy_frame
                    ),
                }
            )
        return pd.DataFrame.from_records(records)
