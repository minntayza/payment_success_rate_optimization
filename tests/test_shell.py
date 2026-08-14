"""Tests for the command-center navigation shell."""

from unittest.mock import Mock

import pytest

from payment_dashboard.dashboard_repository import DashboardFilters
from payment_dashboard.ui import shell
from payment_dashboard.ui.shell import (
    FILTERED_VIEWS,
    DashboardView,
    active_view,
    render_filter_bar,
)


def test_filtered_views_are_explicit() -> None:
    """Changing a filtered view must not silently affect another view."""
    assert {
        DashboardView.OVERVIEW,
        DashboardView.GATEWAYS,
        DashboardView.TRANSACTIONS,
    } == FILTERED_VIEWS


def test_active_view_defaults_to_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset command-center selection must open the overview."""
    monkeypatch.setattr(shell.st, "session_state", {})

    assert active_view() is DashboardView.OVERVIEW


def test_filter_bar_returns_repository_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty compact-filter selections must produce the repository default."""
    monkeypatch.setattr(shell.st, "multiselect", lambda *args, **kwargs: [])
    monkeypatch.setattr(shell.st, "date_input", lambda *args, **kwargs: [])
    monkeypatch.setattr(shell.st, "button", Mock())

    assert render_filter_bar("en", Mock(), Mock()) == DashboardFilters()
