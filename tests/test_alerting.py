from __future__ import annotations

import pandas as pd

from payment_dashboard.alerting import calculate_baselines, evaluate_alerts


def transactions(
    gateway: str,
    successes: int,
    failures: int,
    prefix: str,
) -> pd.DataFrame:
    statuses = ["Success"] * successes + ["Failed"] * failures
    return pd.DataFrame(
        {
            "Transaction ID": [f"{prefix}{index}" for index in range(len(statuses))],
            "Bank Gateway": gateway,
            "Transaction Status": statuses,
        }
    )


def test_calculate_baselines_uses_full_gateway_history():
    full = pd.concat(
        [
            transactions("Gateway A", 3, 1, "A"),
            transactions("Gateway B", 1, 3, "B"),
        ],
        ignore_index=True,
    )

    result = calculate_baselines(full)

    assert result["Gateway A"] == 0.75
    assert result["Gateway B"] == 0.25
    assert pd.isna(result["Gateway C"])
    assert pd.isna(result["Gateway D"])


def test_exact_ten_point_drop_triggers():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 30, 20, "R")

    result = evaluate_alerts(full, replay).iloc[0]

    assert result["baseline_rate"] == 0.7
    assert result["rolling_rate"] == 0.6
    assert result["drop"] == 0.1
    assert bool(result["is_alert"]) is True


def test_less_than_ten_point_drop_does_not_trigger():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 31, 19, "R")

    result = evaluate_alerts(full, replay).iloc[0]

    assert result["drop"] == 0.08
    assert bool(result["is_alert"]) is False


def test_fewer_than_fifty_gateway_transactions_is_insufficient():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 29, 20, "R")

    result = evaluate_alerts(full, replay).iloc[0]

    assert bool(result["has_sufficient_history"]) is False
    assert bool(result["is_alert"]) is False
    assert pd.isna(result["rolling_rate"])
    assert pd.isna(result["drop"])


def test_latest_fifty_transactions_are_used():
    full = transactions("Gateway A", 70, 30, "F")
    older = transactions("Gateway A", 50, 0, "O")
    latest = transactions("Gateway A", 25, 25, "L")

    result = evaluate_alerts(
        full,
        pd.concat([older, latest], ignore_index=True),
    ).iloc[0]

    assert result["rolling_rate"] == 0.5
    assert bool(result["is_alert"]) is True


def test_evaluate_alerts_returns_every_gateway():
    full = pd.concat(
        [
            transactions("Gateway A", 70, 30, "A"),
            transactions("Gateway B", 60, 40, "B"),
            transactions("Gateway C", 50, 50, "C"),
            transactions("Gateway D", 40, 60, "D"),
        ],
        ignore_index=True,
    )

    result = evaluate_alerts(full, full)

    assert result["Bank Gateway"].tolist() == [
        "Gateway A",
        "Gateway B",
        "Gateway C",
        "Gateway D",
    ]
