"""Streamlit page section renderers."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from payment_dashboard.ai_brief import (
    BriefResult,
    build_brief_facts,
    configured_brief_model,
    facts_fingerprint,
    generate_brief_result,
)
from payment_dashboard.analytics import summary_metrics
from payment_dashboard.config import CHART_COLORS
from payment_dashboard.dashboard_repository import DashboardFilters
from payment_dashboard.i18n import DEFAULT_LANGUAGE, Language, translate
from payment_dashboard.models import DashboardSnapshot, DashboardState, DataSource
from payment_dashboard.ui.charts import (
    FAILURE_DIMENSIONS,
    failure_breakdown_chart,
    gateway_success_chart,
    gateway_volume_chart,
    success_trend_chart,
)

RECENT_COLUMNS = [
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
RECENT_COLUMN_KEYS = {
    "Transaction ID": "table.transaction_id",
    "Timestamp": "table.timestamp",
    "Bank Gateway": "table.gateway",
    "Transaction Type": "table.transaction_type",
    "Transaction Status": "table.transaction_status",
    "Transaction Amount": "table.transaction_amount",
    "Device Used": "table.device_used",
    "Latency (ms)": "table.latency_ms",
    "Fraud Flag": "table.fraud_flag",
}

AI_BRIEF_RESULT_KEY = "ai_brief_result"
AI_BRIEF_FINGERPRINT_KEY = "ai_brief_fingerprint"
EMPTY_MASCOT_DATA_URI = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='34' r='24' fill='%23F59E72'/%3E"
    "%3Ccircle cx='16' cy='16' r='9' fill='%237C3AED'/%3E%3Ccircle cx='48' "
    "cy='16' r='9' fill='%237C3AED'/%3E%3Ccircle cx='24' cy='31' r='5' "
    "fill='%23FFF8F0'/%3E%3Ccircle cx='40' cy='31' r='5' fill='%23FFF8F0'/%3E"
    "%3Ccircle cx='24' cy='31' r='2' fill='%23251A3D'/%3E%3Ccircle cx='40' "
    "cy='31' r='2' fill='%23251A3D'/%3E%3Cpath d='M27 43q5 5 10 0' "
    "fill='none' stroke='%23251A3D' stroke-width='3' stroke-linecap='round'/%3E"
    "%3C/svg%3E"
)


def _dashboard_metrics(
    state: DashboardState | DashboardSnapshot,
) -> dict[str, int | float]:
    """Adapt legacy and repository dashboard state to one metric mapping."""
    if isinstance(state, DashboardSnapshot):
        return dict(state.metrics)
    return summary_metrics(state.display_frame)


def _snapshot_chart_labels(language: Language) -> dict[str, str]:
    """Return localized labels shared by every snapshot-backed chart."""
    return {
        "Bank Gateway": translate("dimensions.gateway", language),
        "Timestamp": translate("dimensions.timestamp", language),
        "Latency Band": translate("dimensions.latency_band", language),
        "success_rate": translate("kpi.success_rate", language),
        "transaction_count": translate("kpi.transactions", language),
        "failed_count": translate("kpi.failed", language),
    }


def build_story_hero_html(
    successful: int,
    metrics: dict[str, int | float],
    status_key: str,
    language: Language,
) -> str:
    """Build the localized, stable HTML structure for the dashboard story hero."""
    return "\n".join(
        (
            '<section class="playful-hero">',
            f'  <p class="hero-eyebrow">{translate("hero.eyebrow", language)}</p>',
            f"  <h1>{translate('hero.title', language, successful=successful)}</h1>",
            '  <p class="hero-subtitle">'
            f"{translate('hero.subtitle', language, **metrics)}</p>",
            f'  <span class="status-pill">{translate(status_key, language)}</span>',
            "</section>",
        )
    )


def render_story_hero(
    state: DashboardState | DashboardSnapshot,
    database_source: str,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render the localized success-first dashboard story."""
    metrics = _dashboard_metrics(state)
    successful = int(metrics["transaction_count"] - metrics["failed_count"])
    status_key = (
        "hero.database_live"
        if database_source in ("mongodb", DataSource.LIVE.value)
        else "hero.demo_mode"
    )
    st.markdown(
        build_story_hero_html(successful, metrics, status_key, language),
        unsafe_allow_html=True,
    )


def render_empty_state(language: Language = DEFAULT_LANGUAGE) -> None:
    """Render a localized, friendly empty-filter result."""
    st.markdown(
        "\n".join(
            (
                '<section class="empty-state">',
                f'  <img class="empty-mascot" src="{EMPTY_MASCOT_DATA_URI}" '
                'width="96" height="96" alt="" aria-hidden="true">',
                f"  <h2>{translate('empty.title', language)}</h2>",
                f"  <p>{translate('empty.body', language)}</p>",
                '  <span class="empty-action">↻ '
                f"{translate('actions.reset_filters', language)}</span>",
                "</section>",
            )
        ),
        unsafe_allow_html=True,
    )


