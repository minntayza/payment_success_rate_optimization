"""Typed navigation and compact filters for the dashboard command center."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

import streamlit as st

from payment_dashboard.config import DEVICES, GATEWAYS, STATUSES, TRANSACTION_TYPES
from payment_dashboard.dashboard_repository import DashboardFilters
from payment_dashboard.i18n import Language, translate


class DashboardView(StrEnum):
    """Top-level destinations in the dashboard command center."""

    OVERVIEW = "overview"
    GATEWAYS = "gateways"
    ROUTING = "routing"
    TRANSACTIONS = "transactions"
    ADMIN = "admin"


FILTERED_VIEWS = frozenset(
    {DashboardView.OVERVIEW, DashboardView.GATEWAYS, DashboardView.TRANSACTIONS}
)


def active_view() -> DashboardView:
    """Return the selected dashboard view, safely defaulting to overview."""
    raw = st.session_state.get("dashboard_view", DashboardView.OVERVIEW.value)
    try:
        return DashboardView(str(raw))
    except ValueError:
        return DashboardView.OVERVIEW


def render_top_navigation(language: Language) -> DashboardView:
    """Render the command-center navigation and return its selected view."""
    st.markdown(f"### {translate('shell.product_name', language)}")
    selected = st.radio(
        translate("shell.navigation", language),
        options=tuple(DashboardView),
        format_func=lambda view: translate(f"shell.view.{view.value}", language),
        horizontal=True,
        key="dashboard_view",
    )
    view = DashboardView(str(selected))
    st.caption(translate(f"shell.view_description.{view.value}", language))
    return view


def render_filter_bar(
    language: Language,
    on_change: Callable[[], None],
    on_reset: Callable[[], None],
) -> DashboardFilters:
    """Render compact repository filters while retaining stable widget keys."""
    with st.container(border=True):
        gateway_column, type_column, device_column, status_column, date_column = (
            st.columns(5)
        )
        with gateway_column:
            gateways = st.multiselect(
                translate("sidebar.gateway", language),
                sorted(GATEWAYS),
                placeholder=translate("sidebar.all_gateways", language),
                key="gateway_filter",
                on_change=on_change,
            )
        with type_column:
            transaction_types = st.multiselect(
                translate("sidebar.transaction_type", language),
                sorted(TRANSACTION_TYPES),
                placeholder=translate("sidebar.all_transaction_types", language),
                key="transaction_type_filter",
                on_change=on_change,
            )
        with device_column:
            devices = st.multiselect(
                translate("sidebar.device", language),
                sorted(DEVICES),
                placeholder=translate("sidebar.all_devices", language),
                key="device_filter",
                on_change=on_change,
            )
        with status_column:
            statuses = st.multiselect(
                translate("sidebar.status", language),
                sorted(STATUSES),
                placeholder=translate("sidebar.all_statuses", language),
                key="status_filter",
                on_change=on_change,
            )
        with date_column:
            selected_dates = st.date_input(
                translate("sidebar.date_range", language),
                value=[],
                key="date_filter",
                on_change=on_change,
            )
            st.button(
                translate("shell.reset_filters", language),
                type="secondary",
                on_click=on_reset,
            )

    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (None, None)
    )
    return DashboardFilters(
        gateways=tuple(gateways),
        transaction_types=tuple(transaction_types),
        devices=tuple(devices),
        statuses=tuple(statuses),
        start=start,
        end=end,
    )
