"""Deterministic synthetic transactions for the hosted academic demo."""

from __future__ import annotations

import numpy as np
import pandas as pd

from payment_dashboard.config import DEFAULT_SEED
from payment_dashboard.simulation import simulate_transactions


def generate_demo_transactions(
    row_count: int = 1000,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """Return schema-compatible transactions using the controlled simulation."""
    rng = np.random.default_rng(seed)
    transaction_numbers = np.arange(1, row_count + 1)
    timestamps = pd.date_range(
        "2025-01-17 08:00:00",
        periods=row_count,
        freq="min",
    )

    frame = pd.DataFrame(
        {
            "Transaction ID": [f"DEMO-{number:05d}" for number in transaction_numbers],
            "Sender Account ID": [
                f"S-{number:04d}" for number in rng.integers(1, 500, row_count)
            ],
            "Receiver Account ID": [
                f"R-{number:04d}" for number in rng.integers(1, 500, row_count)
            ],
            "Transaction Amount": rng.uniform(5, 5000, row_count).round(2),
            "Transaction Type": rng.choice(
                ["Transfer", "Deposit", "Withdrawal"], row_count
            ),
            "Timestamp": timestamps,
            "Transaction Status": rng.choice(["Success", "Failed"], row_count),
            "Fraud Flag": rng.random(row_count) < 0.05,
            "Geolocation (Latitude/Longitude)": rng.choice(
                ["Yangon", "Mandalay", "Naypyidaw", "Bago"],
                row_count,
            ),
            "Device Used": rng.choice(["Mobile", "Desktop"], row_count),
            "Network Slice ID": rng.choice(
                ["Slice-1", "Slice-2", "Slice-3"],
                row_count,
            ),
            "Latency (ms)": rng.uniform(3, 150, row_count).round(2),
            "Slice Bandwidth (Mbps)": rng.uniform(25, 500, row_count).round(2),
            "PIN Code": [
                f"{number:04d}" for number in rng.integers(0, 10000, row_count)
            ],
        }
    )
    return simulate_transactions(frame, seed=seed)
