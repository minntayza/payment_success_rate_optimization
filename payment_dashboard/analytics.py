from __future__ import annotations

from datetime import date

import pandas as pd

from payment_dashboard.config import FAILED_STATUS, P95_QUANTILE, SUCCESS_STATUS


def add_latency_band(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["Latency Band"] = pd.cut(
        result["Latency (ms)"],
        bins=[-float("inf"), 5, 10, 15, float("inf")],
        labels=["0-5 ms", "6-10 ms", "11-15 ms", "16+ ms"],
    )
    return result


def summary_metrics(frame: pd.DataFrame) -> dict[str, int | float]:
    count = len(frame)
    success_rate = (
        frame["Transaction Status"].eq(SUCCESS_STATUS).mean() if count else 0.0
    )
    return {
        "transaction_count": count,
        "success_rate": float(success_rate),
        "failed_count": int(frame["Transaction Status"].eq(FAILED_STATUS).sum()),
        "average_latency_ms": float(frame["Latency (ms)"].mean()) if count else 0.0,
        "p95_latency_ms": (
            float(frame["Latency (ms)"].quantile(P95_QUANTILE)) if count else 0.0
        ),
    }


def gateway_summary(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.assign(
        is_success=frame["Transaction Status"].eq(SUCCESS_STATUS).astype(int)
    )
    return (
        working.groupby("Bank Gateway", observed=True)
        .agg(
            transaction_count=("Transaction ID", "count"),
            success_rate=("is_success", "mean"),
            average_latency_ms=("Latency (ms)", "mean"),
        )
        .reset_index()
        .sort_values("Bank Gateway")
    )


def failure_breakdown(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    failures = frame.loc[frame["Transaction Status"].eq(FAILED_STATUS)]
    return (
        failures.groupby(dimension, observed=True)
        .size()
        .rename("failed_count")
        .reset_index()
        .sort_values("failed_count", ascending=False)
    )


def success_rate_series(
    frame: pd.DataFrame,
    frequency: str = "15min",
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Timestamp", "success_rate", "transaction_count"])
    working = frame.assign(
        is_success=frame["Transaction Status"].eq(SUCCESS_STATUS).astype(int)
    ).set_index("Timestamp")
    return (
        working.resample(frequency)
        .agg(
            success_rate=("is_success", "mean"),
            transaction_count=("is_success", "size"),
        )
        .dropna(subset=["success_rate"])
        .reset_index()
    )


def apply_filters(
    frame: pd.DataFrame,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for column, selected in (
        ("Bank Gateway", gateways),
        ("Transaction Type", transaction_types),
        ("Device Used", devices),
        ("Transaction Status", statuses),
    ):
        if selected:
            mask &= frame[column].isin(selected)
    if start is not None:
        mask &= frame["Timestamp"].dt.date >= start
    if end is not None:
        mask &= frame["Timestamp"].dt.date <= end
    return frame.loc[mask].copy()
