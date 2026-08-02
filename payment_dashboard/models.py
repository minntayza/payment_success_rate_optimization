"""Typed data structures for the payment dashboard."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

import pandas as pd


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Immutable snapshot of computed dashboard data."""

    replay_frame: pd.DataFrame
    display_frame: pd.DataFrame
    alerts: pd.DataFrame


class DataSource(str, Enum):  # noqa: UP042
    """Origin of the dashboard data shown to the user."""

    LIVE = "live"
    DEMO = "demo"


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Typed repository result consumed by the dashboard UI."""

    metrics: Mapping[str, int | float]
    gateway_summary: pd.DataFrame
    trend: pd.DataFrame
    failure_summary: pd.DataFrame
    alerts: pd.DataFrame
    transactions: pd.DataFrame
    total_transactions: int
    source: DataSource
    simulation_version: str
    diagnostic: str | None = None
