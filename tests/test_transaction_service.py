from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from payment_dashboard.transaction_service import (
    AuthenticatedPrincipal,
    TransactionValidationError,
    create_transaction,
    soft_delete_transaction,
    update_transaction,
    validate_transaction,
)

PRINCIPAL = AuthenticatedPrincipal("demo-admin", "administrator", datetime.now(UTC))


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
        "Bank Gateway": "Gateway A",
    }


class Transactions:
    def __init__(self):
        self.document = None
        self.update = None

    def insert_one(self, document, **_options):
        self.document = document

    def find_one(self, query, **_options):
        return self.document or {"transaction_id": query["transaction_id"]}

    def update_one(self, query, update, **_options):
        self.update = (query, update)
        return SimpleNamespace(matched_count=1)


class Audit:
    def __init__(self):
        self.events = []

    def insert_one(self, event, **_options):
        self.events.append(event)


class Database(dict):
    def __init__(self):
        self.transactions = Transactions()
        self.audit = Audit()
        super().__init__(
            transactions=self.transactions, transaction_audit_log=self.audit
        )


class Session:
    def __init__(self):
        self.transaction_started = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def start_transaction(self):
        self.transaction_started = True
        return self


class Client:
    def __init__(self):
        self.session = Session()

    def start_session(self):
        return self.session


class TransactionalDatabase(Database):
    def __init__(self):
        super().__init__()
        self.client = Client()


def test_validation_rejects_negative_amount(values) -> None:
    values["Transaction Amount"] = -1
    with pytest.raises(TransactionValidationError, match="non-negative"):
        validate_transaction(values)


@pytest.mark.parametrize(
    "field",
    ("Transaction Amount", "Latency (ms)", "Slice Bandwidth (Mbps)"),
)
@pytest.mark.parametrize("value", (float("inf"), float("-inf")))
def test_validation_rejects_infinite_numeric_values(values, field, value) -> None:
    values[field] = value
    with pytest.raises(TransactionValidationError, match="finite and non-negative"):
        validate_transaction(values)


def test_create_inserts_document_and_sanitized_audit(values) -> None:
    database = Database()
    create_transaction(database, values, PRINCIPAL)
    assert database.transactions.document["transaction_id"] == "TX-1"
    assert database.transactions.document["source_transaction_status"] == "Success"
    assert database.transactions.document["simulation_version"] == "manual-v1"
    assert "pin_code" not in database.transactions.document
    event = database.audit.events[0]
    assert event["action"] == "INSERT"
    assert event["actor"] == "demo-admin"
    assert event["actor_role"] == "administrator"
    assert "pin_code" not in event["new_document"]
    assert "changed_at" in event
    assert "timestamp" not in event


def test_mutation_and_audit_share_database_transaction(values) -> None:
    database = TransactionalDatabase()
    create_transaction(database, values, PRINCIPAL)
    assert database.client.session.transaction_started is True


def test_update_preserves_id_and_audits(values) -> None:
    database = Database()
    values["Source Transaction Status"] = "Failed"
    values["Simulation Version"] = "controlled-v1"
    update_transaction(database, "TX-1", values, PRINCIPAL)
    query, update = database.transactions.update
    assert query == {"transaction_id": "TX-1", "is_deleted": False}
    assert "transaction_id" not in update["$set"]
    assert update["$set"]["simulation_version"] == "manual-v1"
    assert "source_transaction_status" not in update["$set"]
    assert "pin_code" not in update["$set"]
    assert database.audit.events[0]["action"] == "UPDATE"


def test_soft_delete_updates_instead_of_deleting() -> None:
    database = Database()
    soft_delete_transaction(database, "TX-1", PRINCIPAL)
    _, update = database.transactions.update
    assert update["$set"]["is_deleted"] is True
    assert "deleted_at" in update["$set"]
    assert database.audit.events[0]["action"] == "SOFT_DELETE"


def test_mutations_reject_forgeable_actor_strings(values) -> None:
    with pytest.raises(TypeError, match="AuthenticatedPrincipal"):
        create_transaction(Database(), values, "administrator")  # type: ignore[arg-type]
