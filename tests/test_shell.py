"""Tests for the command-center navigation shell."""

from contextlib import nullcontext
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


def test_filter_bar_restores_values_after_widget_is_hidden_for_a_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Routing/Admin visits must not erase analytical filter selections."""
    session: dict[str, object] = {}
    selected_gateway = False

    def multiselect(*_args: object, **kwargs: object) -> list[str]:
        nonlocal selected_gateway
        key = str(kwargs["key"])
        if key == "gateway_filter" and not selected_gateway:
            selected_gateway = True
            session[key] = ["Gateway C"]
            callback = kwargs["on_change"]
            callback(*kwargs.get("args", ()))
        return list(session.get(key, []))

    monkeypatch.setattr(shell.st, "session_state", session)
    monkeypatch.setattr(shell.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(
        shell.st,
        "columns",
        lambda _count: tuple(nullcontext() for _ in range(5)),
    )
    monkeypatch.setattr(shell.st, "multiselect", multiselect)
    monkeypatch.setattr(
        shell.st,
        "date_input",
        lambda *_args, **kwargs: session.get(str(kwargs["key"]), []),
    )
    monkeypatch.setattr(shell.st, "button", Mock())

    selected = render_filter_bar("en", Mock(), Mock())
    for key in (
        "gateway_filter",
        "transaction_type_filter",
        "device_filter",
        "status_filter",
        "date_filter",
    ):
        session.pop(key, None)
    restored = render_filter_bar("en", Mock(), Mock())

    assert selected.gateways == ("Gateway C",)
    assert restored == selected
