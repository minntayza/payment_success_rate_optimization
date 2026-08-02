from __future__ import annotations

import pandas as pd
import pytest

from payment_dashboard.simulation import (
    SIMULATION_VERSION,
    simulate_transactions,
    success_probabilities,
)


def test_simulation_is_deterministic(sample_transactions: pd.DataFrame) -> None:
    first = simulate_transactions(sample_transactions, seed=42)
    second = simulate_transactions(sample_transactions, seed=42)

    pd.testing.assert_frame_equal(first, second)


def test_simulation_preserves_source_status(sample_transactions: pd.DataFrame) -> None:
    result = simulate_transactions(sample_transactions, seed=42)

    sorted_source = sample_transactions.sort_values(
        "Timestamp", kind="stable"
    ).reset_index(drop=True)
    assert (
        result["Source Transaction Status"].tolist()
        == sorted_source["Transaction Status"].tolist()
    )
    assert set(result["Transaction Status"]) <= {"Success", "Failed"}
    assert result["Simulation Version"].eq(SIMULATION_VERSION).all()


def test_gateway_a_outperforms_gateway_d_on_large_sample() -> None:
    large_transactions = pd.DataFrame(
        {
            "Transaction ID": [f"TX{index}" for index in range(8_000)],
            "Sender Account ID": ["S"] * 8_000,
            "Receiver Account ID": ["R"] * 8_000,
            "Transaction Amount": [500.0] * 8_000,
            "Transaction Type": ["Deposit"] * 8_000,
            "Timestamp": pd.date_range("2025-01-01", periods=8_000, freq="min"),
            "Transaction Status": ["Success"] * 8_000,
            "Fraud Flag": [False] * 8_000,
            "Geolocation (Latitude/Longitude)": ["A"] * 8_000,
            "Device Used": ["Desktop"] * 8_000,
            "Network Slice ID": ["Slice1"] * 8_000,
            "Latency (ms)": [5] * 8_000,
            "Slice Bandwidth (Mbps)": [100] * 8_000,
            "PIN Code": ["1111"] * 8_000,
        }
    )

    result = simulate_transactions(large_transactions, seed=42)
    rates = result.groupby("Bank Gateway")["Transaction Status"].apply(
        lambda values: values.eq("Success").mean()
    )

    assert rates["Gateway A"] > rates["Gateway D"]


@pytest.mark.parametrize(
    ("timestamp", "amount", "expected"),
    [
        ("2025-01-01 05:59:00+00:00", 500.0, 0.925),
        ("2025-01-01 06:00:00+00:00", 501.0, 0.94),
        ("2025-01-01 09:00:00+00:00", 1_000.0, 0.945),
        ("2025-01-01 17:59:00+00:00", 1_001.0, 0.935),
        ("2025-01-01 18:00:00+00:00", 500.0, 0.95),
    ],
)
def test_success_probabilities_apply_hour_and_amount_boundaries(
    timestamp: str, amount: float, expected: float
) -> None:
    frame = pd.DataFrame(
        {
            "Bank Gateway": ["Gateway A"],
            "Device Used": ["Desktop"],
            "Transaction Type": ["Deposit"],
            "Timestamp": [timestamp],
            "Transaction Amount": [amount],
        }
    )

    probability = success_probabilities(frame).iloc[0]

    assert probability == pytest.approx(expected)
