"""Validated importer for prepared simulated transactions in MongoDB Atlas."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
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
from payment_dashboard.transaction_service import sanitize_audit_document

IMPORT_EXISTING_PROJECTION = {
    "_id": 0,
    "transaction_id": 1,
    "is_deleted": 1,
    "transaction_amount": 1,
    "transaction_type": 1,
    "transaction_timestamp": 1,
    "transaction_status": 1,
    "source_transaction_status": 1,
    "simulation_version": 1,
    "fraud_flag": 1,
    "geolocation": 1,
    "device_used": 1,
    "network_slice_id": 1,
    "latency_ms": 1,
    "slice_bandwidth_mbps": 1,
    "bank_gateway": 1,
}


@dataclass(frozen=True, slots=True)
class ImportSummary:
    imported_count: int
    inserted_count: int
    updated_count: int
    preserved_deleted_count: int
    absent_count: int


def frame_to_documents(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Serialize a validated dashboard DataFrame for MongoDB."""
    validate_transactions(frame, require_gateway=True)
    reverse_map = {display: storage for storage, display in COLUMN_MAP.items()}
    prepared = frame[list(reverse_map)].rename(columns=reverse_map).copy()
    prepared["transaction_timestamp"] = pd.to_datetime(
        prepared["transaction_timestamp"], utc=True
    ).map(lambda value: value.to_pydatetime())
    prepared["fraud_flag"] = prepared["fraud_flag"].astype(bool)
    return [
        {str(key): _native(value) for key, value in row.items()}
        for row in prepared.to_dict(orient="records")
    ]


def _native(value: object) -> object:
    return value.item() if hasattr(value, "item") else value


def import_transactions(
    path: Path,
    database: Any,
    batch_size: int = 200,
) -> ImportSummary:
    """Synchronize prepared rows without resurrecting soft-deleted records."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    collection = database["transactions"]
    ensure_indexes(database)
    documents = frame_to_documents(load_transactions(path, require_gateway=True))
    existing_documents = {
        str(document["transaction_id"]): document
        for document in collection.find({}, IMPORT_EXISTING_PROJECTION)
    }
    imported_ids = {str(document["transaction_id"]) for document in documents}
    now = datetime.now(UTC)
    inserted_count = 0
    updated_count = 0
    preserved_deleted_count = 0
    for start in range(0, len(documents), batch_size):
        operations = []
        audit_events = []
        for document in documents[start : start + batch_size]:
            transaction_id = str(document["transaction_id"])
            existing = existing_documents.get(transaction_id)
            if existing is not None and bool(existing.get("is_deleted", False)):
                preserved_deleted_count += 1
                continue
            changes = {**document, "updated_at": now, "updated_by": "dataset-importer"}
            inserted = existing is None
            operations.append(
                UpdateOne(
                    (
                        {"transaction_id": transaction_id}
                        if inserted
                        else {"transaction_id": transaction_id, "is_deleted": False}
                    ),
                    {
                        "$set": changes,
                        "$setOnInsert": {
                            "is_deleted": False,
                            "created_at": now,
                            "created_by": "dataset-importer",
                        },
                    },
                    upsert=inserted,
                )
            )
            action = "IMPORT_INSERT" if inserted else "IMPORT_UPDATE"
            inserted_count += int(inserted)
            updated_count += int(not inserted)
            audit_events.append(
                {
                    "transaction_id": transaction_id,
                    "action": action,
                    "old_document": sanitize_audit_document(existing),
                    "new_document": sanitize_audit_document(changes),
                    "actor": "dataset-importer",
                    "actor_role": "service",
                    "changed_at": now,
                }
            )
        if operations:
            client = getattr(database, "client", None)
            if client is None:
                session_context = contextlib.nullcontext(None)
            else:
                session_context = client.start_session()
            with session_context as session:
                transaction_context = (
                    session.start_transaction()
                    if session is not None
                    else contextlib.nullcontext()
                )
                with transaction_context:
                    options: dict[str, object] = (
                        {"session": session} if session is not None else {}
                    )
                    collection.bulk_write(operations, ordered=False, **options)
                    database["transaction_audit_log"].insert_many(
                        audit_events,
                        **options,
                    )
    return ImportSummary(
        imported_count=len(documents),
        inserted_count=inserted_count,
        updated_count=updated_count,
        preserved_deleted_count=preserved_deleted_count,
        absent_count=len(set(existing_documents) - imported_ids),
    )


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
    summary = import_transactions(
        args.input, resources.database, batch_size=args.batch_size
    )
    print(
        f"Imported {summary.imported_count} simulated transactions "
        f"({summary.inserted_count} inserted, {summary.updated_count} updated, "
        f"{summary.preserved_deleted_count} deleted preserved, "
        f"{summary.absent_count} existing absent from import)."
    )


if __name__ == "__main__":
    main()
