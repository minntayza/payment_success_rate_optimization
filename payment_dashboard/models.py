"""Typed data structures for the payment dashboard."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Immutable snapshot of computed dashboard data."""

    replay_frame: pd.DataFrame
    display_frame: pd.DataFrame
    alerts: pd.DataFrame
