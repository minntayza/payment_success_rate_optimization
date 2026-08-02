from __future__ import annotations

from payment_dashboard.load_mongodb import frame_to_documents, import_transactions
from payment_dashboard.simulation import simulate_transactions


class Collection:
    def __init__(self):
        self.operations = []
        self.updates = []

    def bulk_write(self, operations, ordered):
        assert ordered is False
        self.operations.extend(operations)

    def update_many(self, query, update):
        self.updates.append((query, update))


class Database(dict):
    def __init__(self):
        self.collection = Collection()
        super().__init__(transactions=self.collection)


def test_frame_to_documents_uses_native_values(sample_transactions) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:1], seed=42)
    document = frame_to_documents(frame)[0]
    assert document["transaction_id"] == "TX1"
    assert document["transaction_timestamp"].tzinfo is not None
    assert isinstance(document["fraud_flag"], bool)
    assert document["source_transaction_status"] == "Success"
    assert document["simulation_version"]


def test_import_uses_batched_upserts(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = simulate_transactions(sample_transactions.iloc[:3], seed=42)
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = Database()
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)
    count = import_transactions(path, database, batch_size=2)
    assert count == 3
    assert len(database.collection.operations) == 3
    assert all(operation._upsert for operation in database.collection.operations)
    assert database.collection.updates == [
        ({"is_deleted": {"$exists": False}}, {"$set": {"is_deleted": False}})
    ]
