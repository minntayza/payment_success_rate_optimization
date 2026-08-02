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


class Transactions:
    def __init__(self):
        self.document = None
        self.update = None

    def insert_one(self, document):
        self.document = document

    def find_one(self, query):
        return self.document or {"transaction_id": query["transaction_id"]}

    def update_one(self, query, update):
        self.update = (query, update)
        return SimpleNamespace(matched_count=1)


class Audit:
    def __init__(self):
        self.events = []

    def insert_one(self, event):
        self.events.append(event)


class Database(dict):
    def __init__(self):
        self.transactions = Transactions()
        self.audit = Audit()
        super().__init__(
            transactions=self.transactions, transaction_audit_log=self.audit
        )


def test_validation_rejects_negative_amount(values) -> None:
    values["Transaction Amount"] = -1
    with pytest.raises(TransactionValidationError, match="non-negative"):
        validate_transaction(values)


def test_create_inserts_document_and_sanitized_audit(values) -> None:
    database = Database()
    create_transaction(database, values)
    assert database.transactions.document["transaction_id"] == "TX-1"
    assert database.transactions.document["source_transaction_status"] == "Success"
    assert database.transactions.document["simulation_version"] == "manual-v1"
    event = database.audit.events[0]
    assert event["action"] == "INSERT"
    assert "pin_code" not in event["new_document"]


def test_update_preserves_id_and_audits(values) -> None:
    database = Database()
    values["Source Transaction Status"] = "Failed"
    values["Simulation Version"] = "controlled-v1"
    update_transaction(database, "TX-1", values)
    query, update = database.transactions.update
    assert query == {"transaction_id": "TX-1", "is_deleted": False}
    assert "transaction_id" not in update["$set"]
    assert update["$set"]["simulation_version"] == "manual-v1"
    assert "source_transaction_status" not in update["$set"]
    assert database.audit.events[0]["action"] == "UPDATE"


def test_soft_delete_updates_instead_of_deleting() -> None:
    database = Database()
    soft_delete_transaction(database, "TX-1")
    _, update = database.transactions.update
    assert update["$set"]["is_deleted"] is True
    assert "deleted_at" in update["$set"]
    assert database.audit.events[0]["action"] == "SOFT_DELETE"
