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
from payment_dashboard.i18n import DEFAULT_LANGUAGE, translate
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


def _render_language_toggle() -> str:
    """Render the top-of-page language switch and return its language code."""
    use_burmese = st.toggle(
        "English / မြန်မာ",
        value=False,
        key="language_toggle",
    )
    return "my" if use_burmese else DEFAULT_LANGUAGE


def _load_data(language: str = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """Load transaction data or show Streamlit error and stop."""
    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    try:
        return load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(translate("errors.load_data", language, exc=exc))
        st.info(translate("errors.prepare_data_guidance", language))
        st.stop()


def _render_sidebar(
    full_frame: pd.DataFrame,
    language: str = DEFAULT_LANGUAGE,
) -> tuple[int, list[str], list[str], list[str], list[str], date, date]:
    """Render sidebar controls and return filter selections."""
    st.sidebar.header(translate("sidebar.controls", language))
    st.sidebar.caption(translate("sidebar.replay_description", language))
    replay_count = st.sidebar.slider(
        translate("sidebar.replayed_transactions", language),
        min_value=1,
        max_value=len(full_frame),
        value=len(full_frame),
        help=translate("sidebar.replay_help", language),
    )
    st.sidebar.progress(replay_count / len(full_frame))
    st.sidebar.caption(
        translate(
            "sidebar.replay_count",
            language,
            replay_count=replay_count,
            total_count=len(full_frame),
        )
    )

    st.sidebar.subheader(translate("sidebar.display_filters", language))
    gateways = st.sidebar.multiselect(
        translate("sidebar.gateway", language),
        sorted(full_frame["Bank Gateway"].unique()),
        placeholder=translate("sidebar.all_gateways", language),
    )
    transaction_types = st.sidebar.multiselect(
        translate("sidebar.transaction_type", language),
        sorted(full_frame["Transaction Type"].unique()),
        placeholder=translate("sidebar.all_transaction_types", language),
    )
    devices = st.sidebar.multiselect(
        translate("sidebar.device", language),
        sorted(full_frame["Device Used"].unique()),
        placeholder=translate("sidebar.all_devices", language),
    )
    statuses = st.sidebar.multiselect(
        translate("sidebar.status", language),
        sorted(full_frame["Transaction Status"].unique()),
        placeholder=translate("sidebar.all_statuses", language),
    )

    minimum_date = full_frame["Timestamp"].min().date()
    maximum_date = full_frame["Timestamp"].max().date()
    selected_dates = st.sidebar.date_input(
        translate("sidebar.date_range", language),
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (minimum_date, maximum_date)
    )
    st.sidebar.info(translate("sidebar.filter_note", language))

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

    language = _render_language_toggle()
    st.title(translate("dashboard.title", language))
    st.markdown(translate("dashboard.description", language))
    st.caption(translate("dashboard.disclaimer", language))

    full_frame = _load_data(language)
    replay_count, gateways, transaction_types, devices, statuses, start, end = (
        _render_sidebar(full_frame, language=language)
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

    render_kpis(state, language=language)
    render_gateway_health(state.alerts, language=language)

    if state.display_frame.empty:
        st.info(translate("errors.no_matching_transactions", language))
        return

    render_gateway_performance(state.display_frame, language=language)
    render_success_trend(state.display_frame, language=language)
    render_failure_analysis(state.display_frame, language=language)
    render_recent_transactions(state.display_frame, language=language)
    render_interpretation_guide(language=language)


if __name__ == "__main__":
    render_app()
