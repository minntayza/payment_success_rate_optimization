"""Local-only importer for prepared simulated transactions."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pandas as pd

from payment_dashboard.data_loader import load_transactions, validate_transactions
from payment_dashboard.database import COLUMN_MAP


def frame_to_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Serialize a validated dashboard DataFrame for PostgreSQL."""
    validate_transactions(frame, require_gateway=True)
    reverse_map = {display: sql for sql, display in COLUMN_MAP.items()}
    prepared = frame[list(reverse_map)].rename(columns=reverse_map).copy()
    prepared["transaction_timestamp"] = pd.to_datetime(
        prepared["transaction_timestamp"], utc=True
    ).map(lambda value: value.isoformat())
    prepared["fraud_flag"] = prepared["fraud_flag"].astype(bool)
    prepared["pin_code"] = prepared["pin_code"].astype(str)
    return [
        {key: _native(value) for key, value in row.items()}
        for row in prepared.to_dict(orient="records")
    ]


def _native(value: object) -> object:
    """Convert NumPy scalars into values accepted by JSON encoders."""
    return value.item() if hasattr(value, "item") else value


def import_transactions(path: Path, client: Any, batch_size: int = 200) -> int:
    """Validate and deterministically upsert a prepared CSV in batches."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    rows = frame_to_rows(load_transactions(path, require_gateway=True))
    for start in range(0, len(rows), batch_size):
        client.table("transactions").upsert(
            rows[start : start + batch_size], on_conflict="transaction_id"
        ).execute()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/transactions_with_gateways.csv"),
    )
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        raise SystemExit(
            "Set SUPABASE_URL and local-only SUPABASE_SERVICE_ROLE_KEY first."
        )
    from supabase import create_client

    count = import_transactions(
        args.input, create_client(url, service_key), batch_size=args.batch_size
    )
    print(f"Imported {count} simulated transactions.")


if __name__ == "__main__":
    main()
