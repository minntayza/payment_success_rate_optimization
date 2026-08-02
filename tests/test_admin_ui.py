from __future__ import annotations

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


def test_row_values_preserve_pin_and_boolean(sample_transactions) -> None:
    frame = sample_transactions.iloc[:1].assign(**{"Bank Gateway": "Gateway A"})
    values = admin._row_values(frame.iloc[0])
    assert values["PIN Code"] == "1111"
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
