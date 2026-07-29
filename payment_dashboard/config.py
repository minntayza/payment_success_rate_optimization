"""Central configuration constants for the payment dashboard."""

from __future__ import annotations

from pathlib import Path

# Gateway assignment
GATEWAYS = ("Gateway A", "Gateway B", "Gateway C", "Gateway D")
DEFAULT_SEED = 20260728

# Alert thresholds
ALERT_WINDOW_SIZE = 50
ALERT_THRESHOLD = 0.10  # 10 percentage points

# Data paths
DEFAULT_DATA_PATH = Path("data/processed/transactions_with_gateways.csv")

# Chart styling
CHART_COLORS = ["#2563EB", "#06B6D4", "#8B5CF6", "#F59E0B"]

# Schema validation
STATUSES = frozenset({"Success", "Failed"})

REQUIRED_COLUMNS = frozenset(
    {
        "Transaction ID",
        "Sender Account ID",
        "Receiver Account ID",
        "Transaction Amount",
        "Transaction Type",
        "Timestamp",
        "Transaction Status",
        "Fraud Flag",
        "Geolocation (Latitude/Longitude)",
        "Device Used",
        "Network Slice ID",
        "Latency (ms)",
        "Slice Bandwidth (Mbps)",
        "PIN Code",
    }
)
