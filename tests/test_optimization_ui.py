from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from payment_dashboard.routing_models import (
    ObjectiveWeights,
    OptimizationReport,
    PolicyMetrics,
)
from payment_dashboard.ui import optimization


def test_optimization_ui_discloses_benchmark_and_policies(monkeypatch) -> None:
    metric = PolicyMetrics(
        transaction_count=10,
        assigned_count=9,
        unassigned_count=1,
        successful_count=8,
        success_rate=0.8,
        total_fee=4.0,
        cost_per_success=0.5,
        average_latency_ms=50,
        p95_latency_ms=80,
        expected_utility=88,
        realized_utility=75,
        capacity_violation_count=0,
        eligibility_violation_count=0,
        availability_violation_count=0,
        feasible_bucket_count=2,
        infeasible_bucket_count=1,
        degraded_transaction_count=2,
        degraded_success_rate=0.5,
        normal_success_rate=0.9,
    )
    report = OptimizationReport(
        metrics={"uniform_random": metric, "milp_optimizer": metric},
        decisions={},
        comparison=pd.DataFrame(
            [
                {
                    "policy": "uniform_random",
                    "success_rate": 0.8,
                    "total_fee": 5,
                    "average_latency_ms": 70,
                    "expected_utility": 75,
                },
                {
                    "policy": "milp_optimizer",
                    "success_rate": 0.9,
                    "total_fee": 4,
                    "average_latency_ms": 50,
                    "expected_utility": 88,
                },
            ]
        ),
        split_boundaries={
            "test": (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-02"))
        },
        weights=ObjectiveWeights(),
        simulation_version="routing-v1",
        capacity_binding_bucket_count=1,
        infeasible_bucket_count=1,
        unassigned_count=1,
        confidence_intervals={},
    )
    markdown = MagicMock()
    monkeypatch.setattr(optimization.st, "markdown", markdown)
    monkeypatch.setattr(optimization.st, "subheader", MagicMock())
    monkeypatch.setattr(optimization.st, "caption", MagicMock())
    monkeypatch.setattr(optimization.st, "dataframe", MagicMock())
    optimization.render_optimization_report(report)
    assert "SYNTHETIC BENCHMARK" in markdown.call_args_list[0].args[0]
    rendered = " ".join(str(call.args[0]) for call in markdown.call_args_list)
    captions = " ".join(
        str(call.args[0]) for call in optimization.st.caption.call_args_list
    )
    assert "Infeasible buckets" in rendered
    assert "Unassigned" in rendered
    assert "Test period" in captions
    assert "uncertainty" in captions.lower()
    assert optimization.st.dataframe.call_count >= 3