def render_ai_operations_brief(
    state: DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
    *,
    filters: DashboardFilters | None = None,
) -> None:
    """Render analysis from aggregate facts in the selected language."""
    filters = filters or DashboardFilters()
    with st.container(key="ai_brief_card"):
        st.subheader(translate("ai.title", language))
        st.caption(translate("ai.description", language))
        facts = build_brief_facts(state)
        model = configured_brief_model()
        fingerprint = facts_fingerprint(
            {
                "language": language,
                "model": model,
                "filters": {
                    "gateways": _normalized_filter_values(filters.gateways),
                    "transaction_types": _normalized_filter_values(
                        filters.transaction_types
                    ),
                    "devices": _normalized_filter_values(filters.devices),
                    "statuses": _normalized_filter_values(filters.statuses),
                    "start": filters.start.isoformat() if filters.start else None,
                    "end": filters.end.isoformat() if filters.end else None,
                },
                "data_source": state.source.value,
                "simulation_version": state.simulation_version,
                "facts": facts,
            }
        )

        if st.session_state.get(AI_BRIEF_FINGERPRINT_KEY) != fingerprint:
            st.session_state.pop(AI_BRIEF_RESULT_KEY, None)
            st.session_state.pop(AI_BRIEF_FINGERPRINT_KEY, None)

        generate = st.button(
            translate("ai.generate", language),
            disabled=state.total_transactions == 0,
            type="primary",
        )
        if state.total_transactions == 0:
            st.info(translate("ai.requires_data", language))

        if generate:
            with st.spinner(translate("ai.generating", language)):
                brief = generate_brief_result(
                    facts,
                    language=language,
                    model=model,
                )
            st.session_state[AI_BRIEF_RESULT_KEY] = brief
            st.session_state[AI_BRIEF_FINGERPRINT_KEY] = fingerprint

        brief = st.session_state.get(AI_BRIEF_RESULT_KEY)
        if isinstance(brief, BriefResult):
            with st.container(key="ai_brief_result"):
                st.caption(translate(f"ai.origin.{brief.origin}", language))
                st.markdown(f"**{translate('ai.summary', language)}**")
                st.markdown(brief.content.summary)
                st.markdown(f"**{translate('ai.risks', language)}**")
                for risk in brief.content.risks:
                    st.markdown(f"- {risk}")
                st.markdown(f"**{translate('ai.actions', language)}**")
                for action in brief.content.actions:
                    st.markdown(f"- {action}")
            with st.expander(translate("ai.evidence", language)):
                for evidence in brief.content.evidence:
                    st.markdown(f"- {evidence}")


