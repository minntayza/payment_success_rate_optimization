from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from payment_dashboard.config import (
    DEVICES,
    GATEWAYS,
    REQUIRED_COLUMNS,
    STATUSES,
    TRANSACTION_TYPES,
)


class DataValidationError(ValueError):
    """Raised when transaction data violates the project schema."""


def _validate_common(frame: pd.DataFrame) -> None:
    required = REQUIRED_COLUMNS
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if frame.empty:
        raise DataValidationError("Transaction data is empty")
    for column in ("Transaction ID", "Sender Account ID", "Receiver Account ID"):
        values = frame[column]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise DataValidationError(f"{column} must be non-empty")
    if not frame["Transaction ID"].is_unique:
        raise DataValidationError("Transaction ID must be unique")
    statuses = frame["Transaction Status"]
    if statuses.isna().any() or not set(statuses).issubset(STATUSES):
        raise DataValidationError("Transaction Status must be Success or Failed")

    for column, allowed in (
        ("Transaction Type", TRANSACTION_TYPES),
        ("Device Used", DEVICES),
    ):
        values = frame[column]
        if values.isna().any() or not set(values).issubset(allowed):
            raise DataValidationError(f"{column} contains invalid values")

    fraud_flags = frame["Fraud Flag"]
    if (
        fraud_flags.isna().any()
        or not fraud_flags.map(lambda value: isinstance(value, (bool, np.bool_))).all()
    ):
        raise DataValidationError("Fraud Flag must contain only true or false")

    for column in (
        "Transaction Amount",
        "Latency (ms)",
        "Slice Bandwidth (Mbps)",
    ):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all() or values.lt(0).any():
            raise DataValidationError(
                f"{column} must be finite, numeric, and non-negative"
            )

    timestamps = pd.to_datetime(frame["Timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise DataValidationError("Timestamp contains invalid values")


def validate_raw_transactions(frame: pd.DataFrame) -> None:
    """Validate immutable source transaction contexts."""
    _validate_common(frame)


def validate_prepared_transactions(frame: pd.DataFrame) -> None:
    """Validate prepared data with gateway and simulation metadata."""
    _validate_common(frame)
    missing = sorted({"Bank Gateway", "Simulation Version"} - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    gateway_values = frame["Bank Gateway"]
    if gateway_values.isna().any() or not set(gateway_values).issubset(GATEWAYS):
        raise DataValidationError(
            "Bank Gateway must contain exactly one value from Gateway A-D per row"
        )
    versions = frame["Simulation Version"]
    if versions.isna().any() or versions.astype(str).str.strip().eq("").any():
        raise DataValidationError("Simulation Version must be non-empty")
    if versions.astype(str).nunique() != 1:
        raise DataValidationError(
            "Prepared data must contain exactly one Simulation Version"
        )


def validate_transactions(
    frame: pd.DataFrame,
    require_gateway: bool = True,
) -> None:
    """Compatibility wrapper for raw and prepared validation."""
    if require_gateway:
        validate_prepared_transactions(frame)
    else:
        validate_raw_transactions(frame)


def load_transactions(
    path: str | Path,
    require_gateway: bool = True,
) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataValidationError(f"CSV file does not exist: {csv_path}")
    try:
        frame = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError) as exc:
        raise DataValidationError(f"Unable to read CSV: {csv_path}") from exc

    result = frame.drop(columns=["PIN Code"], errors="ignore").copy()
    validate_transactions(result, require_gateway=require_gateway)
    result["Timestamp"] = pd.to_datetime(result["Timestamp"], utc=True).dt.tz_localize(
        None
    )
    result["Transaction Amount"] = pd.to_numeric(result["Transaction Amount"])
    result["Latency (ms)"] = pd.to_numeric(result["Latency (ms)"])
    result["Slice Bandwidth (Mbps)"] = pd.to_numeric(result["Slice Bandwidth (Mbps)"])
    result["Fraud Flag"] = result["Fraud Flag"].astype("boolean")
    return result.sort_values("Timestamp", kind="stable").reset_index(drop=True)
