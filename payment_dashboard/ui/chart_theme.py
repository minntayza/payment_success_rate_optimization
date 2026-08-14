"""Shared Plotly presentation for the command-center dashboard."""

from __future__ import annotations

import plotly.graph_objects as go


def apply_chart_theme(
    figure: go.Figure, *, show_legend: bool | None = None
) -> go.Figure:
    """Apply the dashboard chrome without changing chart traces or source data."""
    layout: dict[str, object] = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#F8FAFC", "family": "Inter, sans-serif"},
        "hoverlabel": {"bgcolor": "#122235", "font_color": "#F8FAFC"},
        "margin": {"l": 40, "r": 20, "t": 56, "b": 40},
    }
    if show_legend is not None:
        layout["showlegend"] = show_legend
    figure.update_layout(**layout)
    figure.update_xaxes(gridcolor="#24364B", zerolinecolor="#24364B")
    figure.update_yaxes(gridcolor="#24364B", zerolinecolor="#24364B")
    return figure
