from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest
from plotly import graph_objects as go

from payment_dashboard.analytics import add_latency_band
from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)
from payment_dashboard.models import DashboardSnapshot
from payment_dashboard.ui import sections
from payment_dashboard.ui.charts import (
    failure_breakdown_chart,
    gateway_success_chart,
    gateway_volume_chart,
    success_trend_chart,
)
from payment_dashboard.ui.sections import (
    render_failure_analysis,
    render_gateway_performance,
    render_success_trend,
)


@pytest.fixture
def dashboard_fixture(sample_transactions: pd.DataFrame) -> pd.DataFrame:
    frame = sample_transactions.copy()
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"])
    frame["Bank Gateway"] = ["Gateway A", "Gateway A", "Gateway B", "Gateway B"]
    return add_latency_band(frame)


@pytest.fixture
def dashboard_snapshot(dashboard_fixture: pd.DataFrame) -> DashboardSnapshot:
    return PandasDashboardRepository(dashboard_fixture).fetch(
        DashboardFilters(),
        PageRequest(),
    )


@pytest.mark.integration
def test_snapshot_gateway_charts_localize_myanmar_axes(
    monkeypatch: pytest.MonkeyPatch,
    dashboard_snapshot: DashboardSnapshot,
) -> None:
    charts: list[go.Figure] = []

    class Column:
        def plotly_chart(self, chart: go.Figure, **_kwargs: object) -> None:
            charts.append(chart)

    monkeypatch.setattr(sections.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections.st, "columns", lambda _count: [Column(), Column()])

    render_gateway_performance(dashboard_snapshot, language="my")

    assert charts[0].layout.xaxis.title.text == "ဂိတ်ဝေး"
    assert charts[0].layout.yaxis.title.text == "အောင်မြင်နှုန်း"
    assert charts[1].layout.xaxis.title.text == "ဂိတ်ဝေး"
    assert charts[1].layout.yaxis.title.text == "ငွေပေးချေမှုများ"


@pytest.mark.integration
def test_snapshot_trend_chart_localizes_myanmar_axes(
    monkeypatch: pytest.MonkeyPatch,
    dashboard_snapshot: DashboardSnapshot,
) -> None:
    charts: list[go.Figure] = []
    monkeypatch.setattr(sections.st, "subheader", lambda *_: None)
    monkeypatch.setattr(
        sections.st,
        "plotly_chart",
        lambda chart, **_kwargs: charts.append(chart),
    )

    render_success_trend(dashboard_snapshot, language="my")

    assert charts[0].layout.xaxis.title.text == "အချိန်မှတ်တမ်း"
    assert charts[0].layout.yaxis.title.text == "အောင်မြင်နှုန်း"


@pytest.mark.integration
def test_snapshot_failure_chart_localizes_myanmar_axes(
    monkeypatch: pytest.MonkeyPatch,
    dashboard_snapshot: DashboardSnapshot,
) -> None:
    charts: list[go.Figure] = []
    monkeypatch.setattr(sections.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections.st, "caption", lambda *_: None)
    monkeypatch.setattr(
        sections.st,
        "plotly_chart",
        lambda chart, **_kwargs: charts.append(chart),
    )

    render_failure_analysis(dashboard_snapshot, language="my")

    assert charts[0].layout.xaxis.title.text == "တုံ့ပြန်ချိန် အပိုင်းအခြား"
    assert charts[0].layout.yaxis.title.text == "မအောင်မြင်သော"


@pytest.mark.parametrize(
    ("builder", "title", "x_title", "y_title"),
    [
        (
            gateway_success_chart,
            "ဂိတ်ဝေးအလိုက် အောင်မြင်နှုန်း",
            "ဂိတ်ဝေး",
            "အောင်မြင်နှုန်း",
        ),
        (
            gateway_volume_chart,
            "ဂိတ်ဝေးအလိုက် ငွေပေးချေမှုပမာဏ",
            "ဂိတ်ဝေး",
            "ငွေပေးချေမှုများ",
        ),
    ],
)
def test_gateway_charts_localize_every_visible_label_without_changing_categories(
    dashboard_fixture: pd.DataFrame,
    builder: Callable[..., go.Figure],
    title: str,
    x_title: str,
    y_title: str,
) -> None:
    chart = builder(dashboard_fixture, language="my")
    categories = {value for trace in chart.data for value in trace.x}

    assert chart.layout.title.text == title
    assert chart.layout.xaxis.title.text == x_title
    assert chart.layout.yaxis.title.text == y_title
    assert categories <= set(dashboard_fixture["Bank Gateway"])


def test_success_trend_localizes_every_visible_label(
    dashboard_fixture: pd.DataFrame,
) -> None:
    chart = success_trend_chart(dashboard_fixture, language="my")

    assert chart.layout.title.text == "အောင်မြင်နှုန်း လမ်းကြောင်း"
    assert chart.layout.xaxis.title.text == "အချိန်မှတ်တမ်း"
    assert chart.layout.yaxis.title.text == "အောင်မြင်နှုန်း"


@pytest.mark.parametrize(
    ("dimension", "title", "burmese_dimension", "burmese_title"),
    [
        (
            "Fraud Flag",
            "Fraud flag",
            "လိမ်လည်မှု အမှတ်အသား",
            "လိမ်လည်မှု အမှတ်အသား အလိုက် မအောင်မြင်မှုများ",
        ),
        (
            "Latency Band",
            "Latency band",
            "တုံ့ပြန်ချိန် အပိုင်းအခြား",
            "တုံ့ပြန်ချိန် အပိုင်းအခြား အလိုက် မအောင်မြင်မှုများ",
        ),
        (
            "Device Used",
            "Device",
            "အသုံးပြုသည့် စက်",
            "အသုံးပြုသည့် စက် အလိုက် မအောင်မြင်မှုများ",
        ),
        (
            "Transaction Type",
            "Transaction type",
            "ငွေပေးချေမှု အမျိုးအစား",
            "ငွေပေးချေမှု အမျိုးအစား အလိုက် မအောင်မြင်မှုများ",
        ),
    ],
)
def test_failure_charts_localize_every_visible_label_and_keep_category_values(
    dashboard_fixture: pd.DataFrame,
    dimension: str,
    title: str,
    burmese_dimension: str,
    burmese_title: str,
) -> None:
    chart = failure_breakdown_chart(
        dashboard_fixture,
        dimension,
        title,
        language="my",
    )

    assert chart.layout.title.text == burmese_title
    assert chart.layout.xaxis.title.text == burmese_dimension
    assert chart.layout.yaxis.title.text == "မအောင်မြင်သော"
    assert set(chart.data[0].x) <= set(dashboard_fixture[dimension])
