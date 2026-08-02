from __future__ import annotations

import os
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import streamlit as st
from pytest import MonkeyPatch, fixture
from streamlit.testing.v1 import AppTest

import payment_dashboard.app as app_module
import payment_dashboard.ui.sections as sections_module
from payment_dashboard.ai_brief import (
    AIBriefError,
    build_brief_facts,
    facts_fingerprint,
)
from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.app import (
    _render_language_toggle,
    _render_sidebar,
    build_dashboard_state,
)
from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)
from payment_dashboard.models import DashboardSnapshot, DashboardState, DataSource
from payment_dashboard.ui.sections import (
    render_ai_operations_brief,
    render_gateway_health,
    render_kpis,
    render_recent_transactions,
    render_story_hero,
)


def dashboard_fixture(sample_transactions: pd.DataFrame) -> pd.DataFrame:
    full = pd.concat([sample_transactions] * 60, ignore_index=True)
    full["Transaction ID"] = [f"TX{i}" for i in range(len(full))]
    full["Timestamp"] = pd.date_range(
        "2025-01-01",
        periods=len(full),
        freq="min",
    )
    full["Bank Gateway"] = [
        f"Gateway {chr(65 + (index % 4))}" for index in range(len(full))
    ]
    return full


@pytest.mark.integration
def test_language_toggle_defaults_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(st, "toggle", lambda *_, **kwargs: kwargs["value"])

    assert _render_language_toggle() == "en"


@pytest.mark.integration
def test_burmese_mode_keeps_neutral_filter_values(
    monkeypatch: pytest.MonkeyPatch, sample_transactions: pd.DataFrame
) -> None:
    full_frame = dashboard_fixture(sample_transactions)
    multiselect = MagicMock(return_value=[])
    monkeypatch.setattr(st.sidebar, "multiselect", multiselect)
    monkeypatch.setattr(st.sidebar, "slider", lambda *_, **kwargs: kwargs["value"])
    monkeypatch.setattr(st.sidebar, "date_input", lambda *_, **kwargs: kwargs["value"])

    _render_sidebar(full_frame, language="my")

    gateway_options = multiselect.call_args_list[0].args[1]
    assert "Gateway A" in gateway_options


@pytest.mark.integration
def test_burmese_session_state_sets_burmese_browser_page_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configured: dict[str, object] = {}

    class TrackedSessionState(dict[str, object]):
        def get(self, key: str, default: object = None) -> object:
            events.append("session_state")
            return super().get(key, default)

    class StopAfterPageConfig(Exception):
        pass

    def capture_page_config(**values: object) -> None:
        events.append("set_page_config")
        configured.update(values)

    def stop_after_page_config() -> None:
        events.append("apply_page_style")
        raise StopAfterPageConfig

    monkeypatch.setattr(
        app_module.st,
        "session_state",
        TrackedSessionState(language_toggle=True),
    )
    monkeypatch.setattr(app_module.st, "set_page_config", capture_page_config)
    monkeypatch.setattr(app_module, "apply_page_style", stop_after_page_config)

    with pytest.raises(StopAfterPageConfig):
        app_module.render_app()

    assert configured["page_title"] == "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်"
    assert events == ["session_state", "set_page_config", "apply_page_style"]


@pytest.mark.integration
def test_alerts_ignore_display_filters(sample_transactions):
    full = dashboard_fixture(sample_transactions)

    state = build_dashboard_state(
        full_frame=full,
        replay_count=220,
        gateways=["Gateway D"],
        transaction_types=[],
        devices=[],
        statuses=["Failed"],
        start=None,
        end=None,
    )

    assert len(state.replay_frame) == 220
    assert set(state.display_frame["Bank Gateway"]) <= {"Gateway D"}
    assert set(state.display_frame["Transaction Status"]) <= {"Failed"}
    assert state.alerts["has_sufficient_history"].all()


