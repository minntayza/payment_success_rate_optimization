from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from pymongo.errors import OperationFailure

from payment_dashboard import mongodb
from payment_dashboard.data_loader import DataValidationError
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


def _aggregate_result(documents: list[dict[str, object]]) -> dict[str, object]:
    return {
        "metrics": [],
        "gateway_summary": [],
        "trend": [],
        "failure_summary": [],
        "alerts": [],
        "transactions": documents,
        "total_count": [{"count": len(documents)}],
        "metadata": [{"simulation_version": SIMULATION_VERSION}],
    }


def test_documents_to_frame_preserves_dashboard_contract() -> None:
    frame = mongodb.documents_to_frame([_document()])
    assert frame.loc[0, "Transaction ID"] == "TX-1"
    assert "PIN Code" not in frame
    assert frame.loc[0, "Source Transaction Status"] == "Success"
    assert frame.loc[0, "Simulation Version"] == SIMULATION_VERSION
    assert pd.api.types.is_datetime64_any_dtype(frame["Timestamp"])


def test_documents_to_frame_redacts_accounts_omitted_by_public_projection() -> None:
    document = _document()
    document.pop("sender_account_id")
    document.pop("receiver_account_id")
    frame = mongodb.documents_to_frame([document])
    assert frame.loc[0, "Sender Account ID"] == "[redacted]"
    assert frame.loc[0, "Receiver Account ID"] == "[redacted]"


def test_documents_to_frame_rejects_mixed_legacy_and_simulated_documents() -> None:
    simulated = _document()
    legacy = _document()
    legacy.update({"transaction_id": "TX-2", "transaction_status": "Failed"})
    legacy.pop("source_transaction_status")
    legacy.pop("simulation_version")

    with pytest.raises(DataValidationError, match="exactly one Simulation Version"):
        mongodb.documents_to_frame([simulated, legacy])

    assert "source_transaction_status" not in legacy
    assert "simulation_version" not in legacy


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
        keys == [("is_deleted", 1), ("transaction_timestamp", -1)] for keys, _ in calls
    )


def test_public_transaction_projection_is_an_allowlist() -> None:
    projection = mongodb.PUBLIC_TRANSACTION_PROJECTION
    assert projection["transaction_id"] == 1
    assert "pin_code" not in projection
    assert "sender_account_id" not in projection
    assert "receiver_account_id" not in projection
    pipeline = mongodb._display_dashboard_pipeline(
        mongodb.DashboardFilters(), mongodb.PageRequest()
    )
    transactions = pipeline[1]["$facet"]["transactions"]
    assert transactions[-1] == {"$project": projection}


def test_load_queries_active_documents(monkeypatch) -> None:
    class Collection:
        find_called = False

        def __init__(self):
            self.aggregate_calls = []

        def aggregate(self, pipeline):
            self.aggregate_calls.append(pipeline)
            assert pipeline[0] == {"$match": {"is_deleted": False}}
            facet = pipeline[1]["$facet"]
            if "transactions" in facet:
                assert {"$limit": 100} in facet["transactions"]
            return [_aggregate_result([_document()])]

        def find(self, *_):
            self.find_called = True
            raise AssertionError("legacy loader must use bounded aggregation")

    collection = Collection()
    database = {"transactions": collection}
    resources = mongodb.MongoResources(SimpleNamespace(), database)
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: resources)
    monkeypatch.setattr(mongodb, "ensure_indexes", lambda _: None)
    result = mongodb.load_dashboard_transactions(lambda: pd.DataFrame())
    assert result.source == "mongodb"
    assert result.frame["Transaction ID"].tolist() == ["TX-1"]
    assert collection.find_called is False
    assert len(collection.aggregate_calls) == 2


def test_load_uses_safe_fallback_on_failure(monkeypatch, sample_transactions) -> None:
    class Collection:
        def aggregate(self, *_):
            raise OperationFailure("secret uri detail")

    resources = mongodb.MongoResources(
        SimpleNamespace(), {"transactions": Collection()}
    )
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: resources)
    monkeypatch.setattr(mongodb, "ensure_indexes", lambda _: None)
    result = mongodb.load_dashboard_transactions(lambda: sample_transactions)
    assert result.source == "fallback"
    assert result.message == "database.fallback_unavailable"


def test_load_does_not_hide_unexpected_programming_errors(
    monkeypatch, sample_transactions
) -> None:
    class Collection:
        def aggregate(self, *_):
            raise RuntimeError("programming defect")

    resources = mongodb.MongoResources(
        SimpleNamespace(), {"transactions": Collection()}
    )
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: resources)
    monkeypatch.setattr(mongodb, "ensure_indexes", lambda _: None)

    with pytest.raises(RuntimeError, match="programming defect"):
        mongodb.load_dashboard_transactions(lambda: sample_transactions)


def test_load_uses_localizable_status_when_database_is_not_configured(
    monkeypatch, sample_transactions
) -> None:
    monkeypatch.setattr(mongodb, "create_resources_from_env", lambda: None)

    result = mongodb.load_dashboard_transactions(lambda: sample_transactions)

    assert result.source == "fallback"
    assert result.message == "database.fallback_not_configured"
