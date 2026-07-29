"""Streamlit entry point for the payment success dashboard."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.analytics import add_latency_band, apply_filters
from payment_dashboard.config import DEFAULT_DATA_PATH
from payment_dashboard.data_loader import DataValidationError, load_transactions
from payment_dashboard.models import DashboardState
from payment_dashboard.ui.sections import (
    render_failure_analysis,
    render_gateway_health,
    render_gateway_performance,
    render_interpretation_guide,
    render_kpis,
    render_recent_transactions,
    render_success_trend,
)
from payment_dashboard.ui.style import apply_page_style


def build_dashboard_state(
    full_frame: pd.DataFrame,
    replay_count: int,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> DashboardState:
    """Compute the replay slice, filtered display frame, and alerts."""
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
    return DashboardState(
        replay_frame=replay_frame,
        display_frame=display_frame,
        alerts=evaluate_alerts(full_frame, replay_frame),
    )


def _load_data() -> pd.DataFrame:
    """Load transaction data or show Streamlit error and stop."""
    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    try:
        return load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(f"Unable to load dashboard data: {exc}")
        st.info(
            "Generate the prepared dataset with "
            "`python -m payment_dashboard.prepare_data` and refresh this page."
        )
        st.stop()


def _render_sidebar(
    full_frame: pd.DataFrame,
) -> tuple[int, list[str], list[str], list[str], list[str], date, date]:
    """Render sidebar controls and return filter selections."""
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
    st.sidebar.progress(replay_count / len(full_frame))
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

    return replay_count, gateways, transaction_types, devices, statuses, start, end


def render_app() -> None:
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Payment Success Monitor",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_page_style()

    st.title("Payment Success Monitor")
    st.markdown(
        "Track transaction health, compare simulated gateways, and investigate "
        "payment failures from one local dashboard."
    )
    st.caption(
        "Academic demo · Gateway labels are randomly simulated and do not "
        "represent real bank or gateway performance."
    )

    full_frame = _load_data()
    replay_count, gateways, transaction_types, devices, statuses, start, end = (
        _render_sidebar(full_frame)
    )

    state = build_dashboard_state(
        full_frame, replay_count, gateways, transaction_types,
        devices, statuses, start, end,
    )

    render_kpis(state)
    render_gateway_health(state.alerts)

    if state.display_frame.empty:
        st.info(
            "No transactions match the selected filters. Clear one or more "
            "sidebar filters to continue."
        )
        return

    render_gateway_performance(state.display_frame)
    render_success_trend(state.display_frame)
    render_failure_analysis(state.display_frame)
    render_recent_transactions(state.display_frame)
    render_interpretation_guide()


if __name__ == "__main__":
    render_app()
