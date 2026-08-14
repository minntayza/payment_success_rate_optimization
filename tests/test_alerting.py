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
            "Timestamp": pd.date_range("2025-01-01", periods=len(statuses), freq="min"),
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
    full = transactions("Gateway A", 200, 0, "F")
    replay = transactions("Gateway A", 45, 5, "R")

    result = evaluate_alerts(full, replay, window_size=50).iloc[0]

    assert result["baseline_rate"] == 1.0
    assert result["rolling_rate"] == 0.9
    assert result["drop"] == 0.1
    assert result["drop_ci_lower"] > 0
    assert bool(result["is_alert"]) is True


def test_less_than_ten_point_drop_does_not_trigger():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 31, 19, "R")

    result = evaluate_alerts(full, replay, window_size=50, baseline_min_size=1).iloc[0]

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
        baseline_min_size=1,
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


def test_overlapping_replay_excludes_recent_window_from_baseline():
    history = transactions("Gateway A", 70, 30, "A")
    result = evaluate_alerts(history, history, window_size=20).iloc[0]
    assert result["baseline_count"] == 80
    assert result["recent_count"] == 20


def test_alert_requires_two_hundred_earlier_baseline_attempts() -> None:
    insufficient = transactions("Gateway A", 200, 49, "I")
    sufficient = transactions("Gateway A", 200, 50, "S")
    insufficient_result = evaluate_alerts(insufficient, insufficient).iloc[0]
    sufficient_result = evaluate_alerts(sufficient, sufficient).iloc[0]
    assert insufficient_result["baseline_count"] == 199
    assert bool(insufficient_result["has_sufficient_history"]) is False
    assert sufficient_result["baseline_count"] == 200
    assert bool(sufficient_result["has_sufficient_history"]) is True


def test_alert_evidence_contains_non_overlapping_boundaries_and_interval() -> None:
    history = transactions("Gateway A", 225, 25, "A")
    result = evaluate_alerts(history, history).iloc[0]

    assert result["baseline_count"] == 200
    assert result["recent_count"] == 50
    assert result["baseline_start"] == pd.Timestamp("2025-01-01 00:00:00Z")
    assert result["baseline_end"] < result["recent_start"]
    assert result["recent_end"] == pd.Timestamp("2025-01-01 04:09:00Z")
    assert result["drop_ci_lower"] <= result["drop"] <= result["drop_ci_upper"]


def test_practical_drop_without_statistical_support_does_not_alert() -> None:
    baseline = transactions("Gateway A", 140, 60, "B")
    recent = transactions("Gateway A", 30, 20, "R")
    recent["Timestamp"] = recent["Timestamp"] + pd.offsets.Day(1)
    history = pd.concat([baseline, recent], ignore_index=True)

    result = evaluate_alerts(history, history).iloc[0]

    assert result["drop"] == 0.1
    assert result["drop_ci_lower"] < 0
    assert bool(result["is_alert"]) is False
