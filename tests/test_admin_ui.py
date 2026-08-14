from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from payment_dashboard.admin_auth import hash_fingerprint
from payment_dashboard.models import DataSource
from payment_dashboard.ui import admin


def test_fallback_mode_disables_transaction_editing(monkeypatch) -> None:
    info = MagicMock()
    monkeypatch.setattr(admin.st, "info", info)
    changed = admin.render_admin_panel(None, "fallback", pd.DataFrame(), "en")
    assert changed is False
    info.assert_called_once()


def test_demo_snapshot_disables_editing_even_with_database_credentials(
    monkeypatch,
) -> None:
    info = MagicMock()
    manager = MagicMock(side_effect=AssertionError("demo mode opened mutations"))
    monkeypatch.setattr(admin.st, "info", info)
    monkeypatch.setattr(admin, "_render_manager", manager)

    changed = admin.render_admin_panel(
        object(),
        DataSource.DEMO,
        pd.DataFrame(),
        "my",
        "configured-hash",
    )

    assert changed is False
    info.assert_called_once_with(
        "Demo fallback data အသုံးပြုနေချိန် database ပြင်ဆင်မှု မရနိုင်ပါ။"
    )
    manager.assert_not_called()


@pytest.mark.integration
def test_authenticated_live_admin_handles_empty_transaction_page() -> None:
    password_hash = "configured-hash"
    app = AppTest.from_string(
        f"""
import pandas as pd
import streamlit as st
from payment_dashboard.models import DataSource
from payment_dashboard.ui.admin import AUTH_STATE_KEY, render_admin_panel

st.session_state[AUTH_STATE_KEY] = {{
    "authenticated": True,
    "fingerprint": "{hash_fingerprint(password_hash)}",
    "subject": "demo-admin",
    "role": "administrator",
    "authenticated_at": "{datetime.now(UTC).isoformat()}",
    "expires_at": "{(datetime.now(UTC) + timedelta(minutes=30)).isoformat()}",
}}
render_admin_panel(
    object(),
    DataSource.LIVE,
    pd.DataFrame(columns=["Transaction ID"]),
    "en",
    "{password_hash}",
)
"""
    ).run(timeout=10)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Add", "Edit", "Soft delete"]
    assert app.text_input(key="add_id")


@pytest.mark.integration
def test_authenticated_live_admin_uses_unique_edit_widget_keys() -> None:
    password_hash = "configured-hash"
    app = AppTest.from_string(
        f'''
from datetime import datetime

import pandas as pd
import streamlit as st
from payment_dashboard.models import DataSource
from payment_dashboard.ui.admin import AUTH_STATE_KEY, render_admin_panel

st.session_state[AUTH_STATE_KEY] = {{
    "authenticated": True,
    "fingerprint": "{hash_fingerprint(password_hash)}",
    "subject": "demo-admin",
    "role": "administrator",
    "authenticated_at": "{datetime.now(UTC).isoformat()}",
    "expires_at": "{(datetime.now(UTC) + timedelta(minutes=30)).isoformat()}",
}}
frame = pd.DataFrame([{{
    "Transaction ID": "TX1",
    "Sender Account ID": "S1",
    "Receiver Account ID": "R1",
    "Transaction Amount": 100.0,
    "Transaction Type": "Transfer",
    "Timestamp": datetime(2025, 1, 17, 10, 3),
    "Transaction Status": "Success",
    "Fraud Flag": False,
    "Geolocation (Latitude/Longitude)": "A",
    "Device Used": "Mobile",
    "Network Slice ID": "Slice1",
    "Latency (ms)": 4.0,
    "Slice Bandwidth (Mbps)": 100.0,
    "Bank Gateway": "Gateway A",
}}])
render_admin_panel(object(), DataSource.LIVE, frame, "en", "{password_hash}")
'''
    ).run(timeout=10)

    assert not app.exception
    assert app.selectbox(key="edit_transaction_selector").value == "TX1"
    assert app.text_input(key="edit_id").value == "TX1"


def test_row_values_remove_pin_and_preserve_boolean(sample_transactions) -> None:
    frame = sample_transactions.iloc[:1].assign(**{"Bank Gateway": "Gateway A"})
    values = admin._row_values(frame.iloc[0])
    assert "PIN Code" not in values
    assert values["Fraud Flag"] is False


def test_clear_admin_session_removes_auth_state(monkeypatch) -> None:
    monkeypatch.setattr(admin.st, "session_state", {admin.AUTH_STATE_KEY: object()})
    admin._clear_admin_session()
    assert admin.AUTH_STATE_KEY not in admin.st.session_state


def test_authentication_requires_matching_hash_fingerprint(monkeypatch) -> None:
    monkeypatch.setattr(
        admin.st,
        "session_state",
        {admin.AUTH_STATE_KEY: {"authenticated": True, "fingerprint": "old"}},
    )
    assert admin._is_authenticated("new") is False
    assert admin.AUTH_STATE_KEY not in admin.st.session_state


def test_failed_admin_login_uses_server_backed_throttle(monkeypatch) -> None:
    record = MagicMock()
    allowed = MagicMock(return_value=False)
    monkeypatch.setattr(admin, "record_failed_login", record)
    monkeypatch.setattr(admin, "login_allowed", allowed)
    database = object()

    admin._record_failed_login(database, "encoded-hash")

    fingerprint = hash_fingerprint("encoded-hash")
    record.assert_called_once_with(database, fingerprint)
    assert admin._login_allowed(database, "encoded-hash") is False
    allowed.assert_called_once_with(database, fingerprint)
