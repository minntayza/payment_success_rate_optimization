from __future__ import annotations

from types import SimpleNamespace

from payment_dashboard.load_supabase import frame_to_rows, import_transactions


class Query:
    def __init__(self, batches):
        self.batches = batches

    def upsert(self, payload, on_conflict):
        assert on_conflict == "transaction_id"
        self.batches.append(payload)
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class Client:
    def __init__(self):
        self.batches = []

    def table(self, name):
        assert name == "transactions"
        return Query(self.batches)


def test_frame_to_rows_serializes_timestamp_and_boolean(sample_transactions) -> None:
    frame = sample_transactions.iloc[:1].assign(**{"Bank Gateway": "Gateway A"})
    row = frame_to_rows(frame)[0]
    assert row["transaction_timestamp"].endswith("+00:00")
    assert isinstance(row["fraud_flag"], bool)
    assert row["pin_code"] == "1111"


def test_import_upserts_in_batches(tmp_path, sample_transactions) -> None:
    frame = sample_transactions.iloc[:3].assign(**{"Bank Gateway": "Gateway A"})
    path = tmp_path / "prepared.csv"
    frame.to_csv(path, index=False)
    client = Client()

    count = import_transactions(path, client, batch_size=2)

    assert count == 3
    assert [len(batch) for batch in client.batches] == [2, 1]
