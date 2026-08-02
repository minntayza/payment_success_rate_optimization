from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from payment_dashboard import mongodb
from payment_dashboard.simulation import SIMULATION_VERSION


def _document() -> dict[str, object]:
    return {
        "transaction_id": "TX-1",
        "sender_account_id": "S1",
        "receiver_account_id": "R1",
        "transaction_amount": 25.5,
        "transaction_type": "Transfer",
        "transaction_timestamp": "2025-01-17T10:00:00+00:00",
        "transaction_status": "Success",
        "source_transaction_status": "Success",
        "simulation_version": SIMULATION_VERSION,
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


def test_documents_to_frame_preserves_dashboard_contract() -> None:
    frame = mongodb.documents_to_frame([_document()])
    assert frame.loc[0, "Transaction ID"] == "TX-1"
    assert frame.loc[0, "PIN Code"] == "0123"
    assert frame.loc[0, "Source Transaction Status"] == "Success"
    assert frame.loc[0, "Simulation Version"] == SIMULATION_VERSION
    assert pd.api.types.is_datetime64_any_dtype(frame["Timestamp"])


def test_create_resources_returns_none_without_configuration(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    assert mongodb.create_resources_from_env() is None


def test_ensure_indexes_creates_required_indexes() -> None:
    calls = []
    collection = SimpleNamespace(
        create_index=lambda keys, **options: calls.append((keys, options))
    )
    mongodb.ensure_indexes({"transactions": collection})
    assert any(options.get("unique") for _, options in calls)
    assert any(
        keys == [("is_deleted", 1), ("transaction_timestamp", 1)] for keys, _ in calls
    )


def test_load_queries_active_documents(monkeypatch) -> None:
    class Cursor(list):
        def sort(self, key, direction):
            assert (key, direction) == ("transaction_timestamp", 1)
            return self

    class Collection:
        def find(self, query, projection):
            assert query == {"is_deleted": {"$ne": True}}
            assert projection == {"_id": False}
            return Cursor([_document()])

    database = {"transactions": Collection()}
    resources = mongodb.MongoResources(SimpleNamespace(), database)
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: resources)
    monkeypatch.setattr(mongodb, "ensure_indexes", lambda _: None)
    result = mongodb.load_dashboard_transactions(lambda: pd.DataFrame())
    assert result.source == "mongodb"
    assert result.frame["Transaction ID"].tolist() == ["TX-1"]


def test_load_uses_safe_fallback_on_failure(monkeypatch, sample_transactions) -> None:
    class Collection:
        def find(self, *_):
            raise RuntimeError("secret uri detail")

    resources = mongodb.MongoResources(
        SimpleNamespace(), {"transactions": Collection()}
    )
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: resources)
    monkeypatch.setattr(mongodb, "ensure_indexes", lambda _: None)
    result = mongodb.load_dashboard_transactions(lambda: sample_transactions)
    assert result.source == "fallback"
    assert result.message == "database.fallback_unavailable"


def test_load_uses_localizable_status_when_database_is_not_configured(
    monkeypatch, sample_transactions
) -> None:
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: None)

    result = mongodb.load_dashboard_transactions(lambda: sample_transactions)

    assert result.source == "fallback"
    assert result.message == "database.fallback_not_configured"
