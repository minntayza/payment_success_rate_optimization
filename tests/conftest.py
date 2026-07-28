from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Transaction ID": ["TX1", "TX2", "TX3", "TX4"],
            "Sender Account ID": ["S1", "S2", "S3", "S4"],
            "Receiver Account ID": ["R1", "R2", "R3", "R4"],
            "Transaction Amount": [100.0, 200.0, 300.0, 400.0],
            "Transaction Type": ["Transfer", "Deposit", "Withdrawal", "Transfer"],
            "Timestamp": [
                "2025-01-17 10:03:00",
                "2025-01-17 10:01:00",
                "2025-01-17 10:04:00",
                "2025-01-17 10:02:00",
            ],
            "Transaction Status": ["Success", "Failed", "Success", "Failed"],
            "Fraud Flag": [False, False, True, True],
            "Geolocation (Latitude/Longitude)": ["A", "B", "C", "D"],
            "Device Used": ["Mobile", "Desktop", "Mobile", "Desktop"],
            "Network Slice ID": ["Slice1", "Slice2", "Slice1", "Slice2"],
            "Latency (ms)": [4, 12, 8, 20],
            "Slice Bandwidth (Mbps)": [100, 110, 120, 130],
            "PIN Code": ["1111", "2222", "3333", "4444"],
        }
    )