@pytest.mark.integration
def test_replay_count_limits_displayed_transactions(sample_transactions):
    full = dashboard_fixture(sample_transactions)

    state = build_dashboard_state(
        full_frame=full,
        replay_count=80,
        gateways=[],
        transaction_types=[],
        devices=[],
        statuses=[],
        start=None,
        end=None,
    )

    assert len(state.replay_frame) == 80
    assert len(state.display_frame) == 80
    assert "Latency Band" in state.display_frame
    assert not state.alerts["has_sufficient_history"].any()


@pytest.mark.integration
def test_streamlit_app_starts_without_exception():
    app_path = Path(__file__).parents[1] / "payment_dashboard" / "app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception


@pytest.mark.integration
def test_degraded_mode_is_explicit_and_disables_editing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.setenv("PAYMENT_DEMO_MODE", "1")
    monkeypatch.setenv("PAYMENT_DATA_PATH", "/missing/dashboard-data.csv")
    monkeypatch.setattr(app_module, "_apply_streamlit_secrets", lambda: None)

    app = AppTest.from_file("streamlit_app.py").run(timeout=10)

    assert not app.exception
    assert any("DEMO" in item.value for item in app.markdown)
    assert any("simulated demo data" in item.value.lower() for item in app.warning)
    assert app.button(key="database_retry")
    assert not app.tabs


