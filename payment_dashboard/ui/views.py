"""Composition of the focused dashboard analytical views."""

from __future__ import annotations

import streamlit as st

from payment_dashboard.i18n import Language
from payment_dashboard.models import DashboardSnapshot
from payment_dashboard.routing_models import OptimizationReport
from payment_dashboard.ui.optimization import render_optimization_report
from payment_dashboard.ui.sections import (
    render_empty_state,
    render_failure_analysis,
    render_gateway_health,
    render_gateway_performance,
    render_interpretation_guide,
    render_kpis,
    render_recent_transactions,
    render_success_trend,
)


def _is_empty(snapshot: DashboardSnapshot) -> bool:
    """Return whether the active snapshot has no transactions to analyse."""
    return snapshot.transactions.empty


def render_overview(snapshot: DashboardSnapshot, language: Language) -> None:
    """Render the at-a-glance payment operations summary."""
    if _is_empty(snapshot):
        render_empty_state(language)
        return

    render_kpis(snapshot, language)
    trend, health = st.columns((1.7, 1.0))
    with trend:
        render_success_trend(snapshot, language)
    with health:
        render_gateway_health(snapshot.alerts, language)
    render_recent_transactions(snapshot.transactions, language, limit=8)


def render_gateways(snapshot: DashboardSnapshot, language: Language) -> None:
    """Render gateway performance, failure analysis, and health."""
    if _is_empty(snapshot):
        render_empty_state(language)
        return

    render_gateway_performance(snapshot, language)
    render_failure_analysis(snapshot, language)
    render_gateway_health(snapshot.alerts, language)


def render_routing_lab(report: OptimizationReport, language: Language) -> None:
    """Render the routing optimization benchmark."""
    render_optimization_report(report, language)


def render_transactions(snapshot: DashboardSnapshot, language: Language) -> None:
    """Render the complete filtered transaction table and its guide."""
    if _is_empty(snapshot):
        render_empty_state(language)
        return

    render_recent_transactions(snapshot.transactions, language, limit=None)
    render_interpretation_guide(language)
