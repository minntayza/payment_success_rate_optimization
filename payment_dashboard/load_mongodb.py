"""Validated importer for prepared simulated transactions in MongoDB Atlas."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pymongo import UpdateOne

from payment_dashboard.data_loader import load_transactions, validate_transactions
from payment_dashboard.mongodb import (
    COLUMN_MAP,
    create_resources_from_env,
    ensure_indexes,
)


def frame_to_documents(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Serialize a validated dashboard DataFrame for MongoDB."""
    validate_transactions(frame, require_gateway=True)
    reverse_map = {display: storage for storage, display in COLUMN_MAP.items()}
    prepared = frame[list(reverse_map)].rename(columns=reverse_map).copy()
    prepared["transaction_timestamp"] = pd.to_datetime(
        prepared["transaction_timestamp"], utc=True
    ).map(lambda value: value.to_pydatetime())
    prepared["fraud_flag"] = prepared["fraud_flag"].astype(bool)
    prepared["pin_code"] = prepared["pin_code"].astype(str)
    return [
        {key: _native(value) for key, value in row.items()}
        for row in prepared.to_dict(orient="records")
    ]


def _native(value: object) -> object:
    return value.item() if hasattr(value, "item") else value


def import_transactions(path: Path, database: Any, batch_size: int = 200) -> int:
    """Validate and deterministically upsert the prepared CSV."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    collection = database["transactions"]
    collection.update_many(
        {"is_deleted": {"$exists": False}},
        {"$set": {"is_deleted": False}},
    )
    ensure_indexes(database)
    documents = frame_to_documents(load_transactions(path, require_gateway=True))
    now = datetime.now(UTC)
    for start in range(0, len(documents), batch_size):
        operations = []
        for document in documents[start : start + batch_size]:
            document.update({"is_deleted": False, "updated_at": now})
            operations.append(
                UpdateOne(
                    {"transaction_id": document["transaction_id"]},
                    {
                        "$set": document,
                        "$setOnInsert": {
                            "created_at": now,
                            "created_by": "dataset-importer",
                        },
                    },
                    upsert=True,
                )
            )
        if operations:
            collection.bulk_write(operations, ordered=False)
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/transactions_with_gateways.csv"),
    )
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    resources = create_resources_from_env()
    if resources is None:
        raise SystemExit("Set MONGODB_URI and MONGODB_DATABASE first.")
    count = import_transactions(
        args.input, resources.database, batch_size=args.batch_size
    )
    print(f"Imported {count} simulated transactions.")


if __name__ == "__main__":
    main()
