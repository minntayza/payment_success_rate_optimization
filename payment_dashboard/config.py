"""Central configuration constants for the payment dashboard."""

from __future__ import annotations

from pathlib import Path

# Gateway assignment
GATEWAYS = ("Gateway A", "Gateway B", "Gateway C", "Gateway D")
DEFAULT_SEED = 20260728

# Controlled simulation probabilities. These values describe synthetic academic
# outcomes, not real gateway performance.
GATEWAY_BASE_SUCCESS_RATES = {
    "Gateway A": 0.94,
    "Gateway B": 0.91,
    "Gateway C": 0.88,
    "Gateway D": 0.85,
}
DEVICE_SUCCESS_ADJUSTMENTS = {"Desktop": 0.0, "Mobile": -0.015}
TRANSACTION_TYPE_SUCCESS_ADJUSTMENTS = {
    "Deposit": 0.01,
    "Transfer": -0.01,
    "Withdrawal": -0.02,
}
LOW_TRAFFIC_HOUR_ADJUSTMENT = -0.025  # 00:00-05:59 UTC
BUSINESS_HOUR_ADJUSTMENT = 0.005  # 09:00-17:59 UTC
MEDIUM_AMOUNT_SUCCESS_ADJUSTMENT = -0.01  # 500 < amount <= 1000
HIGH_AMOUNT_SUCCESS_ADJUSTMENT = -0.02  # amount > 1000
SIMULATION_PROBABILITY_RANGE = (0.55, 0.99)

# Alert thresholds
ALERT_WINDOW_SIZE = 50
ALERT_BASELINE_MIN_SIZE = 200
ALERT_THRESHOLD = 0.10  # 10 percentage points
P95_QUANTILE = 0.95

# Shared transaction outcome labels
SUCCESS_STATUS = "Success"
FAILED_STATUS = "Failed"

# Data paths
DEFAULT_DATA_PATH = Path("data/processed/transactions_with_gateways.csv")

# Chart styling
CHART_COLORS = ["#2563EB", "#06B6D4", "#8B5CF6", "#F59E0B"]

# Schema validation
STATUSES = frozenset({SUCCESS_STATUS, FAILED_STATUS})
TRANSACTION_TYPES = frozenset({"Transfer", "Deposit", "Withdrawal"})
DEVICES = frozenset({"Mobile", "Desktop", "Tablet"})

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
    }
)
