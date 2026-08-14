from __future__ import annotations

from math import sqrt

import pandas as pd

from payment_dashboard.config import (
    ALERT_BASELINE_MIN_SIZE,
    ALERT_THRESHOLD,
    ALERT_WINDOW_SIZE,
    GATEWAYS,
    SUCCESS_STATUS,
)


def calculate_baselines(full_frame: pd.DataFrame) -> pd.Series:
    return (
        full_frame.assign(
            is_success=full_frame["Transaction Status"].eq(SUCCESS_STATUS).astype(int)
        )
        .groupby("Bank Gateway", observed=True)["is_success"]
        .mean()
        .reindex(GATEWAYS)
    )


def difference_of_proportions_interval(
    baseline_successes: int,
    baseline_count: int,
    recent_successes: int,
    recent_count: int,
) -> tuple[float, float]:
    """Return a 95% Wald interval for baseline minus recent success rate."""
    if baseline_count <= 0 or recent_count <= 0:
        return float("nan"), float("nan")
    baseline_rate = baseline_successes / baseline_count
    recent_rate = recent_successes / recent_count
    difference = baseline_rate - recent_rate
    standard_error = sqrt(
        baseline_rate * (1 - baseline_rate) / baseline_count
        + recent_rate * (1 - recent_rate) / recent_count
    )
    margin = 1.96 * standard_error
    return difference - margin, difference + margin


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    if "Timestamp" not in frame:
        return frame.reset_index(drop=True)
    keys = ["Timestamp"]
    if "Transaction ID" in frame:
        keys.append("Transaction ID")
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


def _boundary(frame: pd.DataFrame, position: str) -> pd.Timestamp | None:
    if frame.empty or "Timestamp" not in frame:
        return None
    values = pd.to_datetime(frame["Timestamp"], utc=True)
    value = values.iloc[0] if position == "start" else values.iloc[-1]
    return pd.Timestamp(value)


def evaluate_alerts(
    full_frame: pd.DataFrame,
    replay_frame: pd.DataFrame,
    window_size: int = ALERT_WINDOW_SIZE,
    threshold: float = ALERT_THRESHOLD,
    baseline_min_size: int = ALERT_BASELINE_MIN_SIZE,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    shared_history = (
        "Transaction ID" in full_frame
        and "Transaction ID" in replay_frame
        and bool(
            set(replay_frame["Transaction ID"].astype(str))
            & set(full_frame["Transaction ID"].astype(str))
        )
    )

    for gateway in GATEWAYS:
        gateway_rows = _ordered(
            replay_frame.loc[replay_frame["Bank Gateway"].eq(gateway)]
        )
        recent = gateway_rows.tail(window_size)
        if shared_history:
            baseline_rows = gateway_rows.iloc[: max(0, len(gateway_rows) - window_size)]
        else:
            baseline_rows = _ordered(
                full_frame.loc[full_frame["Bank Gateway"].eq(gateway)]
            )
        sufficient = (
            len(recent) >= window_size and len(baseline_rows) >= baseline_min_size
        )
        rolling_rate = (
            recent["Transaction Status"].eq(SUCCESS_STATUS).mean()
            if sufficient
            else float("nan")
        )
        baseline = (
            float(baseline_rows["Transaction Status"].eq(SUCCESS_STATUS).mean())
            if not baseline_rows.empty
            else float("nan")
        )
        baseline_successes = int(
            baseline_rows["Transaction Status"].eq(SUCCESS_STATUS).sum()
        )
        recent_successes = int(recent["Transaction Status"].eq(SUCCESS_STATUS).sum())
        lower, upper = (
            difference_of_proportions_interval(
                baseline_successes,
                len(baseline_rows),
                recent_successes,
                len(recent),
            )
            if sufficient
            else (float("nan"), float("nan"))
        )
        drop = round(baseline - float(rolling_rate), 12) if sufficient else float("nan")
        records.append(
            {
                "Bank Gateway": gateway,
                "baseline_rate": baseline,
                "rolling_rate": rolling_rate,
                "baseline_count": len(baseline_rows),
                "recent_count": len(recent),
                "baseline_start": _boundary(baseline_rows, "start"),
                "baseline_end": _boundary(baseline_rows, "end"),
                "recent_start": _boundary(recent, "start"),
                "recent_end": _boundary(recent, "end"),
                "drop": drop,
                "drop_ci_lower": lower,
                "drop_ci_upper": upper,
                "has_sufficient_history": sufficient,
                "is_alert": sufficient and drop >= threshold and lower > 0,
            }
        )

    return pd.DataFrame.from_records(records)
