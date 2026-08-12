"""Facade for building an optimization report from transaction contexts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from payment_dashboard.routing_evaluation import evaluate_all_policies
from payment_dashboard.routing_models import ObjectiveWeights, OptimizationReport
from payment_dashboard.routing_run_store import RoutingRunStore
from payment_dashboard.routing_simulation import generate_routing_benchmark


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
    ) -> OptimizationReport:
        benchmark = generate_routing_benchmark(contexts, seed=seed)
        report = evaluate_all_policies(benchmark, weights)
        selected_weights = report.weights
        manifest = self.run_store.save(
            contexts=benchmark.contexts,
            candidates=benchmark.candidates,
            outcomes=benchmark.potential_outcomes,
            report=report.comparison,
            configuration={
                "seed": seed,
                "simulation_version": benchmark.simulation_version,
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
        return replace(report, run_id=manifest.run_id)
