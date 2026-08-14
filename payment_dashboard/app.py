"""Streamlit entry point for the payment success dashboard."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import os
import sys
import types
from dataclasses import replace
from datetime import date
from html import escape
from pathlib import Path
from types import ModuleType
from typing import cast

# When Streamlit Cloud runs this file directly, payment_dashboard is not
# an installed package. Load sibling modules by file path to avoid
# relying on sys.path or package installation.
_PKG_DIR = Path(__file__).resolve().parent
CLOUD_SETTING_KEYS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "PAYMENT_DEMO_MODE",
    "MONGODB_URI",
    "MONGODB_DATABASE",
    "ADMIN_PASSWORD_HASH",
)
FILTER_WIDGET_KEYS = (
    "gateway_filter",
    "transaction_type_filter",
    "device_filter",
    "status_filter",
    "date_filter",
)
TRANSACTION_PAGE_SIZE = 50


def _load(name: str) -> ModuleType:
    """Import a sibling module from the payment_dashboard package."""
    spec = importlib.util.spec_from_file_location(
        f"payment_dashboard.{name}", _PKG_DIR / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load payment_dashboard.{name}")
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
    for _name in (
        "config",
        "models",
        "i18n",
        "data_loader",
        "mongodb",
        "admin_auth",
        "transaction_service",
        "analytics",
        "alerting",
        "routing_config",
        "routing_models",
        "routing_simulation",
        "routing_policies",
        "routing_optimizer",
        "routing_evaluation",
        "routing_repository",
    ):
        _load(_name)

# Now the normal imports work because the modules are in sys.modules.
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from payment_dashboard.alerting import evaluate_alerts  # noqa: E402
from payment_dashboard.analytics import add_latency_band, apply_filters  # noqa: E402
from payment_dashboard.config import DEFAULT_DATA_PATH, GATEWAYS  # noqa: E402
from payment_dashboard.dashboard_repository import (  # noqa: E402
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)
from payment_dashboard.data_loader import (  # noqa: E402
    DataValidationError,
    load_transactions,
)
from payment_dashboard.demo_data import generate_demo_transactions  # noqa: E402
from payment_dashboard.i18n import DEFAULT_LANGUAGE, Language, translate  # noqa: E402
from payment_dashboard.models import (  # noqa: E402
    DashboardSnapshot,
    DashboardState,
    DataSource,
)
from payment_dashboard.mongodb import (  # noqa: E402
    DatabaseResult,
    MongoDashboardRepository,
    MongoResources,
    classify_mongodb_error,
    create_resources_from_env,
    load_dashboard_transactions,
)
from payment_dashboard.routing_models import (  # noqa: E402
    OptimizationReport,
)
from payment_dashboard.routing_repository import PandasRoutingRepository  # noqa: E402
from payment_dashboard.transaction_service import (  # noqa: E402
    DEVICES,
    TRANSACTION_TYPES,
)
from payment_dashboard.ui.admin import render_admin_panel  # noqa: E402
from payment_dashboard.ui.shell import (  # noqa: E402
    FILTERED_VIEWS,
    DashboardView,
    render_filter_bar,
    render_top_navigation,
)
from payment_dashboard.ui.style import apply_page_style  # noqa: E402
from payment_dashboard.ui.views import (  # noqa: E402
    render_gateways,
    render_overview,
    render_routing_lab,
    render_transactions,
)


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


def _load_data(language: Language = DEFAULT_LANGUAGE) -> DatabaseResult:
    """Load MongoDB transactions with a validated local/demo fallback."""
    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))

    def fallback() -> pd.DataFrame:
        if os.getenv("PAYMENT_DEMO_MODE") == "1" and not data_path.is_file():
            return generate_demo_transactions()
        try:
            return load_transactions(data_path, require_gateway=True)
        except DataValidationError as exc:
            st.error(translate("errors.load_data", language, exc=exc))
            st.info(translate("errors.prepare_data_guidance", language))
            st.stop()

    if os.getenv("PAYMENT_DEMO_MODE") == "1":
        return DatabaseResult(
            fallback(), "fallback", "database.fallback_not_configured"
        )
    return load_dashboard_transactions(fallback)


def _load_demo_frame(language: Language = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """Load validated local data, generating the configured offline demo if needed."""
    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    if os.getenv("PAYMENT_DEMO_MODE") == "1" and not data_path.is_file():
        return generate_demo_transactions()
    try:
        return load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(translate("errors.load_data", language, exc=exc))
        st.info(translate("errors.prepare_data_guidance", language))
        st.stop()


def _load_optimization_contexts(
    snapshot: DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> tuple[pd.DataFrame, str]:
    """Load routing contexts from the same backend as the dashboard snapshot."""
    if snapshot.source is DataSource.LIVE:
        resources = _mongo_resources(_mongo_configuration_fingerprint())
        if resources is None:
            raise RuntimeError("Live snapshot has no configured MongoDB resources")
        frame = MongoDashboardRepository(resources.database).fetch_routing_contexts()
        return frame, "full active MongoDB transaction history"
    return _load_demo_frame(language), "validated local/demo transaction history"


@st.cache_resource(show_spinner=False)
def _build_optimization_report(
    frame: pd.DataFrame,
    source_label: str,
) -> OptimizationReport:
    """Build a deterministic synthetic benchmark from disclosed source contexts."""
    return PandasRoutingRepository().build_report(
        frame,
        source_label=source_label,
    )


@st.cache_resource(show_spinner=False)
def _mongo_resources(
    configuration_fingerprint: str,
) -> MongoResources | None:
    """Return MongoDB resources cached without retaining the raw connection URI."""
    del configuration_fingerprint
    return create_resources_from_env()


def _mongo_configuration_fingerprint() -> str:
    """Build a non-secret cache key that changes with MongoDB configuration."""
    uri = os.getenv("MONGODB_URI", "")
    database_name = os.getenv("MONGODB_DATABASE", "")
    digest = hashlib.sha256(uri.encode()).hexdigest() if uri else "unconfigured"
    return f"{digest}:{database_name}"


def _load_snapshot(
    filters: DashboardFilters,
    page: PageRequest,
    language: Language = DEFAULT_LANGUAGE,
) -> DashboardSnapshot:
    """Fetch one live dashboard snapshot or a clearly categorized demo fallback."""

    def demo_snapshot(diagnostic: str) -> DashboardSnapshot:
        snapshot = PandasDashboardRepository(_load_demo_frame(language)).fetch(
            filters,
            page,
        )
        return replace(snapshot, diagnostic=diagnostic)

    try:
        resources = _mongo_resources(_mongo_configuration_fingerprint())
        if resources is None:
            return demo_snapshot("configuration")
        return MongoDashboardRepository(resources.database).fetch(filters, page)
    except Exception as exc:
        diagnostic = classify_mongodb_error(exc)
        if diagnostic == "unexpected":
            raise
        return demo_snapshot(diagnostic)


def _load_valid_snapshot(
    filters: DashboardFilters,
    requested_page: int,
    language: Language = DEFAULT_LANGUAGE,
) -> tuple[DashboardSnapshot, int, int]:
    """Fetch a bounded page, correcting stale page state with one refetch."""
    page_number = max(1, requested_page)
    if page_number != requested_page:
        st.session_state["transaction_page"] = page_number
    snapshot = _load_snapshot(
        filters,
        PageRequest(number=page_number, size=TRANSACTION_PAGE_SIZE),
        language,
    )
    total_pages = max(
        1,
        (snapshot.total_transactions + TRANSACTION_PAGE_SIZE - 1)
        // TRANSACTION_PAGE_SIZE,
    )
    if page_number > total_pages:
        page_number = total_pages
        st.session_state["transaction_page"] = page_number
        snapshot = _load_snapshot(
            filters,
            PageRequest(number=page_number, size=TRANSACTION_PAGE_SIZE),
            language,
        )
    return snapshot, page_number, total_pages


def _retry_database() -> None:
    """Discard cached connection/query state before rerunning the dashboard."""
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()


def _render_source_badge(snapshot: DashboardSnapshot, language: Language) -> None:
    """Render a compact localized badge without exposing connection details."""
    label_key = (
        "source.live_label"
        if snapshot.source is DataSource.LIVE
        else "source.demo_label"
    )
    disclosure = translate(
        "source.simulation_disclosure",
        language,
        version=snapshot.simulation_version,
    )
    st.markdown(
        '<div class="source-status">'
        f'<span class="status-pill">{snapshot.source.value.upper()}</span> '
        f"{translate(label_key, language)} · "
        f"{escape(disclosure)}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_source_status(
    snapshot: DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render explicit live/degraded state with safe recovery guidance."""
    _render_source_badge(snapshot, language)
    if snapshot.source is DataSource.LIVE:
        return
    st.warning(translate("source.degraded_warning", language))
    with st.expander(translate("source.diagnostics", language)):
        category = snapshot.diagnostic or "unavailable"
        st.write(translate("source.diagnostic_category", language, category=category))
        st.caption(translate("source.retry_guidance", language))
    st.button(
        translate("source.retry", language),
        key="database_retry",
        on_click=_retry_database,
    )