def _normalized_filter_values(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return set-valued filters in one deterministic cache-key order."""
    return tuple(sorted(set(values)))


def render_kpis(
    state: DashboardState | DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render the top-level KPI metric cards."""
    metrics = _dashboard_metrics(state)
    active_alerts = int(state.alerts["is_alert"].sum())

    kpis = (
        (
            "kpi_transactions",
            "⇄",
            translate("kpi.transactions", language),
            f"{metrics['transaction_count']:,}",
        ),
        (
            "kpi_success",
            "✓",
            translate("kpi.success_rate", language),
            f"{metrics['success_rate']:.1%}",
        ),
        (
            "kpi_failed",
            "!",
            translate("kpi.failed", language),
            f"{metrics['failed_count']:,}",
        ),
        (
            "kpi_latency",
            "◷",
            translate("kpi.average_latency", language),
            f"{metrics['average_latency_ms']:.1f} ms",
        ),
        (
            "kpi_alerts",
            "⚑",
            translate("kpi.active_alerts", language),
            active_alerts,
        ),
    )
    for column, (key, icon, label, value) in zip(st.columns(5), kpis, strict=True):
        with column.container(key=key):
            st.markdown(
                f'<span class="kpi-icon" aria-hidden="true">{icon}</span>',
                unsafe_allow_html=True,
            )
            st.metric(label, value)


def render_gateway_health(
    alerts: pd.DataFrame,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render the gateway health table with alert status."""
    st.subheader(translate("health.title", language))
    st.caption(translate("health.description", language))

    active = alerts.loc[alerts["is_alert"]]
    if active.empty:
        st.success(translate("health.no_alert", language))
    else:
        names = ", ".join(active["Bank Gateway"].astype(str))
        st.error(translate("health.action_required", language, names=names))

    display = alerts.copy()
    status_column = translate("sidebar.status", language)
    display[status_column] = display.apply(
        lambda row: (
            translate("health.insufficient_history", language)
            if not row["has_sufficient_history"]
            else (
                translate("health.alert", language)
                if row["is_alert"]
                else translate("health.healthy", language)
            )
        ),
        axis=1,
    )
    for column in ("baseline_rate", "rolling_rate", "drop"):
        display[column] = display[column].map(
            lambda v: "—" if pd.isna(v) else f"{v:.1%}"
        )
    display = display.rename(
        columns={
            "Bank Gateway": translate("table.gateway", language),
            "baseline_rate": translate("health.baseline", language),
            "rolling_rate": translate("health.latest_50", language),
            "drop": translate("health.drop", language),
        }
    )
    gateway_column = translate("table.gateway", language)
    baseline_column = translate("health.baseline", language)
    latest_50_column = translate("health.latest_50", language)
    drop_column = translate("health.drop", language)
    st.dataframe(
        display[
            [
                gateway_column,
                baseline_column,
                latest_50_column,
                drop_column,
                status_column,
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_gateway_performance(
    frame: pd.DataFrame | DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render gateway success rate and volume charts side by side."""
    st.subheader(translate("charts.gateway_performance", language))
    left, right = st.columns(2)
    if isinstance(frame, DashboardSnapshot):
        summary = frame.gateway_summary
        labels = _snapshot_chart_labels(language)
        success_chart = px.bar(
            summary,
            x="Bank Gateway",
            y="success_rate",
            color="Bank Gateway",
            color_discrete_sequence=CHART_COLORS,
            title=translate("charts.success_rate_by_gateway", language),
            range_y=[0, 1],
            text_auto=".1%",
            labels=labels,
        )
        success_chart.update_layout(showlegend=False, yaxis_tickformat=".0%")
        volume_chart = px.bar(
            summary,
            x="Bank Gateway",
            y="transaction_count",
            color="Bank Gateway",
            color_discrete_sequence=CHART_COLORS,
            title=translate("charts.transaction_volume_by_gateway", language),
            text_auto=True,
            labels=labels,
        )
        volume_chart.update_layout(showlegend=False)
    else:
        success_chart = gateway_success_chart(frame, language=language)
        volume_chart = gateway_volume_chart(frame, language=language)
    left.plotly_chart(success_chart, use_container_width=True)
    right.plotly_chart(volume_chart, use_container_width=True)


def render_success_trend(
    frame: pd.DataFrame | DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render the success rate trend line chart."""
    st.subheader(translate("charts.success_trend", language))
    if isinstance(frame, DashboardSnapshot):
        labels = _snapshot_chart_labels(language)
        chart = px.line(
            frame.trend,
            x="Timestamp",
            y="success_rate",
            markers=True,
            color_discrete_sequence=["#2563EB"],
            title=translate("charts.success_trend", language),
            labels=labels,
        )
        chart.update_layout(yaxis_tickformat=".0%", yaxis_range=[0, 1])
    else:
        chart = success_trend_chart(frame, language=language)
    st.plotly_chart(chart, use_container_width=True)


def render_failure_analysis(
    frame: pd.DataFrame | DashboardSnapshot,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render failure breakdown charts by four dimensions."""
    st.subheader(translate("sections.failure_analysis", language))
    st.caption(translate("sections.failure_analysis_description", language))
    if isinstance(frame, DashboardSnapshot):
        labels = _snapshot_chart_labels(language)
        chart = px.bar(
            frame.failure_summary,
            x="Latency Band",
            y="failed_count",
            title=translate(
                "charts.failures_by",
                language,
                title=translate("dimensions.latency_band", language).lower(),
            ),
            color_discrete_sequence=["#F97316"],
            text_auto=True,
            labels=labels,
        )
        chart.update_layout(showlegend=False)
        st.plotly_chart(chart, width="stretch")
        return
    columns = st.columns(2)
    for index, (dimension, title) in enumerate(FAILURE_DIMENSIONS):
        chart = failure_breakdown_chart(frame, dimension, title, language=language)
        columns[index % 2].plotly_chart(chart, use_container_width=True)


def render_recent_transactions(
    frame: pd.DataFrame,
    language: Language = DEFAULT_LANGUAGE,
    limit: int | None = 25,
) -> None:
    """Render the recent transactions table."""
    st.subheader(translate("table.recent_transactions", language))
    display = frame.sort_values("Timestamp", ascending=False)
    if limit is not None:
        display = display.head(limit)
    display = display[RECENT_COLUMNS]
    display = display.rename(
        columns={
            column: translate(key, language)
            for column, key in RECENT_COLUMN_KEYS.items()
        }
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )


def render_interpretation_guide(
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Render the expandable interpretation guide."""
    with st.expander(translate("guide.title", language)):
        st.markdown(translate("guide.content", language))
