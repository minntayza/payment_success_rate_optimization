"""Seed 100,000 deterministic synthetic payment transactions for MongoDB."""

from __future__ import annotations

from datetime import UTC, datetime

from dotenv import load_dotenv
from pymongo.errors import BulkWriteError

from payment_dashboard.demo_data import generate_demo_transactions
from payment_dashboard.load_mongodb import frame_to_documents
from payment_dashboard.mongodb import create_resources_from_env, ensure_indexes

TRANSACTION_COUNT = 100_000
BATCH_SIZE = 1_000


def _documents() -> list[dict[str, object]]:
    """Build deterministic schema-valid synthetic transaction documents."""
    frame = generate_demo_transactions(row_count=TRANSACTION_COUNT, seed=20_260_914)
    frame["Transaction ID"] = [
        f"SYNTH-{number:06d}" for number in range(1, TRANSACTION_COUNT + 1)
    ]
    frame["Sender Account ID"] = [
        f"CUST-{number % 100_000 + 1:06d}" for number in range(TRANSACTION_COUNT)
    ]
    frame["Receiver Account ID"] = [
        f"CUST-{(number * 17) % 100_000 + 1:06d}" for number in range(TRANSACTION_COUNT)
    ]
    now = datetime.now(UTC)
    return [
        {
            **document,
            "is_deleted": False,
            "created_at": now,
            "created_by": "synthetic-transaction-seeder",
            "updated_at": now,
            "updated_by": "synthetic-transaction-seeder",
        }
        for document in frame_to_documents(frame)
    ]


def main() -> None:
    """Insert synthetic transactions, safely ignoring records from prior runs."""
    load_dotenv()
    resources = create_resources_from_env()
    if resources is None:
        raise SystemExit("Set MONGODB_URI and MONGODB_DATABASE first.")
    ensure_indexes(resources.database)
    collection = resources.database["transactions"]
    inserted = 0
    documents = _documents()
    for start in range(0, len(documents), BATCH_SIZE):
        try:
            result = collection.insert_many(
                documents[start : start + BATCH_SIZE], ordered=False
            )
            inserted += len(result.inserted_ids)
        except BulkWriteError as exc:
            inserted += int(exc.details.get("nInserted", 0))
    total = collection.count_documents({"is_deleted": False})
    print(f"Inserted {inserted} synthetic transactions; active total: {total}")


if __name__ == "__main__":
    main()