def _apply_streamlit_secrets() -> None:
    """Expose approved root-level Streamlit secrets to existing clients."""
    try:
        from dotenv import dotenv_values

        dotenv = dotenv_values(Path.cwd() / ".env")
    except Exception:
        dotenv = {}
    for key in CLOUD_SETTING_KEYS:
        if os.getenv(key):
            continue
        value = None
        with contextlib.suppress(FileNotFoundError):
            value = st.secrets.get(key)
        if not value:
            value = dotenv.get(key)
        if isinstance(value, str) and value:
            os.environ[key] = value


def _persist_sidebar_value(widget_key: str) -> None:
    """Copy a widget value to language-independent session state."""
    st.session_state[f"{widget_key}_value"] = st.session_state[widget_key]


def _sidebar_value(widget_key: str, default: object) -> object:
    """Return the persisted sidebar value or its initial default."""
    return st.session_state.get(f"{widget_key}_value", default)


def _reset_display_filters() -> None:
    """Clear display filters without changing replay or application state."""
    for key in FILTER_WIDGET_KEYS:
        st.session_state.pop(key, None)


def _reset_transaction_page() -> None:
    """Return to the first bounded page after a repository filter changes."""
    st.session_state["transaction_page"] = 1


def _reset_repository_filters() -> None:
    """Clear repository filters and return pagination to its first page."""
    _reset_display_filters()
    _reset_transaction_page()


