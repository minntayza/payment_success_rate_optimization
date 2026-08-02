"""Validated administrator mutations for simulated transactions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from payment_dashboard.config import GATEWAYS, STATUSES
from payment_dashboard.mongodb import COLUMN_MAP
from payment_dashboard.simulation import SIMULATION_VERSION


class TransactionValidationError(ValueError):
    """Transaction input did not satisfy the application contract."""


class TransactionMutationError(RuntimeError):
    """A transaction mutation failed without exposing provider details."""


TRANSACTION_TYPES = frozenset({"Transfer", "Deposit", "Withdrawal"})
DEVICES = frozenset({"Mobile", "Desktop"})
SIMULATION_METADATA_FIELDS = {
    "Source Transaction Status",
    "Simulation Version",
}


def validate_transaction(values: dict[str, object]) -> dict[str, object]:
    """Validate UI-format values and return a database-format payload."""
    missing = [
        name
        for name in COLUMN_MAP.values()
        if name not in SIMULATION_METADATA_FIELDS and name not in values
    ]
    if missing:
        raise TransactionValidationError(
            f"Missing required fields: {', '.join(missing)}"
        )
    for field in ("Transaction ID", "Sender Account ID", "Receiver Account ID"):
        if not str(values[field]).strip():
            raise TransactionValidationError(f"{field} must not be blank")
    if values["Transaction Status"] not in STATUSES:
        raise TransactionValidationError("Choose a valid transaction status")
    if values["Transaction Type"] not in TRANSACTION_TYPES:
        raise TransactionValidationError("Choose a valid transaction type")
    if values["Device Used"] not in DEVICES:
        raise TransactionValidationError("Choose a valid device")
    if values["Bank Gateway"] not in GATEWAYS:
        raise TransactionValidationError("Choose a valid bank gateway")
    if not isinstance(values["Fraud Flag"], bool):
        raise TransactionValidationError("Fraud Flag must be true or false")
    for field in ("Transaction Amount", "Latency (ms)", "Slice Bandwidth (Mbps)"):
        number = pd.to_numeric(values[field], errors="coerce")
        if pd.isna(number) or float(number) < 0:
            raise TransactionValidationError(
                f"{field} must be numeric and non-negative"
            )
    try:
        timestamp = pd.Timestamp(values["Timestamp"])
    except (TypeError, ValueError) as exc:
        raise TransactionValidationError("Timestamp must be valid") from exc
    if pd.isna(timestamp):
        raise TransactionValidationError("Timestamp must be valid")

    reverse_map = {display: sql for sql, display in COLUMN_MAP.items()}
    payload = {
        reverse_map[name]: value
        for name, value in values.items()
        if name in reverse_map
    }
    payload["transaction_id"] = str(payload["transaction_id"]).strip()
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    payload["transaction_timestamp"] = timestamp.to_pydatetime()
    payload["transaction_amount"] = float(payload["transaction_amount"])
    payload["latency_ms"] = float(payload["latency_ms"])
    payload["slice_bandwidth_mbps"] = float(payload["slice_bandwidth_mbps"])
    payload["pin_code"] = str(payload["pin_code"])
    return payload


def _sanitized(document: dict[str, object] | None) -> dict[str, object] | None:
    if document is None:
        return None
    return {
        key: value for key, value in document.items() if key not in {"_id", "pin_code"}
    }


def _audit(
    database: Any,
    transaction_id: str,
    action: str,
    old_document: dict[str, object] | None,
    new_document: dict[str, object] | None,
    actor: str,
) -> None:
    database["transaction_audit_log"].insert_one(
        {
            "transaction_id": transaction_id,
            "action": action,
            "actor": actor,
            "changed_at": datetime.now(UTC),
            "old_document": _sanitized(old_document),
            "new_document": _sanitized(new_document),
        }
    )


def create_transaction(
    database: Any, values: dict[str, object], actor: str = "administrator"
) -> None:
    payload = validate_transaction(values)
    now = datetime.now(UTC)
    payload.update(
        {
            "source_transaction_status": payload["transaction_status"],
            "simulation_version": SIMULATION_VERSION,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "created_by": actor,
            "updated_by": actor,
        }
    )
    try:
        database["transactions"].insert_one(payload)
        _audit(database, str(payload["transaction_id"]), "INSERT", None, payload, actor)
    except Exception as exc:
        raise TransactionMutationError(
            "Unable to create the transaction. Check that its ID is unique."
        ) from exc


def update_transaction(
    database: Any,
    transaction_id: str,
    values: dict[str, object],
    actor: str = "administrator",
) -> None:
    payload = validate_transaction(values)
    payload.pop("transaction_id", None)
    payload.update({"updated_at": datetime.now(UTC), "updated_by": actor})
    try:
        collection = database["transactions"]
        query = {"transaction_id": transaction_id, "is_deleted": {"$ne": True}}
        old_document = collection.find_one(query)
        result = collection.update_one(query, {"$set": payload})
        if not result.matched_count:
            raise LookupError("Transaction not found")
        new_document = {**(old_document or {}), **payload}
        _audit(
            database,
            transaction_id,
            "UPDATE",
            old_document,
            new_document,
            actor,
        )
    except Exception as exc:
        raise TransactionMutationError("Unable to update the transaction.") from exc


def soft_delete_transaction(
    database: Any, transaction_id: str, actor: str = "administrator"
) -> None:
    if not transaction_id.strip():
        raise TransactionValidationError("Transaction ID must not be blank")
    changes = {
        "is_deleted": True,
        "deleted_at": datetime.now(UTC),
        "deleted_by": actor,
        "updated_at": datetime.now(UTC),
        "updated_by": actor,
    }
    try:
        collection = database["transactions"]
        query = {"transaction_id": transaction_id, "is_deleted": {"$ne": True}}
        old_document = collection.find_one(query)
        result = collection.update_one(query, {"$set": changes})
        if not result.matched_count:
            raise LookupError("Transaction not found")
        _audit(
            database,
            transaction_id,
            "SOFT_DELETE",
            old_document,
            {**(old_document or {}), **changes},
            actor,
        )
    except Exception as exc:
        raise TransactionMutationError("Unable to delete the transaction.") from exc
