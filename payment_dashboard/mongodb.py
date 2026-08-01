"""MongoDB Atlas adapter for the dashboard's DataFrame contract."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from payment_dashboard.data_loader import validate_transactions

LOGGER = logging.getLogger(__name__)

COLUMN_MAP = {
    "transaction_id": "Transaction ID",
    "sender_account_id": "Sender Account ID",
    "receiver_account_id": "Receiver Account ID",
    "transaction_amount": "Transaction Amount",
    "transaction_type": "Transaction Type",
    "transaction_timestamp": "Timestamp",
    "transaction_status": "Transaction Status",
    "fraud_flag": "Fraud Flag",
    "geolocation": "Geolocation (Latitude/Longitude)",
    "device_used": "Device Used",
    "network_slice_id": "Network Slice ID",
    "latency_ms": "Latency (ms)",
    "slice_bandwidth_mbps": "Slice Bandwidth (Mbps)",
    "pin_code": "PIN Code",
    "bank_gateway": "Bank Gateway",
}


@dataclass(frozen=True, slots=True)
class MongoResources:
    client: Any
    database: Any


@dataclass(frozen=True, slots=True)
class DatabaseResult:
    frame: pd.DataFrame
    source: Literal["mongodb", "fallback"]
    message: str | None = None


def create_resources_from_env() -> MongoResources | None:
    """Connect to configured Atlas resources with short failure timeouts."""
    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DATABASE")
    if not uri or not database_name:
        return None
    try:
        from pymongo import MongoClient
    except ImportError:
        LOGGER.warning("PyMongo dependency is unavailable")
        return None
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=3_000,
        connectTimeoutMS=3_000,
        appname="payment-success-monitor",
    )
    client.admin.command("ping")
    return MongoResources(client, client[database_name])


def ensure_indexes(database: Any) -> None:
    """Create the indexes required by imports and dashboard queries."""
    collection = database["transactions"]
    collection.create_index([("transaction_id", 1)], unique=True)
    collection.create_index([("transaction_timestamp", 1)])
    collection.create_index([("bank_gateway", 1), ("transaction_status", 1)])
    collection.create_index([("is_deleted", 1), ("transaction_timestamp", 1)])


def documents_to_frame(documents: list[dict[str, object]]) -> pd.DataFrame:
    """Convert MongoDB documents to the established dashboard schema."""
    frame = pd.DataFrame(documents)
    frame = frame[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    frame["PIN Code"] = frame["PIN Code"].astype("string")
    validate_transactions(frame, require_gateway=True)
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], utc=True).dt.tz_localize(
        None
    )
    frame["Transaction Amount"] = pd.to_numeric(frame["Transaction Amount"])
    frame["Latency (ms)"] = pd.to_numeric(frame["Latency (ms)"])
    frame["Fraud Flag"] = frame["Fraud Flag"].astype("boolean")
    return frame.sort_values("Timestamp", kind="stable").reset_index(drop=True)


def load_dashboard_transactions(
    fallback: Callable[[], pd.DataFrame],
) -> DatabaseResult:
    """Load active Atlas documents, falling back safely when unavailable."""
    try:
        resources = create_resources_from_env()
        if resources is None:
            return DatabaseResult(
                fallback(),
                "fallback",
                "database.fallback_not_configured",
            )
        ensure_indexes(resources.database)
        cursor = resources.database["transactions"].find(
            {"is_deleted": {"$ne": True}}, {"_id": False}
        )
        documents = list(cursor.sort("transaction_timestamp", 1))
        if not documents:
            raise ValueError("No active MongoDB transactions")
        return DatabaseResult(documents_to_frame(documents), "mongodb")
    except Exception as exc:
        LOGGER.warning("MongoDB read failed: %s", type(exc).__name__)
        return DatabaseResult(fallback(), "fallback", "database.fallback_unavailable")
