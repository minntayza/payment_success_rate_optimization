from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pandas as pd
from pytest import MonkeyPatch, fixture
from streamlit.testing.v1 import AppTest

from payment_dashboard.app import build_dashboard_state
from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.models import DashboardState
from payment_dashboard.ui.sections import render_gateway_health, render_kpis


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

    assert len(state["alert_input"]) == 220
    assert set(state["display_frame"]["Bank Gateway"]) <= {"Gateway D"}
    assert set(state["display_frame"]["Transaction Status"]) <= {"Failed"}
    assert state["alerts"]["has_sufficient_history"].all()


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

    assert len(state["alert_input"]) == 80
    assert len(state["display_frame"]) == 80
    assert "Latency Band" in state["display_frame"]
    assert not state["alerts"]["has_sufficient_history"].any()


def test_streamlit_app_starts_without_exception():
    app_path = Path(__file__).parents[1] / "payment_dashboard" / "app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception


def test_app_entrypoint_imports_when_project_root_is_not_on_sys_path():
    project_root = Path(__file__).parents[1]
    app_path = project_root / "payment_dashboard" / "app.py"
    script = f"""
import runpy
import sys

project_root = {str(project_root)!r}
sys.path = [
    {str(app_path.parent)!r},
    *[entry for entry in sys.path if entry not in ("", project_root)],
]
runpy.run_path({str(app_path)!r}, run_name="streamlit_app")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
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
