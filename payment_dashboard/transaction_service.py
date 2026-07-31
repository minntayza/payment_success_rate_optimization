"""Validated administrator mutations for simulated transactions."""

from __future__ import annotations

from typing import Any

import pandas as pd

from payment_dashboard.config import GATEWAYS, STATUSES
from payment_dashboard.database import COLUMN_MAP


class TransactionValidationError(ValueError):
    """Transaction input did not satisfy the application contract."""


class TransactionMutationError(RuntimeError):
    """A transaction mutation failed without exposing provider details."""


TRANSACTION_TYPES = frozenset({"Transfer", "Deposit", "Withdrawal"})
DEVICES = frozenset({"Mobile", "Desktop"})


def validate_transaction(values: dict[str, object]) -> dict[str, object]:
    """Validate UI-format values and return a database-format payload."""
    missing = [name for name in COLUMN_MAP.values() if name not in values]
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
    payload["transaction_timestamp"] = timestamp.isoformat()
    payload["transaction_amount"] = float(payload["transaction_amount"])
    payload["latency_ms"] = float(payload["latency_ms"])
    payload["slice_bandwidth_mbps"] = float(payload["slice_bandwidth_mbps"])
    payload["pin_code"] = str(payload["pin_code"])
    return payload


def _execute(operation: Any, message: str) -> None:
    try:
        operation.execute()
    except Exception as exc:
        raise TransactionMutationError(message) from exc


def create_transaction(client: Any, values: dict[str, object]) -> None:
    payload = validate_transaction(values)
    _execute(
        client.table("transactions").insert(payload),
        "Unable to create the transaction. Check that its ID is unique.",
    )


def update_transaction(
    client: Any, transaction_id: str, values: dict[str, object]
) -> None:
    payload = validate_transaction(values)
    payload.pop("transaction_id", None)
    _execute(
        client.table("transactions")
        .update(payload)
        .eq("transaction_id", transaction_id),
        "Unable to update the transaction.",
    )


def soft_delete_transaction(client: Any, transaction_id: str) -> None:
    if not transaction_id.strip():
        raise TransactionValidationError("Transaction ID must not be blank")
    _execute(
        client.table("transactions")
        .update({"is_deleted": True})
        .eq("transaction_id", transaction_id),
        "Unable to delete the transaction.",
    )
