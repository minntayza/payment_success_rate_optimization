from __future__ import annotations

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
        gateway_rows = replay_frame.loc[replay_frame["Bank Gateway"].eq(gateway)]
        recent = gateway_rows.tail(window_size)
        if shared_history:
            baseline_rows = gateway_rows.iloc[: max(0, len(gateway_rows) - window_size)]
        else:
            baseline_rows = full_frame.loc[full_frame["Bank Gateway"].eq(gateway)]
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
        drop = round(baseline - float(rolling_rate), 12) if sufficient else float("nan")
        records.append(
            {
                "Bank Gateway": gateway,
                "baseline_rate": baseline,
                "rolling_rate": rolling_rate,
                "baseline_count": len(baseline_rows),
                "recent_count": len(recent),
                "drop": drop,
                "has_sufficient_history": sufficient,
                "is_alert": sufficient and drop >= threshold,
            }
        )

    return pd.DataFrame.from_records(records)
