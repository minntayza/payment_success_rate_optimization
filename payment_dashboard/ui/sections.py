"""Streamlit page section renderers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from payment_dashboard.analytics import summary_metrics
from payment_dashboard.i18n import translate
from payment_dashboard.models import DashboardState
from payment_dashboard.ui.charts import (
    FAILURE_DIMENSIONS,
    failure_breakdown_chart,
    gateway_success_chart,
    gateway_volume_chart,
    success_trend_chart,
)

RECENT_COLUMNS = [
    "Transaction ID",
    "Timestamp",
    "Bank Gateway",
    "Transaction Type",
    "Transaction Status",
    "Transaction Amount",
    "Device Used",
    "Latency (ms)",
    "Fraud Flag",
]


def render_kpis(state: DashboardState, language: str = "en") -> None:
    """Render the top-level KPI metric cards."""
    metrics = summary_metrics(state.display_frame)
    active_alerts = int(state.alerts["is_alert"].sum())

    cols = st.columns(5)
    cols[0].metric(
        translate("kpi.transactions", language), f"{metrics['transaction_count']:,}"
    )
    cols[1].metric(
        translate("kpi.success_rate", language), f"{metrics['success_rate']:.1%}"
    )
    cols[2].metric(translate("kpi.failed", language), f"{metrics['failed_count']:,}")
    cols[3].metric(
        translate("kpi.average_latency", language),
        f"{metrics['average_latency_ms']:.1f} ms",
    )
    cols[4].metric(translate("kpi.active_alerts", language), active_alerts)


def render_gateway_health(alerts: pd.DataFrame, language: str = "en") -> None:
    """Render the gateway health table with alert status."""
    st.subheader(translate("health.title", language))
    st.caption(translate("health.description", language))

    active = alerts.loc[alerts["is_alert"]]
    if active.empty:
        st.success(translate("health.no_alert", language))
    else:
        names = ", ".join(active["Bank Gateway"].astype(str))
        st.error(translate("health.action_required", language, names=names))

    display = alerts.copy()
    status_column = translate("sidebar.status", language)
    display[status_column] = display.apply(
        lambda row: (
            translate("health.insufficient_history", language)
            if not row["has_sufficient_history"]
            else (
                translate("health.alert", language)
                if row["is_alert"]
                else translate("health.healthy", language)
            )
        ),
        axis=1,
    )
    for column in ("baseline_rate", "rolling_rate", "drop"):
        display[column] = display[column].map(
            lambda v: "—" if pd.isna(v) else f"{v:.1%}"
        )
    display = display.rename(
        columns={
            "Bank Gateway": translate("table.gateway", language),
            "baseline_rate": translate("health.baseline", language),
            "rolling_rate": translate("health.latest_50", language),
            "drop": translate("health.drop", language),
        }
    )
    gateway_column = translate("table.gateway", language)
    baseline_column = translate("health.baseline", language)
    latest_50_column = translate("health.latest_50", language)
    drop_column = translate("health.drop", language)
    st.dataframe(
        display[
            [
                gateway_column,
                baseline_column,
                latest_50_column,
                drop_column,
                status_column,
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_gateway_performance(frame: pd.DataFrame, language: str = "en") -> None:
    """Render gateway success rate and volume charts side by side."""
    st.subheader(translate("charts.gateway_performance", language))
    left, right = st.columns(2)
    left.plotly_chart(
        gateway_success_chart(frame, language=language), use_container_width=True
    )
    right.plotly_chart(
        gateway_volume_chart(frame, language=language), use_container_width=True
    )


def render_success_trend(frame: pd.DataFrame, language: str = "en") -> None:
    """Render the success rate trend line chart."""
    st.subheader(translate("charts.success_trend", language))
    st.plotly_chart(
        success_trend_chart(frame, language=language), use_container_width=True
    )


def render_failure_analysis(frame: pd.DataFrame, language: str = "en") -> None:
    """Render failure breakdown charts by four dimensions."""
    st.subheader(translate("sections.failure_analysis", language))
    st.caption(translate("sections.failure_analysis_description", language))
    columns = st.columns(2)
    for index, (dimension, title) in enumerate(FAILURE_DIMENSIONS):
        chart = failure_breakdown_chart(frame, dimension, title, language=language)
        columns[index % 2].plotly_chart(chart, use_container_width=True)


def render_recent_transactions(frame: pd.DataFrame, language: str = "en") -> None:
    """Render the recent transactions table."""
    st.subheader(translate("table.recent_transactions", language))
    st.dataframe(
        frame.sort_values("Timestamp", ascending=False).head(25)[RECENT_COLUMNS],
        use_container_width=True,
        hide_index=True,
    )


def render_interpretation_guide(language: str = "en") -> None:
    """Render the expandable interpretation guide."""
    with st.expander(translate("guide.title", language)):
        st.markdown(translate("guide.content", language))
