"""Tests for deterministic academic demo transactions."""

import pandas as pd

from payment_dashboard.data_loader import validate_transactions
from payment_dashboard.demo_data import generate_demo_transactions


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
