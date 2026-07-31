"""Supabase read adapter for the dashboard's DataFrame contract."""

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
class DatabaseResult:
    frame: pd.DataFrame
    source: Literal["supabase", "fallback"]
    message: str | None = None


def create_client_from_env() -> Any | None:
    """Create the public Supabase client when both settings are available."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def rows_to_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Convert Supabase rows to the established dashboard schema."""
    frame = pd.DataFrame(rows)
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
    """Load active Supabase rows, falling back safely when unavailable."""
    client = create_client_from_env()
    if client is None:
        return DatabaseResult(
            fallback(), "fallback", "Supabase is not configured; showing demo data."
        )
    try:
        response = (
            client.table("transactions")
            .select("*")
            .eq("is_deleted", False)
            .order("transaction_timestamp")
            .execute()
        )
        rows = list(response.data or [])
        if not rows:
            raise ValueError("Supabase returned no active transactions")
        return DatabaseResult(rows_to_frame(rows), "supabase")
    except Exception as exc:  # client libraries expose several transport exceptions
        LOGGER.warning("Supabase read failed: %s", type(exc).__name__)
        return DatabaseResult(
            fallback(), "fallback", "Supabase is unavailable; showing demo data."
        )