def _change_transaction_page(delta: int, total_pages: int) -> None:
    """Move pagination within the known valid page range."""
    current = int(st.session_state.get("transaction_page", 1))
    st.session_state["transaction_page"] = min(
        total_pages,
        max(1, current + delta),
    )


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
        value=cast(int, _sidebar_value("replay_count", len(full_frame))),
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
        default=[],
        placeholder=translate("sidebar.all_gateways", language),
        key="gateway_filter",
    )
    transaction_types = st.sidebar.multiselect(
        translate("sidebar.transaction_type", language),
        sorted(full_frame["Transaction Type"].unique()),
        default=[],
        placeholder=translate("sidebar.all_transaction_types", language),
        key="transaction_type_filter",
    )
    devices = st.sidebar.multiselect(
        translate("sidebar.device", language),
        sorted(full_frame["Device Used"].unique()),
        default=[],
        placeholder=translate("sidebar.all_devices", language),
        key="device_filter",
    )
    statuses = st.sidebar.multiselect(
        translate("sidebar.status", language),
        sorted(full_frame["Transaction Status"].unique()),
        default=[],
        placeholder=translate("sidebar.all_statuses", language),
        key="status_filter",
    )

    minimum_date = full_frame["Timestamp"].min().date()
    maximum_date = full_frame["Timestamp"].max().date()
    selected_dates = st.sidebar.date_input(
        translate("sidebar.date_range", language),
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
        key="date_filter",
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (minimum_date, maximum_date)
    )
    st.sidebar.button(
        translate("actions.reset_filters", language),
        type="secondary",
        on_click=_reset_display_filters,
    )
    st.sidebar.info(translate("sidebar.filter_note", language))

    return replay_count, gateways, transaction_types, devices, statuses, start, end


