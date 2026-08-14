from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pandas as pd

from payment_dashboard.routing_models import (
    ObjectiveWeights,
    OptimizationReport,
    PolicyMetrics,
)
from payment_dashboard.routing_statistics import ConfidenceInterval
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
        metrics={
            "uniform_random": metric,
            "greedy_utility": replace(metric, expected_utility=75),
            "milp_optimizer": metric,
        },
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
                    "policy": "greedy_utility",
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
        confidence_intervals={
            "uniform_random": ConfidenceInterval(13.0, 2.0, 20.0, False),
            "greedy_utility": ConfidenceInterval(13.0, -1.0, 21.0, True),
        },
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
    assert "advantage over greedy" in rendered
    assert "13.0" in rendered
    assert "Test period" in captions
    assert "synthetic timeline" in captions.lower()
    assert "moving-block" in captions.lower()
    uncertainty = optimization.st.dataframe.call_args_list[-1].args[0]
    assert uncertainty.to_dict(orient="records") == [
        {
            "Baseline": "Uniform random",
            "Estimate": 13.0,
            "Lower 95%": 2.0,
            "Upper 95%": 20.0,
            "Includes zero": False,
        },
        {
            "Baseline": "Greedy utility",
            "Estimate": 13.0,
            "Lower 95%": -1.0,
            "Upper 95%": 21.0,
            "Includes zero": True,
        },
    ]
    assert optimization.st.dataframe.call_count >= 4


def test_optimization_ui_uses_myanmar_copy(monkeypatch) -> None:
    metric = PolicyMetrics(
        1,
        1,
        0,
        1,
        1.0,
        1.0,
        1.0,
        10.0,
        10.0,
        90.0,
        90.0,
        0,
        0,
        0,
        1,
        0,
        0,
        None,
        1.0,
    )
    report = OptimizationReport(
        metrics={"uniform_random": metric, "milp_optimizer": metric},
        decisions={},
        comparison=pd.DataFrame(
            [
                {
                    "policy": "milp_optimizer",
                    "success_rate": 1.0,
                    "total_fee": 1.0,
                    "average_latency_ms": 10.0,
                    "expected_utility": 90.0,
                }
            ]
        ),
        split_boundaries={},
        weights=ObjectiveWeights(),
        simulation_version="routing-v4",
    )
    markdown = MagicMock()
    subheader = MagicMock()
    caption = MagicMock()
    monkeypatch.setattr(optimization.st, "markdown", markdown)
    monkeypatch.setattr(optimization.st, "subheader", subheader)
    monkeypatch.setattr(optimization.st, "caption", caption)
    monkeypatch.setattr(optimization.st, "dataframe", MagicMock())

    optimization.render_optimization_report(report, language="my")

    rendered = " ".join(
        str(call.args[0])
        for mock in (markdown, subheader, caption)
        for call in mock.call_args_list
    )
    assert "ဖန်တီးထားသော စမ်းသပ် benchmark" in rendered
    assert "SYNTHETIC BENCHMARK" not in rendered
    assert "Payment routing optimization" not in rendered
    assert "Change from baselines" not in rendered
    table_columns = {
        str(column)
        for call in optimization.st.dataframe.call_args_list
        for column in call.args[0].columns
    }
    assert "Policy" not in table_columns
    assert "Normal success rate" not in table_columns
    assert "Feasible buckets" not in table_columns


def test_optimization_cumulative_chart_uses_shared_dark_theme(monkeypatch) -> None:
    """Optimization decisions must emit the same dark Plotly chart as the dashboard."""
    metric = PolicyMetrics(
        transaction_count=2,
        assigned_count=2,
        unassigned_count=0,
        successful_count=2,
        success_rate=1.0,
        total_fee=1.0,
        cost_per_success=0.5,
        average_latency_ms=20.0,
        p95_latency_ms=25.0,
        expected_utility=10.0,
        realized_utility=10.0,
        capacity_violation_count=0,
        eligibility_violation_count=0,
        availability_violation_count=0,
        feasible_bucket_count=1,
        infeasible_bucket_count=0,
        degraded_transaction_count=0,
        degraded_success_rate=None,
        normal_success_rate=1.0,
    )
    report = OptimizationReport(
        metrics={"uniform_random": metric, "milp_optimizer": metric},
        decisions={
            "milp_optimizer": pd.DataFrame(
                [
                    {
                        "time_bucket": "2025-01-01T00:00:00Z",
                        "gateway_id": "Gateway A",
                        "transaction_id": "txn-1",
                        "capacity": 2,
                        "timestamp": pd.Timestamp("2025-01-01T00:00:00Z"),
                        "source_timestamp": pd.Timestamp("2025-01-01T00:00:00Z"),
                        "expected_utility": 4.0,
                        "realized_utility": 3.0,
                        "expected_success_probability": 0.9,
                        "expected_fee": 0.5,
                        "expected_latency_ms": 20.0,
                    },
                    {
                        "time_bucket": "2025-01-01T00:00:00Z",
                        "gateway_id": "Gateway A",
                        "transaction_id": "txn-2",
                        "capacity": 2,
                        "timestamp": pd.Timestamp("2025-01-01T00:01:00Z"),
                        "source_timestamp": pd.Timestamp("2025-01-01T00:01:00Z"),
                        "expected_utility": 6.0,
                        "realized_utility": 7.0,
                        "expected_success_probability": 0.9,
                        "expected_fee": 0.5,
                        "expected_latency_ms": 20.0,
                    },
                ]
            )
        },
        comparison=pd.DataFrame(
            [
                {
                    "policy": "milp_optimizer",
                    "success_rate": 1.0,
                    "total_fee": 1.0,
                    "average_latency_ms": 20.0,
                    "expected_utility": 10.0,
                }
            ]
        ),
        split_boundaries={},
        weights=ObjectiveWeights(),
        simulation_version="routing-v1",
    )
    plotly_chart = MagicMock()
    monkeypatch.setattr(optimization.st, "markdown", MagicMock())
    monkeypatch.setattr(optimization.st, "subheader", MagicMock())
    monkeypatch.setattr(optimization.st, "caption", MagicMock())
    monkeypatch.setattr(optimization.st, "dataframe", MagicMock())
    monkeypatch.setattr(optimization.st, "line_chart", MagicMock())
    monkeypatch.setattr(optimization.st, "plotly_chart", plotly_chart)

    optimization.render_optimization_report(report)

    assert plotly_chart.called
    chart = plotly_chart.call_args.args[0]
    assert chart.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert chart.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert chart.layout.xaxis.gridcolor == "#24364B"
    assert list(chart.data[0].y) == [4.0, 10.0]
