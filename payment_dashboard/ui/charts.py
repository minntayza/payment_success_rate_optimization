"""Plotly chart builders."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from payment_dashboard.analytics import (
    failure_breakdown,
    gateway_summary,
    success_rate_series,
)
from payment_dashboard.config import CHART_COLORS
from payment_dashboard.i18n import translate


def gateway_success_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
    """Bar chart of success rate by gateway."""
    data = gateway_summary(frame)
    chart = px.bar(
        data,
        x="Bank Gateway",
        y="success_rate",
        color="Bank Gateway",
        color_discrete_sequence=CHART_COLORS,
        title=translate("charts.success_rate_by_gateway", language),
        labels={
            "Bank Gateway": translate("sidebar.gateway", language),
            "success_rate": translate("kpi.success_rate", language),
        },
        range_y=[0, 1],
        text_auto=".1%",
    )
    chart.update_layout(showlegend=False, yaxis_tickformat=".0%")
    return chart


def gateway_volume_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
    """Bar chart of transaction volume by gateway."""
    data = gateway_summary(frame)
    chart = px.bar(
        data,
        x="Bank Gateway",
        y="transaction_count",
        color="Bank Gateway",
        color_discrete_sequence=CHART_COLORS,
        title=translate("charts.transaction_volume_by_gateway", language),
        labels={
            "Bank Gateway": translate("sidebar.gateway", language),
            "transaction_count": translate("kpi.transactions", language),
        },
        text_auto=True,
    )
    chart.update_layout(showlegend=False)
    return chart


def success_trend_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
    """Line chart of success rate over time."""
    series = success_rate_series(frame)
    chart = px.line(
        series,
        x="Timestamp",
        y="success_rate",
        markers=True,
        color_discrete_sequence=["#2563EB"],
        title=translate("charts.success_trend", language),
        labels={
            "Timestamp": translate("Timestamp", language),
            "success_rate": translate("kpi.success_rate", language),
        },
    )
    chart.update_layout(yaxis_tickformat=".0%", yaxis_range=[0, 1])
    return chart


def failure_breakdown_chart(
    frame: pd.DataFrame,
    dimension: str,
    title: str,
    language: str = "en",
) -> go.Figure:
    """Bar chart of failures by a single dimension."""
    breakdown = failure_breakdown(frame, dimension)
    display_dimension = _display_dimension(title, language)
    chart = px.bar(
        breakdown,
        x=dimension,
        y="failed_count",
        title=translate(
            "charts.failures_by",
            language,
            title=display_dimension.lower(),
        ),
        labels={
            dimension: display_dimension,
            "failed_count": translate("kpi.failed", language),
        },
        color_discrete_sequence=["#F97316"],
        text_auto=True,
    )
    chart.update_layout(showlegend=False)
    return chart


def _display_dimension(title: str, language: str) -> str:
    """Translate a failure-chart dimension when it has a catalog label."""
    keys = {
        "device": "sidebar.device",
        "transaction type": "sidebar.transaction_type",
    }
    return translate(keys.get(title.lower(), title), language)


FAILURE_DIMENSIONS = (
    ("Fraud Flag", "Fraud flag"),
    ("Latency Band", "Latency band"),
    ("Device Used", "Device"),
    ("Transaction Type", "Transaction type"),
)
