from __future__ import annotations

import pandas as pd

from payment_dashboard import database


def _row() -> dict[str, object]:
    return {
        "transaction_id": "TX-1",
        "sender_account_id": "S1",
        "receiver_account_id": "R1",
        "transaction_amount": 25.5,
        "transaction_type": "Transfer",
        "transaction_timestamp": "2025-01-17T10:00:00+00:00",
        "transaction_status": "Success",
        "fraud_flag": False,
        "geolocation": "16.8,96.1",
        "device_used": "Mobile",
        "network_slice_id": "Slice1",
        "latency_ms": 8,
        "slice_bandwidth_mbps": 100,
        "pin_code": "0123",
        "bank_gateway": "Gateway A",
        "is_deleted": False,
    }


def test_rows_to_frame_preserves_dashboard_contract() -> None:
    frame = database.rows_to_frame([_row()])

    assert frame.loc[0, "Transaction ID"] == "TX-1"
    assert frame.loc[0, "Bank Gateway"] == "Gateway A"
    assert frame.loc[0, "PIN Code"] == "0123"
    assert pd.api.types.is_datetime64_any_dtype(frame["Timestamp"])


def test_load_dashboard_transactions_uses_fallback_when_unconfigured(
    monkeypatch, sample_transactions: pd.DataFrame
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    result = database.load_dashboard_transactions(lambda: sample_transactions)

    assert result.source == "fallback"
    pd.testing.assert_frame_equal(result.frame, sample_transactions)
    assert result.message


def test_load_dashboard_transactions_queries_active_rows(monkeypatch) -> None:
    class Query:
        data = [_row()]

        def select(self, value):
            assert value == "*"
            return self

        def eq(self, column, value):
            assert (column, value) == ("is_deleted", False)
            return self

        def order(self, column):
            assert column == "transaction_timestamp"
            return self

        def execute(self):
            return self

    class Client:
        def table(self, name):
            assert name == "transactions"
            return Query()

    monkeypatch.setattr(database, "create_client_from_env", lambda: Client())
    result = database.load_dashboard_transactions(lambda: pd.DataFrame())

    assert result.source == "supabase"
    assert result.frame["Transaction ID"].tolist() == ["TX-1"]


def test_load_dashboard_transactions_uses_fallback_on_query_error(
    monkeypatch, sample_transactions: pd.DataFrame
) -> None:
    class BrokenClient:
        def table(self, name):
            raise RuntimeError("secret database detail")

    monkeypatch.setattr(database, "create_client_from_env", lambda: BrokenClient())
    result = database.load_dashboard_transactions(lambda: sample_transactions)

    assert result.source == "fallback"
    pd.testing.assert_frame_equal(result.frame, sample_transactions)
    assert "secret database detail" not in (result.message or "")
