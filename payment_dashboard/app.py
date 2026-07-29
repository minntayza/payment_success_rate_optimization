from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.analytics import (
    add_latency_band,
    apply_filters,
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)
from payment_dashboard.data_loader import DataValidationError, load_transactions

DEFAULT_DATA_PATH = Path("data/processed/transactions_with_gateways.csv")
CHART_COLORS = ["#2563EB", "#06B6D4", "#8B5CF6", "#F59E0B"]


def build_dashboard_state(
    full_frame: pd.DataFrame,
    replay_count: int,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> dict[str, object]:
    replay_frame = full_frame.iloc[:replay_count].copy()
    display_frame = apply_filters(
        replay_frame,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )
    display_frame = add_latency_band(display_frame)
    return {
        "alert_input": replay_frame,
        "display_frame": display_frame,
        "alerts": evaluate_alerts(full_frame, replay_frame),
    }


def _apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 90% 0%, rgba(37, 99, 235, 0.10), transparent 30rem),
                #f7f9fc;
        }
        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
        }
        [data-testid="stMetricLabel"] {
            color: #475569;
        }
        [data-testid="stMetricValue"] {
            color: #0f172a;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
        }
        h1, h2, h3 {
            color: #0f172a;
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_alerts(alerts: pd.DataFrame) -> None:
    active_alerts = alerts.loc[alerts["is_alert"]]
    if active_alerts.empty:
        st.success("No gateway currently exceeds the 10-point alert threshold.")
    else:
        names = ", ".join(active_alerts["Bank Gateway"].astype(str))
        st.error(f"Action required: success-rate degradation detected for {names}.")

    alert_display = alerts.copy()
    alert_display["Status"] = alert_display.apply(
        lambda row: (
            "Insufficient history"
            if not row["has_sufficient_history"]
            else ("Alert" if row["is_alert"] else "Healthy")
        ),
        axis=1,
    )
    for column in ("baseline_rate", "rolling_rate", "drop"):
        alert_display[column] = alert_display[column].map(
            lambda value: "—" if pd.isna(value) else f"{value:.1%}"
        )
    alert_display = alert_display.rename(
        columns={
            "Bank Gateway": "Gateway",
            "baseline_rate": "Baseline",
            "rolling_rate": "Latest 50",
            "drop": "Drop",
        }
    )
    st.dataframe(
        alert_display[["Gateway", "Baseline", "Latest 50", "Drop", "Status"]],
        use_container_width=True,
        hide_index=True,
    )


def _render_gateway_charts(frame: pd.DataFrame) -> None:
    gateway_data = gateway_summary(frame)
    left, right = st.columns(2)

    success_chart = px.bar(
        gateway_data,
        x="Bank Gateway",
        y="success_rate",
        color="Bank Gateway",
        color_discrete_sequence=CHART_COLORS,
        title="Success rate by gateway",
        range_y=[0, 1],
        text_auto=".1%",
    )
    success_chart.update_layout(showlegend=False, yaxis_tickformat=".0%")
    left.plotly_chart(success_chart, use_container_width=True)

    volume_chart = px.bar(
        gateway_data,
        x="Bank Gateway",
        y="transaction_count",
        color="Bank Gateway",
        color_discrete_sequence=CHART_COLORS,
        title="Transaction volume by gateway",
        text_auto=True,
    )
    volume_chart.update_layout(showlegend=False)
    right.plotly_chart(volume_chart, use_container_width=True)


def _render_failure_charts(frame: pd.DataFrame) -> None:
    dimensions = (
        ("Fraud Flag", "Fraud flag"),
        ("Latency Band", "Latency band"),
        ("Device Used", "Device"),
        ("Transaction Type", "Transaction type"),
    )
    chart_columns = st.columns(2)
    for index, (dimension, title) in enumerate(dimensions):
        breakdown = failure_breakdown(frame, dimension)
        chart = px.bar(
            breakdown,
            x=dimension,
            y="failed_count",
            title=f"Failures by {title.lower()}",
            color_discrete_sequence=["#F97316"],
            text_auto=True,
        )
        chart.update_layout(showlegend=False)
        chart_columns[index % 2].plotly_chart(chart, use_container_width=True)


def render_app() -> None:
    st.set_page_config(
        page_title="Payment Success Monitor",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_page_style()

    st.title("Payment Success Monitor")
    st.markdown(
        "Track transaction health, compare simulated gateways, and investigate "
        "payment failures from one local dashboard."
    )
    st.caption(
        "Academic demo · Gateway labels are randomly simulated and do not "
        "represent real bank or gateway performance."
    )

    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    try:
        full_frame = load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(f"Unable to load dashboard data: {exc}")
        st.info(
            "Generate the prepared dataset with "
            "`python -m payment_dashboard.prepare_data` and refresh this page."
        )
        st.stop()

    st.sidebar.header("Dashboard controls")
    st.sidebar.caption(
        "Replay transactions chronologically, then narrow the visible analysis."
    )
    replay_count = st.sidebar.slider(
        "Replayed transactions",
        min_value=1,
        max_value=len(full_frame),
        value=len(full_frame),
        help="Controls how many chronological transactions have arrived.",
    )
    replay_progress = replay_count / len(full_frame)
    st.sidebar.progress(replay_progress)
    st.sidebar.caption(f"{replay_count:,} of {len(full_frame):,} transactions")

    st.sidebar.subheader("Display filters")
    gateways = st.sidebar.multiselect(
        "Gateway",
        sorted(full_frame["Bank Gateway"].unique()),
        placeholder="All gateways",
    )
    transaction_types = st.sidebar.multiselect(
        "Transaction type",
        sorted(full_frame["Transaction Type"].unique()),
        placeholder="All transaction types",
    )
    devices = st.sidebar.multiselect(
        "Device",
        sorted(full_frame["Device Used"].unique()),
        placeholder="All devices",
    )
    statuses = st.sidebar.multiselect(
        "Status",
        sorted(full_frame["Transaction Status"].unique()),
        placeholder="All statuses",
    )

    minimum_date = full_frame["Timestamp"].min().date()
    maximum_date = full_frame["Timestamp"].max().date()
    selected_dates = st.sidebar.date_input(
        "Date range",
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (minimum_date, maximum_date)
    )
    st.sidebar.info(
        "Filters change the charts and KPIs. Alert calculations always use "
        "the unfiltered replay stream."
    )

    state = build_dashboard_state(
        full_frame,
        replay_count,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )
    display_frame = state["display_frame"]
    alerts = state["alerts"]

    metrics = summary_metrics(display_frame)
    active_alerts = int(alerts["is_alert"].sum())
    metric_columns = st.columns(5)
    metric_columns[0].metric("Transactions", f"{metrics['transaction_count']:,}")
    metric_columns[1].metric("Success rate", f"{metrics['success_rate']:.1%}")
    metric_columns[2].metric("Failed", f"{metrics['failed_count']:,}")
    metric_columns[3].metric(
        "Average latency",
        f"{metrics['average_latency_ms']:.1f} ms",
    )
    metric_columns[4].metric("Active alerts", active_alerts)

    st.subheader("Gateway health")
    st.caption(
        "An alert triggers when a gateway's latest 50 transactions fall at "
        "least 10 percentage points below its full-data baseline."
    )
    _render_alerts(alerts)

    if display_frame.empty:
        st.info(
            "No transactions match the selected filters. Clear one or more "
            "sidebar filters to continue."
        )
        return

    st.subheader("Gateway performance")
    _render_gateway_charts(display_frame)

    st.subheader("Success trend")
    series = success_rate_series(display_frame)
    trend_chart = px.line(
        series,
        x="Timestamp",
        y="success_rate",
        markers=True,
        color_discrete_sequence=["#2563EB"],
    )
    trend_chart.update_layout(yaxis_tickformat=".0%", yaxis_range=[0, 1])
    st.plotly_chart(trend_chart, use_container_width=True)

    st.subheader("Failure analysis")
    st.caption("Break down failed transactions to identify recurring patterns.")
    _render_failure_charts(display_frame)

    st.subheader("Recent transactions")
    recent_columns = [
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
    st.dataframe(
        display_frame.sort_values("Timestamp", ascending=False)
        .head(25)[recent_columns],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("How to interpret this dashboard"):
        st.markdown(
            """
            - **Baseline** is each gateway's success rate across the complete dataset.
            - **Latest 50** is the gateway's success rate in its newest 50 replayed transactions.
            - **Drop** is baseline minus latest-50 performance.
            - Gateway assignment is random, so comparisons are for demonstration only.
            """
        )


if __name__ == "__main__":
    render_app()