@pytest.mark.integration
def test_transaction_page_changes_without_full_collection_load(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.setenv("PAYMENT_DEMO_MODE", "1")
    monkeypatch.setenv("PAYMENT_DATA_PATH", "/missing/dashboard-data.csv")
    monkeypatch.setattr(app_module, "_apply_streamlit_secrets", lambda: None)

    app = AppTest.from_file("streamlit_app.py").run(timeout=10)

    assert not app.exception
    assert app.number_input(key="transaction_page").value == 1
    first_page = app.dataframe[-1].value

    app.button(key="transaction_next").click().run(timeout=10)

    second_page = app.dataframe[-1].value
    assert not app.exception
    assert app.number_input(key="transaction_page").value == 2
    assert len(first_page) == 50
    assert len(second_page) == 50
    assert set(first_page["Transaction ID"]).isdisjoint(second_page["Transaction ID"])


@pytest.mark.integration
def test_app_imports_as_installed_package():
    """Verify app.py works as an installed package (no sys.path hacks)."""
    result = subprocess.run(
        [sys.executable, "-c", "from payment_dashboard.app import render_app"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sibling_loader_registers_module_before_execution(
    monkeypatch: MonkeyPatch,
) -> None:
    previous = sys.modules["payment_dashboard.config"]
    monkeypatch.delitem(sys.modules, "payment_dashboard.config")

    loaded = app_module._load("config")

    assert sys.modules["payment_dashboard.config"] is loaded
    sys.modules["payment_dashboard.config"] = previous


def test_load_data_uses_demo_generator_when_enabled(
    monkeypatch: MonkeyPatch,
    sample_transactions: pd.DataFrame,
) -> None:
    expected = dashboard_fixture(sample_transactions)
    monkeypatch.setenv("PAYMENT_DEMO_MODE", "1")
    monkeypatch.setenv("PAYMENT_DATA_PATH", "/missing/cloud-data.csv")
    monkeypatch.setattr(app_module, "generate_demo_transactions", lambda: expected)

    loaded = app_module._load_data()

    assert loaded.source == "fallback"
    pd.testing.assert_frame_equal(loaded.frame, expected)


def test_load_snapshot_uses_bounded_demo_repository_when_unconfigured(
    monkeypatch: MonkeyPatch,
    sample_transactions: pd.DataFrame,
) -> None:
    expected = dashboard_fixture(sample_transactions)
    monkeypatch.setattr(app_module, "_mongo_resources", lambda *_: None)
    monkeypatch.setattr(app_module, "_load_demo_frame", lambda _language: expected)

    snapshot = app_module._load_snapshot(
        DashboardFilters(),
        PageRequest(number=2, size=50),
    )

    assert snapshot.source.value == "demo"
    assert snapshot.diagnostic == "configuration"
    assert snapshot.total_transactions == len(expected)
    assert len(snapshot.transactions) == 50
    assert snapshot.transactions.iloc[0]["Transaction ID"] == "TX189"


def test_load_snapshot_does_not_hide_unexpected_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    resources = app_module.MongoResources(object(), object())
    monkeypatch.setattr(app_module, "_mongo_resources", lambda *_: resources)
    monkeypatch.setattr(
        app_module,
        "ensure_indexes",
        MagicMock(side_effect=RuntimeError("programming defect")),
    )

    with pytest.raises(RuntimeError, match="programming defect"):
        app_module._load_snapshot(DashboardFilters(), PageRequest())


def test_database_retry_clears_both_streamlit_caches_and_reruns(
    monkeypatch: MonkeyPatch,
) -> None:
    data_cache = MagicMock()
    resource_cache = MagicMock()
    rerun = MagicMock()
    monkeypatch.setattr(app_module.st, "cache_data", data_cache)
    monkeypatch.setattr(app_module.st, "cache_resource", resource_cache)
    monkeypatch.setattr(app_module.st, "rerun", rerun)

    app_module._retry_database()

    data_cache.clear.assert_called_once_with()
    resource_cache.clear.assert_called_once_with()
    rerun.assert_called_once_with()


def test_streamlit_secrets_populate_known_environment_settings(
    monkeypatch: MonkeyPatch,
) -> None:
    for key in (
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "PAYMENT_DEMO_MODE",
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "ADMIN_PASSWORD_HASH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        app_module.st,
        "secrets",
        {
            "ANTHROPIC_BASE_URL": "https://provider.example",
            "ANTHROPIC_API_KEY": "secret",
            "ANTHROPIC_MODEL": "mimo-2.5-pro",
            "PAYMENT_DEMO_MODE": "1",
            "MONGODB_URI": "mongodb+srv://example.invalid",
            "MONGODB_DATABASE": "payment_demo",
            "ADMIN_PASSWORD_HASH": "pbkdf2_sha256$600000$salt$key",
            "UNRELATED_SECRET": "ignored",
        },
    )

    app_module._apply_streamlit_secrets()

    assert os.environ["ANTHROPIC_BASE_URL"] == "https://provider.example"
    assert os.environ["ANTHROPIC_API_KEY"] == "secret"
    assert os.environ["ANTHROPIC_MODEL"] == "mimo-2.5-pro"
    assert os.environ["PAYMENT_DEMO_MODE"] == "1"
    assert os.environ["MONGODB_URI"] == "mongodb+srv://example.invalid"
    assert os.environ["MONGODB_DATABASE"] == "payment_demo"
    assert os.environ["ADMIN_PASSWORD_HASH"].startswith("pbkdf2_sha256$")
    assert "UNRELATED_SECRET" not in os.environ
    for key in app_module.CLOUD_SETTING_KEYS:
        monkeypatch.delenv(key, raising=False)


@fixture
def dashboard_state(sample_transactions: pd.DataFrame) -> DashboardState:
    frame = dashboard_fixture(sample_transactions)
    alerts = evaluate_alerts(frame, frame)
    return DashboardState(frame, frame, alerts)


def test_snapshot_page_is_clamped_and_refetched_after_total_shrinks(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    base = PandasDashboardRepository(dashboard_state.display_frame).fetch(
        DashboardFilters(),
        PageRequest(),
    )
    stale_page = replace(
        base, transactions=base.transactions.iloc[0:0], total_transactions=1
    )
    valid_page = replace(
        base, transactions=base.transactions.iloc[:1], total_transactions=1
    )
    requested_pages: list[int] = []

    def fetch(_filters, page, _language):
        requested_pages.append(page.number)
        return stale_page if page.number == 2 else valid_page

    monkeypatch.setattr(app_module, "_load_snapshot", fetch)
    monkeypatch.setattr(app_module.st, "session_state", {"transaction_page": 2})

    snapshot, page_number, total_pages = app_module._load_valid_snapshot(
        DashboardFilters(),
        requested_page=2,
        language="en",
    )

    assert requested_pages == [2, 1]
    assert page_number == 1
    assert total_pages == 1
    assert app_module.st.session_state["transaction_page"] == 1
    pd.testing.assert_frame_equal(snapshot.transactions, valid_page.transactions)


def _patch_render_app_shell(
    monkeypatch: MonkeyPatch,
    state: DashboardState,
) -> tuple[list[dict[str, object]], MagicMock, DashboardSnapshot]:
    """Replace Streamlit and data-loading edges around the real composition."""
    containers: list[dict[str, object]] = []
    rerun = MagicMock()

    class Column:
        def __enter__(self) -> Column:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def button(self, *_args: object, **_kwargs: object) -> bool:
            return False

    monkeypatch.setattr(app_module.st, "session_state", {})
    monkeypatch.setattr(app_module.st, "set_page_config", lambda **_: None)
    monkeypatch.setattr(app_module.st, "title", lambda *_: None)
    monkeypatch.setattr(app_module.st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(app_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(app_module.st, "info", lambda *_: None)
    monkeypatch.setattr(app_module.st, "number_input", lambda *_, **__: 1)
    monkeypatch.setattr(
        app_module.st,
        "container",
        lambda *_, **kwargs: containers.append(kwargs) or nullcontext(),
    )
    monkeypatch.setattr(
        app_module.st,
        "columns",
        lambda count: [Column() for _ in range(count)],
    )
    monkeypatch.setattr(app_module.st, "rerun", rerun)
    monkeypatch.setattr(app_module, "_apply_streamlit_secrets", lambda: None)
    monkeypatch.setattr(app_module, "apply_page_style", lambda: None)
    monkeypatch.setattr(app_module, "_render_language_toggle", lambda: "my")
    snapshot = PandasDashboardRepository(state.display_frame).fetch(
        DashboardFilters(),
        PageRequest(),
    )
    monkeypatch.setattr(
        app_module,
        "_load_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        app_module,
        "_render_repository_filters",
        lambda *_args, **_kwargs: DashboardFilters(),
    )
    monkeypatch.setattr(app_module, "_render_source_status", lambda *_args: None)
    monkeypatch.setattr(app_module, "_render_source_badge", lambda *_args: None)
    monkeypatch.setattr(app_module, "_mongo_resources", lambda *_args: None)
    return containers, rerun, snapshot


def _track_renderers(
    monkeypatch: MonkeyPatch,
    calls: list[str],
    *renderers: tuple[str, str],
) -> None:
    """Record section composition without replacing application orchestration."""
    for name, call_name in renderers:
        monkeypatch.setattr(
            app_module,
            name,
            lambda *_args, _call_name=call_name, **_kwargs: calls.append(_call_name),
            raising=False,
        )


@pytest.mark.integration
def test_story_first_composition_and_admin_rerun(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    expected = [
        "hero",
        "kpis",
        "gateway_health",
        "gateway_performance",
        "success_trend",
        "failure_analysis",
        "ai",
        "recent",
        "guide",
    ]
    calls: list[str] = []
    admin_snapshots: list[list[str]] = []
    containers, rerun, snapshot = _patch_render_app_shell(monkeypatch, dashboard_state)

    def render_hero(
        state: DashboardSnapshot,
        database_source: str,
        language: str,
    ) -> None:
        assert state is snapshot
        assert database_source == "demo"
        assert language == "my"
        calls.append("hero")

    def render_ai(state: DashboardState, language: str) -> None:
        pd.testing.assert_frame_equal(state.display_frame, snapshot.transactions)
        assert language == "my"
        calls.append("ai")

    def render_admin(*_args: object, **_kwargs: object) -> bool:
        admin_snapshots.append(calls.copy())
        return True

    monkeypatch.setattr(app_module, "render_story_hero", render_hero, raising=False)
    monkeypatch.setattr(
        app_module,
        "render_kpis",
        lambda *_args, **_kwargs: calls.append("kpis"),
    )
    monkeypatch.setattr(app_module, "render_ai_operations_brief", render_ai)
    _track_renderers(
        monkeypatch,
        calls,
        ("render_gateway_health", "gateway_health"),
        ("render_gateway_performance", "gateway_performance"),
        ("render_success_trend", "success_trend"),
        ("render_failure_analysis", "failure_analysis"),
        ("render_recent_transactions", "recent"),
        ("render_interpretation_guide", "guide"),
    )
    monkeypatch.setattr(app_module, "render_admin_panel", render_admin)

    app_module.render_app()

    assert calls == expected
    assert admin_snapshots == [expected]
    assert containers == [{"border": True}]
    rerun.assert_called_once_with()


@pytest.mark.integration
def test_empty_state_skips_data_sections_but_keeps_admin_manager(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    empty_state = DashboardState(
        dashboard_state.replay_frame,
        dashboard_state.display_frame.iloc[0:0],
        dashboard_state.alerts,
    )
    calls: list[str] = []
    admin_snapshots: list[list[str]] = []
    containers, _, _ = _patch_render_app_shell(monkeypatch, empty_state)

    def render_admin(*_args: object, **_kwargs: object) -> bool:
        admin_snapshots.append(calls.copy())
        return False

    _track_renderers(
        monkeypatch,
        calls,
        ("render_story_hero", "hero"),
        ("render_kpis", "kpis"),
        ("render_ai_operations_brief", "ai"),
        ("render_gateway_health", "gateway_health"),
        ("render_empty_state", "empty_state"),
        ("render_gateway_performance", "gateway_performance"),
        ("render_success_trend", "success_trend"),
        ("render_failure_analysis", "failure_analysis"),
        ("render_recent_transactions", "recent"),
        ("render_interpretation_guide", "guide"),
    )
    monkeypatch.setattr(app_module, "render_admin_panel", render_admin)

    app_module.render_app()

    assert calls == ["hero", "kpis", "gateway_health", "empty_state"]
    assert admin_snapshots == [calls]
    assert containers == [{"border": True}]


@pytest.mark.integration
def test_database_fallback_status_uses_selected_language(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    warnings: list[str] = []
    render_source_status = app_module._render_source_status
    _, _, snapshot = _patch_render_app_shell(monkeypatch, dashboard_state)
    degraded = replace(snapshot, diagnostic="connection")
    monkeypatch.setattr(app_module, "_render_source_status", render_source_status)
    monkeypatch.setattr(app_module.st, "warning", warnings.append)
    monkeypatch.setattr(app_module.st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(app_module.st, "expander", lambda *_: nullcontext())
    monkeypatch.setattr(app_module.st, "write", lambda *_: None)
    monkeypatch.setattr(app_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(app_module.st, "button", lambda *_, **__: False)

    app_module._render_source_status(degraded, "my")

    assert warnings == [
        "MongoDB ကို အသုံးမပြုနိုင်ပါ။ သရုပ်ပြဖန်တီးထားသော ဒေတာကို အသုံးပြုနေပြီး ပြင်ဆင်မှုများကို ပိတ်ထားသည်။"
    ]


@pytest.mark.integration
def test_empty_state_renders_localized_semantic_wrapper(
    monkeypatch: MonkeyPatch,
) -> None:
    rendered: list[tuple[str, bool]] = []
    renderer = getattr(sections_module, "render_empty_state", None)

    assert renderer is not None
    monkeypatch.setattr(
        sections_module.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs["unsafe_allow_html"])),
    )

    renderer(language="my")

    body, allows_html = rendered[0]
    assert '<section class="empty-state">' in body
    assert '<img class="empty-mascot"' in body
    assert 'width="96" height="96"' in body
    assert 'alt=""' in body
    assert 'aria-hidden="true"' in body
    assert "ကိုက်ညီသော ငွေပေးချေမှု မရှိပါ" in body
    assert "စစ်ထုတ်မှုများ ပြန်လည်သတ်မှတ်ရန်" in body
    assert allows_html is True


@pytest.mark.integration
def test_reset_clears_only_display_filter_widget_state(
    monkeypatch: MonkeyPatch,
) -> None:
    reset = getattr(app_module, "_reset_display_filters", None)
    session = {
        "gateway_filter": ["Gateway A"],
        "transaction_type_filter": ["Transfer"],
        "device_filter": ["Mobile"],
        "status_filter": ["Success"],
        "date_filter": (date(2025, 6, 1), date(2025, 6, 2)),
        "replay_count": 120,
        "language_toggle": True,
        "ai_brief_text": "keep",
        "admin_auth": {"authenticated": True},
    }

    assert reset is not None
    monkeypatch.setattr(app_module.st, "session_state", session)

    reset()

    for key in (
        "gateway_filter",
        "transaction_type_filter",
        "device_filter",
        "status_filter",
        "date_filter",
    ):
        assert key not in session
    assert session == {
        "replay_count": 120,
        "language_toggle": True,
        "ai_brief_text": "keep",
        "admin_auth": {"authenticated": True},
    }


@pytest.mark.integration
def test_kpis_render_burmese_labels(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    columns = [MagicMock() for _ in range(5)]
    for column in columns:
        column.container.return_value = nullcontext()
    metric = MagicMock()
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.columns", lambda count: columns
    )
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.markdown", lambda *_, **__: None
    )
    monkeypatch.setattr("payment_dashboard.ui.sections.st.metric", metric)

    render_kpis(dashboard_state, language="my")

    assert metric.call_args_list[0].args[0] == "ငွေပေးချေမှုများ"


@pytest.mark.integration
def test_story_hero_renders_localized_semantic_wrapper(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    rendered: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        sections_module.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs["unsafe_allow_html"])),
    )

    render_story_hero(dashboard_state, database_source="mongodb", language="en")

    assert rendered == [
        (
            '<section class="playful-hero">\n'
            '  <p class="hero-eyebrow">Payment pulse</p>\n'
            "  <h1>120 payments made it through ✦</h1>\n"
            '  <p class="hero-subtitle">50.0% success rate · '
            "11.0 ms average latency</p>\n"
            '  <span class="status-pill">Live MongoDB data</span>\n'
            "</section>",
            True,
        )
    ]


@pytest.mark.integration
def test_story_hero_uses_live_label_for_live_snapshot(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    rendered: list[str] = []
    snapshot = PandasDashboardRepository(dashboard_state.display_frame).fetch(
        DashboardFilters(),
        PageRequest(),
    )
    live_snapshot = replace(snapshot, source=DataSource.LIVE)
    monkeypatch.setattr(
        sections_module.st,
        "markdown",
        lambda body, **_kwargs: rendered.append(body),
    )

    render_story_hero(live_snapshot, database_source="live", language="en")

    assert "Live MongoDB data" in rendered[0]


@pytest.mark.integration
def test_kpis_render_stable_containers_and_labels(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    container_keys: list[str] = []
    metrics: list[tuple[str, object]] = []

    class Column:
        def container(self, *, key: str):
            container_keys.append(key)
            return nullcontext()

        def metric(self, *_args: object) -> None:
            pass

    columns = [Column() for _ in range(5)]
    monkeypatch.setattr(sections_module.st, "columns", lambda count: columns)
    monkeypatch.setattr(sections_module.st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(
        sections_module.st,
        "metric",
        lambda label, value: metrics.append((label, value)),
    )

    render_kpis(dashboard_state, language="en")

    assert container_keys == [
        "kpi_transactions",
        "kpi_success",
        "kpi_failed",
        "kpi_latency",
        "kpi_alerts",
    ]
    assert [label for label, _ in metrics] == [
        "Transactions",
        "Success rate",
        "Failed",
        "Average latency",
        "Active alerts",
    ]


@pytest.mark.integration
def test_kpis_render_decorative_recognizable_icons(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    rendered: list[tuple[str, bool]] = []
    columns = [MagicMock() for _ in range(5)]
    for column in columns:
        column.container.return_value = nullcontext()
    monkeypatch.setattr(sections_module.st, "columns", lambda count: columns)
    monkeypatch.setattr(
        sections_module.st,
        "markdown",
        lambda body, **kwargs: rendered.append((body, kwargs["unsafe_allow_html"])),
    )

    render_kpis(dashboard_state, language="en")

    assert [body for body, _ in rendered] == [
        '<span class="kpi-icon" aria-hidden="true">⇄</span>',
        '<span class="kpi-icon" aria-hidden="true">✓</span>',
        '<span class="kpi-icon" aria-hidden="true">!</span>',
        '<span class="kpi-icon" aria-hidden="true">◷</span>',
        '<span class="kpi-icon" aria-hidden="true">⚑</span>',
    ]
    assert all(allows_html for _, allows_html in rendered)


@pytest.mark.integration
def test_gateway_health_keeps_gateway_values(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.dataframe",
        lambda frame, **_: captured.append(frame),
    )

    render_gateway_health(dashboard_state.alerts, language="my")

    assert set(captured[0]["ဂိတ်ဝေး"]) == set(dashboard_state.alerts["Bank Gateway"])


@pytest.mark.integration
def test_recent_transactions_localizes_headers_without_changing_values(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.dataframe",
        lambda frame, **_: captured.append(frame),
    )
    expected = dashboard_state.display_frame.sort_values(
        "Timestamp", ascending=False
    ).head(25)[
        [
            "Transaction ID",
            "Timestamp",
            "Bank Gateway",
            "Transaction Type",
            "Transaction Status",
            "Transaction Amount",
            "Device Used",
            "Latency (ms)",
            "Fraud Flag",
        ]
    ]

    render_recent_transactions(dashboard_state.display_frame, language="my")

    displayed = captured[0]
    assert list(displayed.columns) == [
        "ငွေပေးချေမှု ID",
        "အချိန်မှတ်တမ်း",
        "ဂိတ်ဝေး",
        "ငွေပေးချေမှု အမျိုးအစား",
        "ငွေပေးချေမှု အခြေအနေ",
        "ငွေပမာဏ",
        "အသုံးပြုသည့် စက်",
        "တုံ့ပြန်ချိန် (ms)",
        "လိမ်လည်မှု အမှတ်အသား",
    ]
    pd.testing.assert_frame_equal(
        displayed.set_axis(expected.columns, axis="columns"), expected
    )


@pytest.mark.integration
def test_ai_brief_waits_for_button_click(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    monkeypatch.setattr(sections_module.st, "session_state", {})
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(
        sections_module.st,
        "button",
        lambda *_, **__: False,
    )
    monkeypatch.setattr(
        sections_module,
        "generate_brief",
        MagicMock(side_effect=AssertionError("model called before click")),
    )

    render_ai_operations_brief(dashboard_state)

    sections_module.generate_brief.assert_not_called()


@pytest.mark.integration
def test_ai_brief_click_stores_text_and_evidence(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    session: dict[str, object] = {}
    markdown: list[str] = []
    evidence: list[object] = []
    container_keys: list[str | None] = []

    def capture_container(*_, **kwargs):
        container_keys.append(kwargs.get("key"))
        return nullcontext()

    monkeypatch.setattr(sections_module.st, "session_state", session)
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: True)
    monkeypatch.setattr(sections_module.st, "spinner", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "markdown", markdown.append)
    monkeypatch.setattr(sections_module.st, "container", capture_container)
    monkeypatch.setattr(sections_module.st, "expander", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "json", evidence.append)
    monkeypatch.setattr(
        sections_module,
        "generate_brief",
        lambda facts, *, language: "AI result",
    )

    render_ai_operations_brief(dashboard_state)

    assert session["ai_brief_text"] == "AI result"
    assert session["ai_brief_fingerprint"]
    assert markdown == ["AI result"]
    assert container_keys == ["ai_brief_card", "ai_brief_result"]
    assert evidence and evidence[0]["transaction_count"] == len(
        dashboard_state.display_frame
    )


@pytest.mark.integration
def test_ai_brief_passes_selected_language(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    generated = MagicMock(return_value="မြန်မာ AI အနှစ်ချုပ်")
    monkeypatch.setattr(sections_module.st, "session_state", {})
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: True)
    monkeypatch.setattr(sections_module.st, "spinner", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "container", lambda *_, **__: nullcontext())
    monkeypatch.setattr(sections_module.st, "expander", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "markdown", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "json", lambda *_: None)
    monkeypatch.setattr(sections_module, "generate_brief", generated)

    render_ai_operations_brief(dashboard_state, language="my")

    assert generated.call_args.kwargs["language"] == "my"


@pytest.mark.integration
def test_ai_brief_invalidates_stale_text(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    session: dict[str, object] = {
        "ai_brief_text": "stale",
        "ai_brief_fingerprint": "different facts",
    }
    rendered: list[str] = []
    monkeypatch.setattr(sections_module.st, "session_state", session)
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: False)
    monkeypatch.setattr(sections_module.st, "markdown", rendered.append)
    monkeypatch.setattr(sections_module.st, "container", lambda *_, **__: nullcontext())

    render_ai_operations_brief(dashboard_state)

    assert "ai_brief_text" not in session
    assert "ai_brief_fingerprint" not in session
    assert rendered == []


@pytest.mark.integration
def test_ai_brief_invalidates_text_from_another_language(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
) -> None:
    facts = build_brief_facts(dashboard_state.display_frame, dashboard_state.alerts)
    session: dict[str, object] = {
        "ai_brief_text": "English brief",
        "ai_brief_fingerprint": facts_fingerprint({"language": "en", "facts": facts}),
    }
    rendered: list[str] = []
    monkeypatch.setattr(sections_module.st, "session_state", session)
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: False)
    monkeypatch.setattr(sections_module.st, "markdown", rendered.append)
    monkeypatch.setattr(sections_module.st, "container", lambda *_, **__: nullcontext())
    monkeypatch.setattr(sections_module.st, "expander", lambda *_: nullcontext())

    render_ai_operations_brief(dashboard_state, language="my")

    assert "ai_brief_text" not in session
    assert "ai_brief_fingerprint" not in session
    assert rendered == []


@pytest.mark.integration
@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "The AI brief could not be generated. Please try again."),
        ("my", "AI အနှစ်ချုပ်ကို မဖန်တီးနိုင်ပါ။ ထပ်မံကြိုးစားပါ။"),
    ],
)
def test_ai_brief_localizes_generation_errors_without_provider_details(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
    language: str,
    expected: str,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(sections_module.st, "session_state", {})
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: True)
    monkeypatch.setattr(sections_module.st, "spinner", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "error", errors.append)
    monkeypatch.setattr(sections_module.st, "container", lambda *_, **__: nullcontext())
    monkeypatch.setattr(
        sections_module,
        "generate_brief",
        MagicMock(
            side_effect=AIBriefError(
                "bad response from https://provider.example using secret-token"
            )
        ),
    )

    render_ai_operations_brief(dashboard_state, language=language)

    assert errors == [expected]