def _render_repository_filters(
    language: Language = DEFAULT_LANGUAGE,
) -> DashboardFilters:
    """Render repository-backed filters without loading the transaction collection."""
    st.sidebar.header(translate("sidebar.controls", language))
    gateways = st.sidebar.multiselect(
        translate("sidebar.gateway", language),
        sorted(GATEWAYS),
        placeholder=translate("sidebar.all_gateways", language),
        key="gateway_filter",
        on_change=_reset_transaction_page,
    )
    transaction_types = st.sidebar.multiselect(
        translate("sidebar.transaction_type", language),
        sorted(TRANSACTION_TYPES),
        placeholder=translate("sidebar.all_transaction_types", language),
        key="transaction_type_filter",
        on_change=_reset_transaction_page,
    )
    devices = st.sidebar.multiselect(
        translate("sidebar.device", language),
        sorted(DEVICES),
        placeholder=translate("sidebar.all_devices", language),
        key="device_filter",
        on_change=_reset_transaction_page,
    )
    statuses = st.sidebar.multiselect(
        translate("sidebar.status", language),
        ["Success", "Failed"],
        placeholder=translate("sidebar.all_statuses", language),
        key="status_filter",
        on_change=_reset_transaction_page,
    )
    selected_dates = st.sidebar.date_input(
        translate("sidebar.date_range", language),
        value=[],
        key="date_filter",
        on_change=_reset_transaction_page,
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (None, None)
    )
    st.sidebar.button(
        translate("actions.reset_filters", language),
        type="secondary",
        on_click=_reset_repository_filters,
    )
    return DashboardFilters(
        gateways=tuple(gateways),
        transaction_types=tuple(transaction_types),
        devices=tuple(devices),
        statuses=tuple(statuses),
        start=start,
        end=end,
    )


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
    _apply_streamlit_secrets()
    apply_page_style()

    language = _render_language_toggle()
    view = render_top_navigation(language)
    filters = (
        render_filter_bar(
            language,
            _reset_transaction_page,
            _reset_repository_filters,
        )
        if view in FILTERED_VIEWS
        else DashboardFilters()
    )
    requested_page = int(st.session_state.get("transaction_page", 1))
    snapshot, page_number, total_pages = _load_valid_snapshot(
        filters,
        requested_page,
        language,
    )
    _render_source_status(snapshot, language)

    if view is DashboardView.OVERVIEW:
        render_overview(snapshot, language)
    elif view is DashboardView.GATEWAYS:
        render_gateways(snapshot, language)
    elif view is DashboardView.ROUTING:
        try:
            optimization_frame, optimization_source = _load_optimization_contexts(
                snapshot,
                language,
            )
            optimization_report = _build_optimization_report(
                optimization_frame,
                optimization_source,
            )
        except ValueError as exc:
            st.error(f"Synthetic routing benchmark unavailable: {exc}")
        except Exception as exc:
            diagnostic = classify_mongodb_error(exc)
            if diagnostic == "unexpected":
                raise
            st.warning(
                "Synthetic routing benchmark unavailable because the full active "
                f"MongoDB history could not be read ({diagnostic})."
            )
        else:
            render_routing_lab(optimization_report, language)
    elif view is DashboardView.TRANSACTIONS:
        st.number_input(
            translate("pagination.page", language),
            min_value=1,
            step=1,
            key="transaction_page",
            disabled=True,
        )
        render_transactions(snapshot, language)
        previous_column, next_column = st.columns(2)
        previous_column.button(
            translate("pagination.previous", language),
            key="transaction_previous",
            disabled=page_number <= 1,
            on_click=_change_transaction_page,
            args=(-1, total_pages),
        )
        next_column.button(
            translate("pagination.next", language),
            key="transaction_next",
            disabled=page_number >= total_pages,
            on_click=_change_transaction_page,
            args=(1, total_pages),
        )
        st.caption(
            translate(
                "pagination.summary",
                language,
                page=page_number,
                pages=total_pages,
                total=snapshot.total_transactions,
            )
        )
    else:
        resources = (
            _mongo_resources(_mongo_configuration_fingerprint())
            if snapshot.source is DataSource.LIVE
            else None
        )
        admin_database = resources.database if resources is not None else None
        with st.container(border=True):
            if render_admin_panel(
                admin_database,
                snapshot.source,
                snapshot.transactions,
                language,
                os.getenv("ADMIN_PASSWORD_HASH"),
            ):
                st.rerun()


if __name__ == "__main__":
    render_app()
