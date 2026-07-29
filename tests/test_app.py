from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd
from streamlit.testing.v1 import AppTest

from payment_dashboard.app import build_dashboard_state


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
