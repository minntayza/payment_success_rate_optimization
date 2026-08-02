"""Common repository contract and offline pandas implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.analytics import (
    add_latency_band,
    apply_filters,
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)
from payment_dashboard.models import DashboardSnapshot, DataSource

LEGACY_SIMULATION_VERSION = "legacy-v0"


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    """Validated dashboard query filters shared by every repository."""

    gateways: tuple[str, ...] = ()
    transaction_types: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start date must be on or before end date")


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Validated bounded request for a deterministic transaction page."""

    number: int = 1
    size: int = 50

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("page number must be at least 1")
        if not 1 <= self.size <= 100:
            raise ValueError("page size must be between 1 and 100")


class DashboardRepository(Protocol):
    """A source that can supply one complete dashboard snapshot."""

    def fetch(
        self,
        filters: DashboardFilters,
        page: PageRequest,
    ) -> DashboardSnapshot:
        """Return the aggregates and bounded transaction page for a query."""


@dataclass(frozen=True, slots=True)
class PandasDashboardRepository:
    """Offline/demo adapter that implements the dashboard repository contract."""

    frame: pd.DataFrame

    def fetch(
        self,
        filters: DashboardFilters,
        page: PageRequest,
    ) -> DashboardSnapshot:
        """Filter a frame, derive dashboard aggregates, and return one page."""
        full_frame = self.frame.sort_values(
            ["Timestamp", "Transaction ID"], kind="stable"
        ).reset_index(drop=True)
        display_frame = add_latency_band(
            apply_filters(
                full_frame,
                list(filters.gateways),
                list(filters.transaction_types),
                list(filters.devices),
                list(filters.statuses),
                filters.start,
                filters.end,
            )
        )
        total_transactions = len(display_frame)
        offset = (page.number - 1) * page.size
        transactions = (
            display_frame.sort_values(
                ["Timestamp", "Transaction ID"],
                ascending=[False, True],
                kind="stable",
            )
            .iloc[offset : offset + page.size]
            .copy()
        )
        return DashboardSnapshot(
            metrics=summary_metrics(display_frame),
            gateway_summary=gateway_summary(display_frame),
            trend=success_rate_series(display_frame),
            failure_summary=failure_breakdown(display_frame, dimension="Latency Band"),
            alerts=evaluate_alerts(full_frame, full_frame),
            transactions=transactions,
            total_transactions=total_transactions,
            source=DataSource.DEMO,
            simulation_version=_simulation_version(full_frame),
            diagnostic=None,
        )


def _simulation_version(frame: pd.DataFrame) -> str:
    """Return the frame's recorded version, retaining the legacy fallback."""
    if "Simulation Version" not in frame:
        return LEGACY_SIMULATION_VERSION
    versions = frame["Simulation Version"].dropna()
    return str(versions.iloc[0]) if not versions.empty else LEGACY_SIMULATION_VERSION
