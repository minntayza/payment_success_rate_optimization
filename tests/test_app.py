from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest import MonkeyPatch, fixture
from streamlit.testing.v1 import AppTest

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.app import build_dashboard_state
from payment_dashboard.models import DashboardState
from payment_dashboard.ui.sections import (
    render_gateway_health,
    render_kpis,
    render_recent_transactions,
)


def dashboard_fixture(sample_transactions: pd.DataFrame) -> pd.DataFrame:
    full = pd.concat([sample_transactions] * 60, ignore_index=True)
    full["Transaction ID"] = [f"TX{i}" for i in range(len(full))]
    full["Timestamp"] = pd.date_range(
        "2025-01-01",
        periods=len(full),
        freq="min",
    )
    full["Bank Gateway"] = [
        f"Gateway {chr(65 + (index % 4))}" for index in range(len(full))
    ]
    return full


@pytest.mark.integration
def test_alerts_ignore_display_filters(sample_transactions):
    full = dashboard_fixture(sample_transactions)

    state = build_dashboard_state(
        full_frame=full,
        replay_count=220,
        gateways=["Gateway D"],
        transaction_types=[],
        devices=[],
        statuses=["Failed"],
        start=None,
        end=None,
    )

    assert len(state.replay_frame) == 220
    assert set(state.display_frame["Bank Gateway"]) <= {"Gateway D"}
    assert set(state.display_frame["Transaction Status"]) <= {"Failed"}
    assert state.alerts["has_sufficient_history"].all()


@pytest.mark.integration
def test_replay_count_limits_displayed_transactions(sample_transactions):
    full = dashboard_fixture(sample_transactions)

    state = build_dashboard_state(
        full_frame=full,
        replay_count=80,
        gateways=[],
        transaction_types=[],
        devices=[],
        statuses=[],
        start=None,
        end=None,
    )

    assert len(state.replay_frame) == 80
    assert len(state.display_frame) == 80
    assert "Latency Band" in state.display_frame
    assert not state.alerts["has_sufficient_history"].any()


@pytest.mark.integration
def test_streamlit_app_starts_without_exception():
    app_path = Path(__file__).parents[1] / "payment_dashboard" / "app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception


@pytest.mark.integration
def test_app_imports_as_installed_package():
    """Verify app.py works as an installed package (no sys.path hacks)."""
    result = subprocess.run(
        [sys.executable, "-c", "from payment_dashboard.app import render_app"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@fixture
def dashboard_state(sample_transactions: pd.DataFrame) -> DashboardState:
    frame = dashboard_fixture(sample_transactions)
    alerts = evaluate_alerts(frame, frame)
    return DashboardState(frame, frame, alerts)


def test_kpis_render_burmese_labels(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    columns = [MagicMock() for _ in range(5)]
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.columns", lambda count: columns
    )

    render_kpis(dashboard_state, language="my")

    assert columns[0].metric.call_args.args[0] == "ငွေပေးချေမှုများ"


def test_gateway_health_keeps_gateway_values(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.dataframe",
        lambda frame, **_: captured.append(frame),
    )

    render_gateway_health(dashboard_state.alerts, language="my")

    assert set(captured[0]["ဂိတ်ဝေး"]) == set(dashboard_state.alerts["Bank Gateway"])


def test_recent_transactions_localizes_headers_without_changing_values(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.dataframe",
        lambda frame, **_: captured.append(frame),
    )
    expected = dashboard_state.display_frame.sort_values(
        "Timestamp", ascending=False
    ).head(25)[
        [
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
    ]

    render_recent_transactions(dashboard_state.display_frame, language="my")

    displayed = captured[0]
    assert list(displayed.columns) == [
        "ငွေပေးချေမှု ID",
        "အချိန်မှတ်တမ်း",
        "ဂိတ်ဝေး",
        "ငွေပေးချေမှု အမျိုးအစား",
        "ငွေပေးချေမှု အခြေအနေ",
        "ငွေပမာဏ",
        "အသုံးပြုသည့် စက်",
        "တုံ့ပြန်ချိန် (ms)",
        "လိမ်လည်မှု အမှတ်အသား",
    ]
    pd.testing.assert_frame_equal(
        displayed.set_axis(expected.columns, axis="columns"), expected
    )
