"""Streamlit presentation for the synthetic routing benchmark."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pandas as pd
import streamlit as st

from payment_dashboard.i18n import DEFAULT_LANGUAGE, Language, translate
from payment_dashboard.routing_models import OptimizationReport
from payment_dashboard.routing_statistics import ConfidenceInterval


def _policy_labels(language: Language) -> dict[str, str]:
    return {
        name: translate(f"optimization.policy.{name}", language)
        for name in (
            "uniform_random",
            "round_robin",
            "best_static",
            "greedy_utility",
            "milp_optimizer",
        )
    }


def render_optimization_report(
    report: OptimizationReport,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render benchmark assumptions and comparable policy outcomes."""
    policy_labels = _policy_labels(language)
    st.markdown(f"### {translate('optimization.eyebrow', language)}")
    st.caption(translate("optimization.assumptions", language))
    st.caption(translate("optimization.timeline", language))
    st.caption(
        translate(
            "optimization.run_source",
            language,
            run_id=report.run_id,
            source=report.source_label,
        )
    )
    st.subheader(translate("optimization.title", language))
    optimizer = report.metrics["milp_optimizer"]
    random = report.metrics["uniform_random"]
    st.markdown(
        translate(
            "optimization.summary",
            language,
            utility=optimizer.expected_utility,
            success=optimizer.success_rate,
            random=random.success_rate,
        )
    )
    st.markdown(
        translate(
            "optimization.constraints",
            language,
            binding=report.capacity_binding_bucket_count,
            infeasible=report.infeasible_bucket_count,
            unassigned=report.unassigned_count,
        )
    )
    greedy = report.metrics.get("greedy_utility")
    if greedy is not None:
        st.markdown(
            translate(
                "optimization.greedy_advantage",
                language,
                advantage=optimizer.expected_utility - greedy.expected_utility,
            )
        )
    display = report.comparison.copy()
    display["policy"] = display["policy"].map(policy_labels)
    sample_size = translate("optimization.column.sample_size", language)
    display[sample_size] = display["policy"].map(
        {
            policy_labels.get(name, name): metric.transaction_count
            for name, metric in report.metrics.items()
        }
    )
    display["success_rate"] = display["success_rate"].map(lambda value: f"{value:.1%}")
    display = display.rename(
        columns={
            "policy": translate("optimization.column.policy", language),
            "success_rate": translate("optimization.column.success_rate", language),
            "total_fee": translate("optimization.column.total_fee", language),
            "average_latency_ms": translate(
                "optimization.column.average_latency", language
            ),
            "expected_utility": translate(
                "optimization.column.expected_utility", language
            ),
        }
    )
    policy_column = translate("optimization.column.policy", language)
    success_column = translate("optimization.column.success_rate", language)
    fee_column = translate("optimization.column.total_fee", language)
    latency_column = translate("optimization.column.average_latency", language)
    utility_column = translate("optimization.column.expected_utility", language)
    st.dataframe(
        display[
            [
                policy_column,
                sample_size,
                success_column,
                fee_column,
                latency_column,
                utility_column,
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
    st.subheader(translate("optimization.change_title", language))
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
                translate("optimization.column.policy", language): policy_labels.get(
                    name, name
                ),
                translate("optimization.column.normal_success", language): (
                    metric.normal_success_rate
                ),
                translate("optimization.column.degraded_success", language): (
                    metric.degraded_success_rate
                ),
                translate("optimization.column.degraded_transactions", language): (
                    metric.degraded_transaction_count
                ),
                translate("optimization.column.feasible_buckets", language): (
                    metric.feasible_bucket_count
                ),
                translate("optimization.column.infeasible_buckets", language): (
                    metric.infeasible_bucket_count
                ),
            }
            for name, metric in report.metrics.items()
        ]
    )
    st.subheader(translate("optimization.period_title", language))
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
        st.subheader(translate("optimization.utilization_title", language))
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
        st.subheader(translate("optimization.cumulative_title", language))
        st.line_chart(
            ordered_decisions.set_index("timestamp")[
                ["cumulative_expected_utility", "cumulative_realized_utility"]
            ]
        )
        st.subheader(translate("optimization.examples_title", language))
        st.dataframe(
            ordered_decisions[
                [
                    "transaction_id",
                    "source_timestamp",
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
        translate(
            "optimization.objective",
            language,
            success=report.weights.success_value,
            fee=report.weights.fee_weight,
            latency=report.weights.latency_weight,
            version=report.simulation_version,
        )
    )
    if "test" in report.split_boundaries:
        start, end = report.split_boundaries["test"]
        st.caption(
            translate("optimization.test_period", language, start=start, end=end)
        )
    if not report.sensitivity_evidence.empty:
        st.subheader(translate("optimization.sensitivity_title", language))
        outcome_evidence = report.sensitivity_evidence.loc[
            report.sensitivity_evidence["scenario_type"].eq("outcome_redraw")
        ]
        allocation_evidence = report.sensitivity_evidence.loc[
            report.sensitivity_evidence["scenario_type"].eq("probability_reroute")
        ]
        st.markdown(f"**{translate('optimization.outcome_sensitivity', language)}**")
        st.dataframe(outcome_evidence, hide_index=True, width="stretch")
        st.markdown(f"**{translate('optimization.allocation_sensitivity', language)}**")
        st.dataframe(allocation_evidence, hide_index=True, width="stretch")
        st.caption(translate("optimization.sensitivity_caption", language))
    intervals = report.confidence_intervals or {}
    if intervals:
        typed_intervals = cast(Mapping[str, ConfidenceInterval], intervals)
        uncertainty = pd.DataFrame(
            [
                {
                    translate("optimization.column.baseline", language): (
                        policy_labels.get(name, name)
                    ),
                    translate("optimization.column.estimate", language): float(
                        interval.estimate
                    ),
                    translate("optimization.column.lower", language): float(
                        interval.lower
                    ),
                    translate("optimization.column.upper", language): float(
                        interval.upper
                    ),
                    translate("optimization.column.includes_zero", language): bool(
                        interval.contains_zero
                    ),
                }
                for name, interval in typed_intervals.items()
            ]
        )
        st.subheader(translate("optimization.uncertainty_title", language))
        st.dataframe(uncertainty, hide_index=True, width="stretch")
        st.caption(translate("optimization.uncertainty_caption", language))
    else:
        st.caption(translate("optimization.no_intervals", language))
