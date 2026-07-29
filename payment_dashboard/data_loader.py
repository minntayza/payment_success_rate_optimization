from __future__ import annotations

from pathlib import Path

import pandas as pd

from payment_dashboard.config import GATEWAYS, REQUIRED_COLUMNS, STATUSES


class DataValidationError(ValueError):
    """Raised when transaction data violates the project schema."""


def validate_transactions(
    frame: pd.DataFrame,
    require_gateway: bool = True,
) -> None:
    required = REQUIRED_COLUMNS | ({"Bank Gateway"} if require_gateway else set())
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if frame.empty:
        raise DataValidationError("Transaction data is empty")
    if frame["Transaction ID"].isna().any() or frame["Transaction ID"].eq("").any():
        raise DataValidationError("Transaction ID must be non-empty")
    if not frame["Transaction ID"].is_unique:
        raise DataValidationError("Transaction ID must be unique")
    statuses = frame["Transaction Status"]
    if statuses.isna().any() or not set(statuses).issubset(STATUSES):
        raise DataValidationError("Transaction Status must be Success or Failed")

    for column in ("Transaction Amount", "Latency (ms)"):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or values.lt(0).any():
            raise DataValidationError(f"{column} must be numeric and non-negative")

    timestamps = pd.to_datetime(frame["Timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise DataValidationError("Timestamp contains invalid values")

    if require_gateway:
        gateway_values = frame["Bank Gateway"]
        if gateway_values.isna().any() or not set(gateway_values).issubset(GATEWAYS):
            raise DataValidationError(
                "Bank Gateway must contain exactly one value from Gateway A-D per row"
            )


def load_transactions(
    path: str | Path,
    require_gateway: bool = True,
) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataValidationError(f"CSV file does not exist: {csv_path}")
    try:
        frame = pd.read_csv(csv_path, dtype={"PIN Code": "string"})
    except (OSError, pd.errors.ParserError) as exc:
        raise DataValidationError(f"Unable to read CSV: {csv_path}") from exc

    validate_transactions(frame, require_gateway=require_gateway)
    result = frame.copy()
    result["Timestamp"] = pd.to_datetime(result["Timestamp"])
    result["Transaction Amount"] = pd.to_numeric(result["Transaction Amount"])
    result["Latency (ms)"] = pd.to_numeric(result["Latency (ms)"])
    result["Fraud Flag"] = result["Fraud Flag"].astype("boolean")
    return result.sort_values("Timestamp", kind="stable").reset_index(drop=True)
