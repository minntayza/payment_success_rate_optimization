from __future__ import annotations

from types import SimpleNamespace

import pytest

from payment_dashboard.transaction_service import (
    TransactionValidationError,
    create_transaction,
    soft_delete_transaction,
    update_transaction,
    validate_transaction,
)


@pytest.fixture
def values() -> dict[str, object]:
    return {
        "Transaction ID": "TX-1",
        "Sender Account ID": "S1",
        "Receiver Account ID": "R1",
        "Transaction Amount": 20.5,
        "Transaction Type": "Transfer",
        "Timestamp": "2025-01-17 10:00:00",
        "Transaction Status": "Success",
        "Fraud Flag": False,
        "Geolocation (Latitude/Longitude)": "16.8,96.1",
        "Device Used": "Mobile",
        "Network Slice ID": "Slice1",
        "Latency (ms)": 8,
        "Slice Bandwidth (Mbps)": 100,
        "PIN Code": "0123",
        "Bank Gateway": "Gateway A",
    }


class Query:
    def __init__(self):
        self.inserted = None
        self.updated = None
        self.filters = []

    def insert(self, payload):
        self.inserted = payload
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        return SimpleNamespace(data=[])


def test_validation_rejects_negative_amount(values) -> None:
    values["Transaction Amount"] = -1
    with pytest.raises(TransactionValidationError, match="non-negative"):
        validate_transaction(values)


def test_validation_rejects_invalid_gateway(values) -> None:
    values["Bank Gateway"] = "Unknown"
    with pytest.raises(TransactionValidationError, match="gateway"):
        validate_transaction(values)


def test_create_maps_dashboard_fields_to_database(values) -> None:
    query = Query()
    create_transaction(SimpleNamespace(table=lambda _: query), values)
    assert query.inserted["transaction_id"] == "TX-1"
    assert query.inserted["transaction_timestamp"].startswith("2025-01-17T10:00:00")


def test_update_does_not_change_transaction_id(values) -> None:
    query = Query()
    values["Transaction Amount"] = 25
    update_transaction(SimpleNamespace(table=lambda _: query), "TX-1", values)
    assert "transaction_id" not in query.updated
    assert query.filters == [("transaction_id", "TX-1")]


def test_soft_delete_uses_update_not_delete() -> None:
    query = Query()
    soft_delete_transaction(SimpleNamespace(table=lambda _: query), "TX-1")
    assert query.updated == {"is_deleted": True}
    assert query.filters == [("transaction_id", "TX-1")]
