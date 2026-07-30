"""Streamlit entry point for the payment success dashboard."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import date
from pathlib import Path

# When Streamlit Cloud runs this file directly, payment_dashboard is not
# an installed package. Load sibling modules by file path to avoid
# relying on sys.path or package installation.
_PKG_DIR = Path(__file__).resolve().parent


def _load(name: str):  # noqa: ANN001
    """Import a sibling module from the payment_dashboard package."""
    spec = importlib.util.spec_from_file_location(
        f"payment_dashboard.{name}", _PKG_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


if __package__ in (None, ""):
    package = types.ModuleType("payment_dashboard")
    package.__path__ = [str(_PKG_DIR)]
    package.__package__ = "payment_dashboard"
    sys.modules.setdefault("payment_dashboard", package)

    # Register direct dependencies before the normal package imports below.
    for _name in ("config", "models", "i18n", "data_loader", "analytics", "alerting"):
        _load(_name)

# Now the normal imports work because the modules are in sys.modules.
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from payment_dashboard.alerting import evaluate_alerts  # noqa: E402
from payment_dashboard.analytics import add_latency_band, apply_filters  # noqa: E402
from payment_dashboard.config import DEFAULT_DATA_PATH  # noqa: E402
from payment_dashboard.data_loader import (  # noqa: E402
    DataValidationError,
    load_transactions,
)
from payment_dashboard.i18n import DEFAULT_LANGUAGE, Language, translate  # noqa: E402
from payment_dashboard.models import DashboardState  # noqa: E402
from payment_dashboard.ui.sections import (  # noqa: E402
    render_ai_operations_brief,
    render_failure_analysis,
    render_gateway_health,
    render_gateway_performance,
    render_interpretation_guide,
    render_kpis,
    render_recent_transactions,
    render_success_trend,
)
from payment_dashboard.ui.style import apply_page_style  # noqa: E402


def build_dashboard_state(
    full_frame: pd.DataFrame,
    replay_count: int,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> DashboardState:
    """Compute the replay slice, filtered display frame, and alerts."""
    replay_frame = full_frame.iloc[:replay_count].copy()
    display_frame = apply_filters(
        replay_frame,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )
    display_frame = add_latency_band(display_frame)
    return DashboardState(
        replay_frame=replay_frame,
        display_frame=display_frame,
        alerts=evaluate_alerts(full_frame, replay_frame),
    )


def _render_language_toggle() -> Language:
    """Render the top-of-page language switch and return its language code."""
    with st.container(border=True):
        use_burmese = st.toggle(
            translate("language.control_label"),
            value=False,
            key="language_toggle",
        )
        language: Language = "my" if use_burmese else DEFAULT_LANGUAGE
        language_name = translate(f"language.{'burmese' if use_burmese else 'english'}")
        st.caption(translate("language.current", language, name=language_name))
    return language


def _load_data(language: Language = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """Load transaction data or show Streamlit error and stop."""
    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    try:
        return load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(translate("errors.load_data", language, exc=exc))
        st.info(translate("errors.prepare_data_guidance", language))
        st.stop()


def _persist_sidebar_value(widget_key: str) -> None:
    """Copy a widget value to language-independent session state."""
    st.session_state[f"{widget_key}_value"] = st.session_state[widget_key]


def _sidebar_value(widget_key: str, default: object) -> object:
    """Return the persisted sidebar value or its initial default."""
    return st.session_state.get(f"{widget_key}_value", default)


def _render_sidebar(
    full_frame: pd.DataFrame,
    language: Language = DEFAULT_LANGUAGE,
) -> tuple[int, list[str], list[str], list[str], list[str], date, date]:
    """Render sidebar controls and return filter selections."""
    st.sidebar.header(translate("sidebar.controls", language))
    st.sidebar.caption(translate("sidebar.replay_description", language))
    replay_count = st.sidebar.slider(
        translate("sidebar.replayed_transactions", language),
        min_value=1,
        max_value=len(full_frame),
        value=_sidebar_value("replay_count", len(full_frame)),
        help=translate("sidebar.replay_help", language),
        key="replay_count",
        on_change=_persist_sidebar_value,
        args=("replay_count",),
    )
    st.sidebar.progress(replay_count / len(full_frame))
    st.sidebar.caption(
        translate(
            "sidebar.replay_count",
            language,
            replay_count=replay_count,
            total_count=len(full_frame),
        )
    )

    st.sidebar.subheader(translate("sidebar.display_filters", language))
    gateways = st.sidebar.multiselect(
        translate("sidebar.gateway", language),
        sorted(full_frame["Bank Gateway"].unique()),
        default=_sidebar_value("gateway_filter", []),
        placeholder=translate("sidebar.all_gateways", language),
        key="gateway_filter",
        on_change=_persist_sidebar_value,
        args=("gateway_filter",),
    )
    transaction_types = st.sidebar.multiselect(
        translate("sidebar.transaction_type", language),
        sorted(full_frame["Transaction Type"].unique()),
        default=_sidebar_value("transaction_type_filter", []),
        placeholder=translate("sidebar.all_transaction_types", language),
        key="transaction_type_filter",
        on_change=_persist_sidebar_value,
        args=("transaction_type_filter",),
    )
    devices = st.sidebar.multiselect(
        translate("sidebar.device", language),
        sorted(full_frame["Device Used"].unique()),
        default=_sidebar_value("device_filter", []),
        placeholder=translate("sidebar.all_devices", language),
        key="device_filter",
        on_change=_persist_sidebar_value,
        args=("device_filter",),
    )
    statuses = st.sidebar.multiselect(
        translate("sidebar.status", language),
        sorted(full_frame["Transaction Status"].unique()),
        default=_sidebar_value("status_filter", []),
        placeholder=translate("sidebar.all_statuses", language),
        key="status_filter",
        on_change=_persist_sidebar_value,
        args=("status_filter",),
    )

    minimum_date = full_frame["Timestamp"].min().date()
    maximum_date = full_frame["Timestamp"].max().date()
    selected_dates = st.sidebar.date_input(
        translate("sidebar.date_range", language),
        value=_sidebar_value("date_range_filter", (minimum_date, maximum_date)),
        min_value=minimum_date,
        max_value=maximum_date,
        key="date_range_filter",
        on_change=_persist_sidebar_value,
        args=("date_range_filter",),
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (minimum_date, maximum_date)
    )
    st.sidebar.info(translate("sidebar.filter_note", language))

    return replay_count, gateways, transaction_types, devices, statuses, start, end


def render_app() -> None:
    """Main Streamlit application."""
    configured_language: Language = (
        "my" if st.session_state.get("language_toggle", False) else DEFAULT_LANGUAGE
    )
    st.set_page_config(
        page_title=translate("dashboard.title", configured_language),
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_page_style()

    language = _render_language_toggle()
    st.title(translate("dashboard.title", language))
    st.markdown(translate("dashboard.description", language))
    st.caption(translate("dashboard.disclaimer", language))

    full_frame = _load_data(language)
    replay_count, gateways, transaction_types, devices, statuses, start, end = (
        _render_sidebar(full_frame, language=language)
    )

    state = build_dashboard_state(
        full_frame,
        replay_count,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )

    render_kpis(state, language=language)
    render_ai_operations_brief(state)
    render_gateway_health(state.alerts, language=language)

    if state.display_frame.empty:
        st.info(translate("errors.no_matching_transactions", language))
        return

    render_gateway_performance(state.display_frame, language=language)
    render_success_trend(state.display_frame, language=language)
    render_failure_analysis(state.display_frame, language=language)
    render_recent_transactions(state.display_frame, language=language)
    render_interpretation_guide(language=language)


if __name__ == "__main__":
    render_app()
