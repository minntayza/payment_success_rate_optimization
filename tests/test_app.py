from __future__ import annotations

import os
import subprocess
import sys
from contextlib import nullcontext
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
from payment_dashboard.models import DashboardState
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


@pytest.mark.integration
def test_kpis_render_burmese_labels(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    columns = [MagicMock() for _ in range(5)]
    monkeypatch.setattr(
        "payment_dashboard.ui.sections.st.columns", lambda count: columns
    )

    render_kpis(dashboard_state, language="my")

    assert columns[0].metric.call_args.args[0] == "ငွေပေးချေမှုများ"


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
def test_kpis_render_stable_containers_and_labels(
    monkeypatch: MonkeyPatch, dashboard_state: DashboardState
) -> None:
    container_keys: list[str] = []

    class Column:
        def __init__(self) -> None:
            self.metric = MagicMock()

        def container(self, *, key: str):
            container_keys.append(key)
            return nullcontext()

    columns = [Column() for _ in range(5)]
    monkeypatch.setattr(sections_module.st, "columns", lambda count: columns)

    render_kpis(dashboard_state, language="en")

    assert container_keys == [
        "kpi_transactions",
        "kpi_success",
        "kpi_failed",
        "kpi_latency",
        "kpi_alerts",
    ]
    assert [column.metric.call_args.args[0] for column in columns] == [
        "Transactions",
        "Success rate",
        "Failed",
        "Average latency",
        "Active alerts",
    ]


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
    assert container_keys == ["ai_brief_result"]
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
        "ai_brief_fingerprint": facts_fingerprint(facts),
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
    ("error", "expected"),
    [
        (AIBriefError("missing ANTHROPIC_API_KEY"), "missing ANTHROPIC_API_KEY"),
        (AIBriefError("bad provider response"), "bad provider response"),
    ],
)
def test_ai_brief_shows_generation_errors(
    monkeypatch: MonkeyPatch,
    dashboard_state: DashboardState,
    error: AIBriefError,
    expected: str,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(sections_module.st, "session_state", {})
    monkeypatch.setattr(sections_module.st, "subheader", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(sections_module.st, "button", lambda *_, **__: True)
    monkeypatch.setattr(sections_module.st, "spinner", lambda *_: nullcontext())
    monkeypatch.setattr(sections_module.st, "error", errors.append)
    monkeypatch.setattr(
        sections_module,
        "generate_brief",
        MagicMock(side_effect=error),
    )

    render_ai_operations_brief(dashboard_state)

    assert errors == [expected]
