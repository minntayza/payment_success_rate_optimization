"""Streamlit presentation for the synthetic routing benchmark."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from payment_dashboard.routing_models import OptimizationReport

POLICY_LABELS = {
    "uniform_random": "Uniform random",
    "round_robin": "Round robin",
    "best_static": "Best static gateway",
    "greedy_success": "Greedy success",
    "milp_optimizer": "Constrained MILP optimizer",
}


def render_optimization_report(report: OptimizationReport) -> None:
    """Render benchmark assumptions and comparable policy outcomes."""
    st.markdown("### SYNTHETIC BENCHMARK")
    st.caption(
        "Gateway alternatives, outcomes, fees, latency, incidents, and capacity "
        "are controlled simulation assumptions—not measurements of real processors."
    )
    st.caption(f"Run ID: {report.run_id}. Source: {report.source_label}.")
    st.subheader("Payment routing optimization")
    optimizer = report.metrics["milp_optimizer"]
    random = report.metrics["uniform_random"]
    st.markdown(
        f"**Optimizer expected utility:** {optimizer.expected_utility:,.1f}  |  "
        f"**Realized success:** {optimizer.success_rate:.1%}  |  "
        f"**Random realized success:** {random.success_rate:.1%}"
    )
    st.markdown(
        f"**Binding-capacity buckets:** {report.capacity_binding_bucket_count}  |  "
        f"**Infeasible buckets:** {report.infeasible_bucket_count}  |  "
        f"**Unassigned transactions:** {report.unassigned_count}"
    )
    display = report.comparison.copy()
    display["policy"] = display["policy"].map(POLICY_LABELS)
    display["Sample size"] = display["policy"].map(
        {
            POLICY_LABELS.get(name, name): metric.transaction_count
            for name, metric in report.metrics.items()
        }
    )
    display["success_rate"] = display["success_rate"].map(lambda value: f"{value:.1%}")
    display = display.rename(
        columns={
            "policy": "Policy",
            "success_rate": "Success rate",
            "total_fee": "Total fee",
            "average_latency_ms": "Average latency (ms)",
            "expected_utility": "Expected utility",
        }
    )
    st.dataframe(
        display[
            [
                "Policy",
                "Sample size",
                "Success rate",
                "Total fee",
                "Average latency (ms)",
                "Expected utility",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    baseline_rows = report.comparison.loc[
        report.comparison["policy"].ne("milp_optimizer")
    ].copy()
    baseline_rows["expected_utility_change"] = (
        optimizer.expected_utility - baseline_rows["expected_utility"]
    )
    baseline_rows["expected_utility_relative_change"] = baseline_rows[
        "expected_utility"
    ].map(
        lambda value: (
            (optimizer.expected_utility - float(value)) / abs(float(value))
            if float(value) != 0
            else None
        )
    )
    st.subheader("Change from baselines")
    st.dataframe(
        baseline_rows[
            [
                "policy",
                "expected_utility_change",
                "expected_utility_relative_change",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    period_evidence = pd.DataFrame(
        [
            {
                "Policy": POLICY_LABELS.get(name, name),
                "Normal success rate": metric.normal_success_rate,
                "Degraded success rate": metric.degraded_success_rate,
                "Degraded transactions": metric.degraded_transaction_count,
                "Feasible buckets": metric.feasible_bucket_count,
                "Infeasible buckets": metric.infeasible_bucket_count,
            }
            for name, metric in report.metrics.items()
        ]
    )
    st.subheader("Normal and degraded-period evidence")
    st.dataframe(period_evidence, hide_index=True, width="stretch")
    optimizer_decisions = report.decisions.get("milp_optimizer")
    if optimizer_decisions is not None and not optimizer_decisions.empty:
        utilization = (
            optimizer_decisions.groupby(["time_bucket", "gateway_id"])
            .agg(assignments=("transaction_id", "size"), capacity=("capacity", "first"))
            .reset_index()
        )
        utilization["utilization"] = (
            utilization["assignments"] / utilization["capacity"]
        )
        st.subheader("Optimizer gateway utilization")
        st.dataframe(utilization, hide_index=True, width="stretch")
        ordered_decisions = optimizer_decisions.sort_values(
            ["timestamp", "transaction_id"], kind="stable"
        ).copy()
        ordered_decisions["cumulative_expected_utility"] = ordered_decisions[
            "expected_utility"
        ].cumsum()
        ordered_decisions["cumulative_realized_utility"] = ordered_decisions[
            "realized_utility"
        ].cumsum()
        st.subheader("Chronological cumulative utility")
        st.line_chart(
            ordered_decisions.set_index("timestamp")[
                ["cumulative_expected_utility", "cumulative_realized_utility"]
            ]
        )
        st.subheader("Example optimizer decisions")
        st.dataframe(
            ordered_decisions[
                [
                    "transaction_id",
                    "timestamp",
                    "gateway_id",
                    "expected_success_probability",
                    "expected_fee",
                    "expected_latency_ms",
                    "expected_utility",
                    "realized_utility",
                ]
            ].head(10),
            hide_index=True,
            width="stretch",
        )
    st.caption(
        f"Objective: {report.weights.success_value:g}×success probability − "
        f"{report.weights.fee_weight:g}×fee − "
        f"{report.weights.latency_weight:g}×latency. "
        f"Version: {report.simulation_version}."
    )
    if "test" in report.split_boundaries:
        start, end = report.split_boundaries["test"]
        st.caption(f"Test period: {start} through {end} (complete UTC buckets).")
    intervals = report.confidence_intervals or {}
    if intervals:
        uncertain = sum(
            bool(getattr(interval, "contains_zero", False))
            for interval in intervals.values()
        )
        st.caption(
            "Realized-utility uncertainty uses paired complete-bucket bootstrap "
            f"intervals; {uncertain} comparison(s) include zero."
        )
    else:
        st.caption("Realized comparisons require uncertainty intervals before use.")
