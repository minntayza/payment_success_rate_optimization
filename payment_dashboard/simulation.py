"""Deterministic controlled simulation for synthetic payment outcomes."""

from __future__ import annotations

import numpy as np
import pandas as pd

from payment_dashboard.config import (
    BUSINESS_HOUR_ADJUSTMENT,
    DEFAULT_SEED,
    DEVICE_SUCCESS_ADJUSTMENTS,
    GATEWAY_BASE_SUCCESS_RATES,
    GATEWAYS,
    HIGH_AMOUNT_SUCCESS_ADJUSTMENT,
    LOW_TRAFFIC_HOUR_ADJUSTMENT,
    MEDIUM_AMOUNT_SUCCESS_ADJUSTMENT,
    SIMULATION_PROBABILITY_RANGE,
    TRANSACTION_TYPE_SUCCESS_ADJUSTMENTS,
)

SIMULATION_VERSION = "controlled-v1"


def success_probabilities(frame: pd.DataFrame) -> pd.Series:
    """Calculate controlled success probabilities from gateway and transaction risk."""
    timestamps = pd.to_datetime(frame["Timestamp"], utc=True)
    hours = timestamps.dt.hour
    amounts = pd.to_numeric(frame["Transaction Amount"])
    hour_adjustments = np.select(
        [hours.between(0, 5), hours.between(9, 17)],
        [LOW_TRAFFIC_HOUR_ADJUSTMENT, BUSINESS_HOUR_ADJUSTMENT],
        default=0.0,
    )
    amount_adjustments = np.select(
        [amounts.gt(1_000), amounts.gt(500)],
        [HIGH_AMOUNT_SUCCESS_ADJUSTMENT, MEDIUM_AMOUNT_SUCCESS_ADJUSTMENT],
        default=0.0,
    )
    probabilities = (
        frame["Bank Gateway"].map(GATEWAY_BASE_SUCCESS_RATES)
        + frame["Device Used"].map(DEVICE_SUCCESS_ADJUSTMENTS)
        + frame["Transaction Type"].map(TRANSACTION_TYPE_SUCCESS_ADJUSTMENTS)
        + hour_adjustments
        + amount_adjustments
    )
    return pd.Series(
        probabilities.clip(*SIMULATION_PROBABILITY_RANGE),
        index=frame.index,
        dtype=float,
    )


def simulate_transactions(
    frame: pd.DataFrame, seed: int = DEFAULT_SEED
) -> pd.DataFrame:
    """Assign synthetic gateways and outcomes while retaining Kaggle outcomes."""
    result = frame.sort_values("Timestamp", kind="stable").reset_index(drop=True).copy()
    generator = np.random.default_rng(seed)
    result["Bank Gateway"] = generator.choice(GATEWAYS, size=len(result), replace=True)
    probabilities = success_probabilities(result)
    result["Source Transaction Status"] = result["Transaction Status"]
    result["Transaction Status"] = np.where(
        generator.random(len(result)) < probabilities, "Success", "Failed"
    )
    result["Simulation Version"] = SIMULATION_VERSION
    return result
