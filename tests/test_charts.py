from __future__ import annotations

import pandas as pd
import pytest

from payment_dashboard.ui.charts import (
    failure_breakdown_chart,
    gateway_success_chart,
)


@pytest.fixture
def dashboard_fixture(sample_transactions: pd.DataFrame) -> pd.DataFrame:
    frame = sample_transactions.copy()
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"])
    frame["Bank Gateway"] = ["Gateway A", "Gateway A", "Gateway B", "Gateway B"]
    return frame


def test_gateway_chart_localizes_title_without_changing_categories(
    dashboard_fixture: pd.DataFrame,
) -> None:
    chart = gateway_success_chart(dashboard_fixture, language="my")

    assert chart.layout.title.text == "ဂိတ်ဝေးအလိုက် အောင်မြင်နှုန်း"
    assert set(chart.data[0].x) <= set(dashboard_fixture["Bank Gateway"])


def test_failure_chart_defaults_to_english(dashboard_fixture: pd.DataFrame) -> None:
    chart = failure_breakdown_chart(
        dashboard_fixture, "Device Used", "Device", language="en"
    )

    assert chart.layout.title.text == "Failures by device"
