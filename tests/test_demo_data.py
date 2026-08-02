"""Tests for deterministic academic demo transactions."""

import pandas as pd

from payment_dashboard.data_loader import validate_transactions
from payment_dashboard.demo_data import generate_demo_transactions
from payment_dashboard.simulation import SIMULATION_VERSION


def test_demo_transactions_are_valid_deterministic_and_chronological() -> None:
    first = generate_demo_transactions(row_count=240, seed=42)
    second = generate_demo_transactions(row_count=240, seed=42)

    pd.testing.assert_frame_equal(first, second)
    validate_transactions(first, require_gateway=True)
    assert first["Timestamp"].is_monotonic_increasing
    assert first["Transaction ID"].is_unique
    assert set(first["Transaction Status"]) == {"Success", "Failed"}
    assert set(first["Bank Gateway"]) == {
        "Gateway A",
        "Gateway B",
        "Gateway C",
        "Gateway D",
    }
    assert set(first["Simulation Version"]) == {SIMULATION_VERSION}
    assert first["Source Transaction Status"].equals(
        second["Source Transaction Status"]
    )


def test_demo_uses_controlled_gateway_outcomes() -> None:
    frame = generate_demo_transactions(row_count=10_000, seed=42)

    rates = frame.groupby("Bank Gateway")["Transaction Status"].apply(
        lambda values: values.eq("Success").mean()
    )

    assert (
        rates["Gateway A"]
        > rates["Gateway B"]
        > rates["Gateway C"]
        > rates["Gateway D"]
    )
    assert set(frame["Transaction Type"]) <= {"Transfer", "Deposit", "Withdrawal"}
    assert set(frame["Device Used"]) <= {"Mobile", "Desktop"}
