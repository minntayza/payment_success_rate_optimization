from __future__ import annotations

from payment_dashboard.load_mongodb import frame_to_documents, import_transactions
from payment_dashboard.simulation import simulate_transactions


class Collection:
    def __init__(self, documents=None):
        self.documents = documents or []
        self.operations = []
        self.updates = []
        self.find_projection = None

    def bulk_write(self, operations, ordered, **_kwargs):
        assert ordered is False
        self.operations.extend(operations)

    def update_many(self, query, update):
        self.updates.append((query, update))

    def find(self, _query=None, projection=None, **_kwargs):
        self.find_projection = projection
        return list(self.documents)


class Audit:
    def __init__(self):
        self.events = []

    def insert_many(self, events, **_kwargs):
        self.events.extend(events)


class Session:
    def __init__(self):
        self.started = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def start_transaction(self):
        self.started = True
        return self


class Client:
    def __init__(self):
        self.session = Session()

    def start_session(self):
        return self.session


class Database(dict):
    def __init__(self, documents=None):
        self.collection = Collection(documents)
        self.audit = Audit()
        super().__init__(
            transactions=self.collection,
            transaction_audit_log=self.audit,
        )


class TransactionalDatabase(Database):
    def __init__(self, documents=None):
        super().__init__(documents)
        self.client = Client()


def test_frame_to_documents_uses_native_values(sample_transactions) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:1], seed=42)
    document = frame_to_documents(frame)[0]
    assert document["transaction_id"] == "TX1"
    assert document["transaction_timestamp"].tzinfo is not None
    assert isinstance(document["fraud_flag"], bool)
    assert document["source_transaction_status"] == "Success"
    assert document["simulation_version"]
    assert "pin_code" not in document


def test_import_uses_batched_upserts(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:3], seed=42)
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = Database()
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)
    summary = import_transactions(path, database, batch_size=2)
    assert summary.imported_count == 3
    assert summary.inserted_count == 3
    assert len(database.collection.operations) == 3
    assert all(operation._upsert for operation in database.collection.operations)
    assert database.collection.updates == []
    assert [event["action"] for event in database.audit.events] == [
        "IMPORT_INSERT",
        "IMPORT_INSERT",
        "IMPORT_INSERT",
    ]


def test_import_preserves_deleted_records_and_reports_absent_rows(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:2], seed=42)
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = Database(
        [
            {"transaction_id": "TX1", "is_deleted": True},
            {"transaction_id": "TX2", "is_deleted": False},
            {"transaction_id": "ABSENT", "is_deleted": False},
        ]
    )
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)

    summary = import_transactions(path, database)

    assert summary.preserved_deleted_count == 1
    assert summary.updated_count == 1
    assert summary.absent_count == 1
    assert len(database.collection.operations) == 1
    operation = database.collection.operations[0]
    assert operation._filter == {"transaction_id": "TX2", "is_deleted": False}
    assert operation._doc["$set"].get("is_deleted") is None
    assert [event["action"] for event in database.audit.events] == ["IMPORT_UPDATE"]


def test_import_and_audit_share_database_transaction(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:1], seed=42)
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = TransactionalDatabase()
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)

    import_transactions(path, database)

    assert database.client.session.started is True


def test_import_sanitizes_legacy_existing_document_before_audit(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:1], seed=42)
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = Database(
        [
            {
                "transaction_id": "TX1",
                "is_deleted": False,
                "pin_code": "1234",
                "sender_account_id": "SECRET-SENDER",
                "receiver_account_id": "SECRET-RECEIVER",
                "transaction_status": "Failed",
            }
        ]
    )
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)

    import_transactions(path, database)

    event = database.audit.events[0]
    assert event["changed_at"]
    assert "timestamp" not in event
    assert "pin_code" not in event["old_document"]
    assert "sender_account_id" not in event["old_document"]
    assert "receiver_account_id" not in event["old_document"]
    assert database.collection.find_projection is not None
    assert database.collection.find_projection.get("pin_code") != 1
