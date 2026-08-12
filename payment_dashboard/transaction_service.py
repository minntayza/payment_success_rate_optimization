"""Validated administrator mutations for simulated transactions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from payment_dashboard.config import GATEWAYS, STATUSES
from payment_dashboard.mongodb import COLUMN_MAP

MANUAL_SIMULATION_VERSION = "manual-v1"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    subject: str
    role: str
    authenticated_at: datetime


def _require_principal(principal: AuthenticatedPrincipal) -> AuthenticatedPrincipal:
    if not isinstance(principal, AuthenticatedPrincipal):
        raise TypeError("Mutation requires an AuthenticatedPrincipal")
    return principal


class TransactionValidationError(ValueError):
    """Transaction input did not satisfy the application contract."""


class TransactionMutationError(RuntimeError):
    """A transaction mutation failed without exposing provider details."""


TRANSACTION_TYPES = frozenset({"Transfer", "Deposit", "Withdrawal"})
DEVICES = frozenset({"Mobile", "Desktop", "Tablet"})
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
        try:
            number = float(str(values[field]))
        except ValueError as exc:
            raise TransactionValidationError(
                f"{field} must be numeric and non-negative"
            ) from exc
        if not pd.notna(number) or number < 0:
            raise TransactionValidationError(
                f"{field} must be numeric and non-negative"
            )
    try:
        timestamp = pd.Timestamp(str(values["Timestamp"]))
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
    payload["transaction_amount"] = float(str(payload["transaction_amount"]))
    payload["latency_ms"] = float(str(payload["latency_ms"]))
    payload["slice_bandwidth_mbps"] = float(str(payload["slice_bandwidth_mbps"]))
    return payload


def _sanitized(document: dict[str, object] | None) -> dict[str, object] | None:
    if document is None:
        return None
    return {key: value for key, value in document.items() if key != "_id"}


def _audit(
    database: Any,
    transaction_id: str,
    action: str,
    old_document: dict[str, object] | None,
    new_document: dict[str, object] | None,
    principal: AuthenticatedPrincipal,
    session: Any = None,
) -> None:
    options = {"session": session} if session is not None else {}
    database["transaction_audit_log"].insert_one(
        {
            "transaction_id": transaction_id,
            "action": action,
            "actor": principal.subject,
            "actor_role": principal.role,
            "changed_at": datetime.now(UTC),
            "old_document": _sanitized(old_document),
            "new_document": _sanitized(new_document),
        },
        **options,
    )


def _atomic(database: Any, mutation: Callable[[Any], None]) -> None:
    """Run the business mutation and audit in one MongoDB transaction."""
    client = getattr(database, "client", None)
    if client is None:
        mutation(None)
        return
    with client.start_session() as session, session.start_transaction():
        mutation(session)


def create_transaction(
    database: Any,
    values: dict[str, object],
    principal: AuthenticatedPrincipal,
) -> None:
    principal = _require_principal(principal)
    payload = validate_transaction(values)
    now = datetime.now(UTC)
    payload.update(
        {
            "source_transaction_status": payload["transaction_status"],
            "simulation_version": MANUAL_SIMULATION_VERSION,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "created_by": principal.subject,
            "updated_by": principal.subject,
        }
    )
    try:

        def mutation(session: Any) -> None:
            options = {"session": session} if session is not None else {}
            database["transactions"].insert_one(payload, **options)
            _audit(
                database,
                str(payload["transaction_id"]),
                "INSERT",
                None,
                payload,
                principal,
                session,
            )

        _atomic(database, mutation)
    except Exception as exc:
        raise TransactionMutationError(
            "Unable to create the transaction. Check that its ID is unique."
        ) from exc


def update_transaction(
    database: Any,
    transaction_id: str,
    values: dict[str, object],
    principal: AuthenticatedPrincipal,
) -> None:
    principal = _require_principal(principal)
    payload = validate_transaction(values)
    payload.pop("transaction_id", None)
    payload.pop("source_transaction_status", None)
    payload.pop("simulation_version", None)
    payload.update(
        {
            "simulation_version": MANUAL_SIMULATION_VERSION,
            "updated_at": datetime.now(UTC),
            "updated_by": principal.subject,
        }
    )
    try:

        def mutation(session: Any) -> None:
            collection = database["transactions"]
            query = {"transaction_id": transaction_id, "is_deleted": False}
            options = {"session": session} if session is not None else {}
            old_document = collection.find_one(query, **options)
            result = collection.update_one(query, {"$set": payload}, **options)
            if not result.matched_count:
                raise LookupError("Transaction not found")
            new_document = {**(old_document or {}), **payload}
            _audit(
                database,
                transaction_id,
                "UPDATE",
                old_document,
                new_document,
                principal,
                session,
            )

        _atomic(database, mutation)
    except Exception as exc:
        raise TransactionMutationError("Unable to update the transaction.") from exc


def soft_delete_transaction(
    database: Any,
    transaction_id: str,
    principal: AuthenticatedPrincipal,
) -> None:
    principal = _require_principal(principal)
    if not transaction_id.strip():
        raise TransactionValidationError("Transaction ID must not be blank")
    changes = {
        "is_deleted": True,
        "deleted_at": datetime.now(UTC),
        "deleted_by": principal.subject,
        "updated_at": datetime.now(UTC),
        "updated_by": principal.subject,
    }
    try:

        def mutation(session: Any) -> None:
            collection = database["transactions"]
            query = {"transaction_id": transaction_id, "is_deleted": False}
            options = {"session": session} if session is not None else {}
            old_document = collection.find_one(query, **options)
            result = collection.update_one(query, {"$set": changes}, **options)
            if not result.matched_count:
                raise LookupError("Transaction not found")
            _audit(
                database,
                transaction_id,
                "SOFT_DELETE",
                old_document,
                {**(old_document or {}), **changes},
                principal,
                session,
            )

        _atomic(database, mutation)
    except Exception as exc:
        raise TransactionMutationError("Unable to delete the transaction.") from exc
