"""Tests for the shared dark Plotly presentation theme."""

from plotly import graph_objects as go

from payment_dashboard.ui.chart_theme import (
    ANALYTICAL_COLOR,
    CHART_TRACE_COLORS,
    CRITICAL_COLOR,
    HEALTHY_COLOR,
    WARNING_COLOR,
    apply_chart_theme,
)


def test_chart_theme_exports_the_approved_trace_palette() -> None:
    """Every analytical trace must draw from the command-center color tokens."""
    assert (
        CHART_TRACE_COLORS
        == (
            ANALYTICAL_COLOR,
            HEALTHY_COLOR,
            WARNING_COLOR,
            CRITICAL_COLOR,
        )
        == ("#22D3EE", "#34D399", "#FBBF24", "#FB7185")
    )


def test_chart_theme_uses_transparent_dark_layout() -> None:
    """Charts must inherit the command-center canvas without opaque panels."""
    figure = apply_chart_theme(go.Figure())

    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.font.color == "#F8FAFC"
    assert figure.layout.xaxis.gridcolor == "#24364B"
    assert figure.layout.yaxis.zerolinecolor == "#24364B"


def test_chart_theme_preserves_traces_and_honors_legend_override() -> None:
    """The presentation helper must not mutate chart data while setting chrome."""
    figure = go.Figure(go.Bar(x=["Gateway A"], y=[0.92]))

    themed = apply_chart_theme(figure, show_legend=False)

    assert themed is figure
    assert list(themed.data[0].x) == ["Gateway A"]
    assert list(themed.data[0].y) == [0.92]
    assert themed.layout.showlegend is False
