"""Contract tests for dashboard data repositories."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    DataSource,
    PageRequest,
    PandasDashboardRepository,
)


@pytest.fixture
def prepared_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Transaction ID": ["TX-3", "TX-1", "TX-2", "TX-4"],
            "Transaction Type": ["Transfer", "Transfer", "Deposit", "Transfer"],
            "Timestamp": pd.to_datetime(
                [
                    "2025-01-17 10:03:00",
                    "2025-01-17 10:03:00",
                    "2025-01-17 10:02:00",
                    "2025-01-17 10:01:00",
                ]
            ),
            "Transaction Status": ["Success", "Failed", "Success", "Failed"],
            "Device Used": ["Mobile", "Desktop", "Mobile", "Desktop"],
            "Latency (ms)": [4, 12, 8, 20],
            "Bank Gateway": ["Gateway A", "Gateway A", "Gateway A", "Gateway B"],
            "Simulation Version": ["controlled-v1"] * 4,
        }
    )


def test_pandas_repository_filters_and_pages(prepared_fixture: pd.DataFrame) -> None:
    """A filtered transaction page never includes rows outside the query."""
    repository = PandasDashboardRepository(prepared_fixture)

    snapshot = repository.fetch(
        DashboardFilters(gateways=("Gateway A",)),
        PageRequest(number=1, size=2),
    )

    assert snapshot.source is DataSource.DEMO
    assert len(snapshot.transactions) <= 2
    assert snapshot.total_transactions >= len(snapshot.transactions)
    assert set(snapshot.transactions["Bank Gateway"]) <= {"Gateway A"}


def test_page_size_is_bounded() -> None:
    """Oversized pages are rejected instead of allowing unbounded reads."""
    with pytest.raises(ValueError, match="page size"):
        PageRequest(number=1, size=501)


def test_page_number_and_date_range_are_validated() -> None:
    """Invalid query bounds fail before a repository can execute them."""
    with pytest.raises(ValueError, match="page number"):
        PageRequest(number=0, size=1)
    with pytest.raises(ValueError, match="start date"):
        DashboardFilters(start=date(2025, 1, 18), end=date(2025, 1, 17))


def test_pandas_repository_sorts_pages_and_exposes_snapshot_metadata(
    prepared_fixture: pd.DataFrame,
) -> None:
    """Pages are deterministic and retain source metadata for the UI."""
    snapshot = PandasDashboardRepository(prepared_fixture).fetch(
        DashboardFilters(), PageRequest(number=1, size=2)
    )

    assert snapshot.transactions["Transaction ID"].tolist() == ["TX-1", "TX-3"]
    assert snapshot.metrics["transaction_count"] == 4
    assert snapshot.simulation_version == "controlled-v1"
    assert snapshot.diagnostic is None
    assert set(snapshot.failure_summary.columns) == {"Latency Band", "failed_count"}
    assert len(snapshot.alerts) == 4
