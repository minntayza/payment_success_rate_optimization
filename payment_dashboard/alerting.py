from __future__ import annotations

import pandas as pd

from payment_dashboard.data_loader import GATEWAYS


def calculate_baselines(full_frame: pd.DataFrame) -> pd.Series:
    return (
        full_frame.assign(
            is_success=full_frame["Transaction Status"].eq("Success").astype(int)
        )
        .groupby("Bank Gateway", observed=True)["is_success"]
        .mean()
        .reindex(GATEWAYS)
    )


def evaluate_alerts(
    full_frame: pd.DataFrame,
    replay_frame: pd.DataFrame,
    window_size: int = 50,
    threshold: float = 0.10,
) -> pd.DataFrame:
    baselines = calculate_baselines(full_frame)
    records: list[dict[str, object]] = []

    for gateway in GATEWAYS:
        gateway_rows = replay_frame.loc[
            replay_frame["Bank Gateway"].eq(gateway)
        ]
        sufficient = len(gateway_rows) >= window_size
        rolling_rate = (
            gateway_rows.tail(window_size)["Transaction Status"]
            .eq("Success")
            .mean()
            if sufficient
            else float("nan")
        )
        baseline = float(baselines[gateway])
        drop = (
            round(baseline - float(rolling_rate), 12)
            if sufficient
            else float("nan")
        )
        records.append(
            {
                "Bank Gateway": gateway,
                "baseline_rate": baseline,
                "rolling_rate": rolling_rate,
                "drop": drop,
                "has_sufficient_history": sufficient,
                "is_alert": sufficient and drop >= threshold,
            }
        )

    return pd.DataFrame.from_records(records)
