"""Tests for the focused dashboard view composition."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from payment_dashboard.ui import views


@pytest.fixture
def snapshot() -> SimpleNamespace:
    """Provide a populated snapshot-shaped object for view composition."""
    return SimpleNamespace(
        alerts=pd.DataFrame({"status": ["active"]}),
        transactions=pd.DataFrame({"Transaction ID": ["TX-1"]}),
    )


def test_overview_renders_operational_summary(
    monkeypatch: pytest.MonkeyPatch, snapshot: SimpleNamespace
) -> None:
    """Catch an overview that omits or reorders an operational summary section."""
    calls: list[str] = []
    for name in (
        "render_kpis",
        "render_success_trend",
        "render_gateway_health",
        "render_recent_transactions",
    ):
        monkeypatch.setattr(
            views,
            name,
            lambda *args, _name=name, **kwargs: calls.append(_name),
        )
    monkeypatch.setattr(views.st, "columns", lambda *_: (nullcontext(), nullcontext()))

    views.render_overview(snapshot, "en")

    assert calls == [
        "render_kpis",
        "render_success_trend",
        "render_gateway_health",
        "render_recent_transactions",
    ]


def test_gateways_does_not_render_transaction_table(
    monkeypatch: pytest.MonkeyPatch, snapshot: SimpleNamespace
) -> None:
    """Catch the gateway view leaking the transaction table into its analysis."""
    recent = Mock()
    calls: list[str] = []
    monkeypatch.setattr(views, "render_recent_transactions", recent)
    for name in (
        "render_gateway_performance",
        "render_failure_analysis",
        "render_gateway_health",
    ):
        monkeypatch.setattr(
            views,
            name,
            lambda *args, _name=name, **kwargs: calls.append(_name),
        )

    views.render_gateways(snapshot, "en")

    assert calls == [
        "render_gateway_performance",
        "render_failure_analysis",
        "render_gateway_health",
    ]
    recent.assert_not_called()


def test_transactions_renders_the_full_table_and_guide(
    monkeypatch: pytest.MonkeyPatch, snapshot: SimpleNamespace
) -> None:
    """Catch the transaction view limiting the table or omitting its guide."""
    table = Mock()
    guide = Mock()
    monkeypatch.setattr(views, "render_recent_transactions", table)
    monkeypatch.setattr(views, "render_interpretation_guide", guide)

    views.render_transactions(snapshot, "en")

    table.assert_called_once_with(snapshot.transactions, "en", limit=None)
    guide.assert_called_once_with("en")


def test_routing_lab_delegates_to_the_optimization_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch Routing Lab rendering anything other than the supplied report."""
    report = object()
    renderer = Mock()
    monkeypatch.setattr(views, "render_optimization_report", renderer)

    views.render_routing_lab(report, "en")

    renderer.assert_called_once_with(report, "en")


@pytest.mark.parametrize(
    ("renderer", "blocked_renderer"),
    (
        ("render_overview", "render_kpis"),
        ("render_gateways", "render_gateway_performance"),
        ("render_transactions", "render_recent_transactions"),
    ),
)
def test_empty_snapshot_renders_empty_state_in_active_view(
    monkeypatch: pytest.MonkeyPatch,
    renderer: str,
    blocked_renderer: str,
) -> None:
    """Catch an active analytical view trying to render empty data."""
    empty_snapshot = SimpleNamespace(
        alerts=pd.DataFrame(),
        transactions=pd.DataFrame(),
    )
    empty_state = Mock()
    blocked = Mock()
    monkeypatch.setattr(views, "render_empty_state", empty_state)
    monkeypatch.setattr(views, blocked_renderer, blocked)

    getattr(views, renderer)(empty_snapshot, "en")

    empty_state.assert_called_once_with("en")
    blocked.assert_not_called()
