from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from payment_dashboard.ui import admin


def test_fallback_mode_disables_transaction_editing(monkeypatch) -> None:
    info = MagicMock()
    monkeypatch.setattr(admin.st, "info", info)
    changed = admin.render_admin_panel(None, "fallback", pd.DataFrame(), "en")
    assert changed is False
    info.assert_called_once()


def test_row_values_preserve_pin_and_boolean(sample_transactions) -> None:
    frame = sample_transactions.iloc[:1].assign(**{"Bank Gateway": "Gateway A"})
    values = admin._row_values(frame.iloc[0])
    assert values["PIN Code"] == "1111"
    assert values["Fraud Flag"] is False


def test_clear_admin_session_removes_auth_state(monkeypatch) -> None:
    monkeypatch.setattr(admin.st, "session_state", {admin.AUTH_STATE_KEY: object()})
    admin._clear_admin_session()
    assert admin.AUTH_STATE_KEY not in admin.st.session_state
