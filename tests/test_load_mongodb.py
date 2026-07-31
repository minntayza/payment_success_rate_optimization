from __future__ import annotations

from payment_dashboard.load_mongodb import frame_to_documents, import_transactions


class Collection:
    def __init__(self):
        self.operations = []

    def bulk_write(self, operations, ordered):
        assert ordered is False
        self.operations.extend(operations)


class Database(dict):
    def __init__(self):
        self.collection = Collection()
        super().__init__(transactions=self.collection)


def test_frame_to_documents_uses_native_values(sample_transactions) -> None:
    frame = sample_transactions.iloc[:1].assign(**{"Bank Gateway": "Gateway A"})
    document = frame_to_documents(frame)[0]
    assert document["transaction_id"] == "TX1"
    assert document["transaction_timestamp"].tzinfo is not None
    assert isinstance(document["fraud_flag"], bool)


def test_import_uses_batched_upserts(
    monkeypatch, tmp_path, sample_transactions
) -> None:
    frame = sample_transactions.iloc[:3].assign(**{"Bank Gateway": "Gateway A"})
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    database = Database()
    monkeypatch.setattr("payment_dashboard.load_mongodb.ensure_indexes", lambda _: None)
    count = import_transactions(path, database, batch_size=2)
    assert count == 3
    assert len(database.collection.operations) == 3
    assert all(operation._upsert for operation in database.collection.operations)
