# Dark Payment Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long light Streamlit page with an accessible dark fintech command center organized into five focused top-navigation views.

**Architecture:** Keep repositories and calculations in their current modules. Add a typed presentation shell and view-composition module, centralize Plotly styling, and let `render_app` orchestrate validated loading before delegating only the active view.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, pandas, pytest, Ruff, strict mypy.

## Global Constraints

- Preserve repository, metric, routing, lineage, audit, and authentication behavior.
- Views are exactly Overview, Gateways, Routing Lab, Transactions, and Admin.
- The compact filter bar appears on Overview, Gateways, and Transactions only.
- Routing Lab and Admin never inherit analytical display filters.
- Base colors are canvas `#07111F`, surface `#0D1B2A`, raised surface `#122235`, border `#24364B`, primary text `#F8FAFC`, secondary text `#94A3B8`, accent `#22D3EE`, healthy `#34D399`, warning `#FBBF24`, and critical `#FB7185`.
- Preserve English/Myanmar rendering, visible keyboard focus, responsive behavior, and reduced-motion support.
- Do not replace Streamlit, add external services, change calculations, or add real-time push updates.

---

## File Structure

- Create `payment_dashboard/ui/shell.py`: typed view identifiers, navigation, compact filter bar, page headings, and source badge.
- Create `payment_dashboard/ui/views.py`: view-level composition only; receives validated snapshots/reports and invokes existing section renderers.
- Create `payment_dashboard/ui/chart_theme.py`: one presentation-only Plotly theme function.
- Modify `payment_dashboard/ui/style.py`: dark design tokens and responsive component styling.
- Modify `payment_dashboard/ui/charts.py`, `payment_dashboard/ui/sections.py`, and `payment_dashboard/ui/optimization.py`: apply the shared chart theme and semantic container keys.
- Modify `payment_dashboard/app.py`: active-view orchestration, filter isolation, lazy Routing Lab report construction, and Admin isolation.
- Modify `payment_dashboard/i18n.py`: shell, view, and filter-bar labels in English and Myanmar.
- Add `tests/test_shell.py`, `tests/test_views.py`, and `tests/test_chart_theme.py`; update `tests/test_app.py`, `tests/test_style.py`, `tests/test_charts.py`, and browser smoke expectations.

### Task 1: Typed Navigation Shell and Compact Filter Bar

**Files:**
- Create: `payment_dashboard/ui/shell.py`
- Modify: `payment_dashboard/i18n.py`
- Test: `tests/test_shell.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces: `DashboardView(StrEnum)`, `FILTERED_VIEWS: frozenset[DashboardView]`, `active_view() -> DashboardView`, `render_top_navigation(language: Language) -> DashboardView`, and `render_filter_bar(language: Language, on_change: Callable[[], None], on_reset: Callable[[], None]) -> DashboardFilters`.
- Consumes: `DashboardFilters`, `Language`, `translate`, `GATEWAYS`, `TRANSACTION_TYPES`, and `DEVICES`.

- [ ] **Step 1: Write failing shell tests**

```python
def test_filtered_views_are_explicit() -> None:
    assert FILTERED_VIEWS == {
        DashboardView.OVERVIEW,
        DashboardView.GATEWAYS,
        DashboardView.TRANSACTIONS,
    }


def test_active_view_defaults_to_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell.st, "session_state", {})
    assert active_view() is DashboardView.OVERVIEW


def test_filter_bar_returns_repository_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell.st, "multiselect", lambda *args, **kwargs: [])
    monkeypatch.setattr(shell.st, "date_input", lambda *args, **kwargs: [])
    monkeypatch.setattr(shell.st, "button", Mock())
    assert render_filter_bar("en", Mock(), Mock()) == DashboardFilters()
```

- [ ] **Step 2: Run shell tests and confirm missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_shell.py tests/test_i18n.py -q`

Expected: FAIL because `payment_dashboard.ui.shell` and new translation keys do not exist.

- [ ] **Step 3: Implement the typed shell**

```python
class DashboardView(StrEnum):
    OVERVIEW = "overview"
    GATEWAYS = "gateways"
    ROUTING = "routing"
    TRANSACTIONS = "transactions"
    ADMIN = "admin"


FILTERED_VIEWS = frozenset(
    {DashboardView.OVERVIEW, DashboardView.GATEWAYS, DashboardView.TRANSACTIONS}
)


def active_view() -> DashboardView:
    raw = st.session_state.get("dashboard_view", DashboardView.OVERVIEW.value)
    try:
        return DashboardView(str(raw))
    except ValueError:
        return DashboardView.OVERVIEW
```

Render navigation with a single horizontal `st.radio` keyed as
`dashboard_view`; render filter widgets in a bordered container with columns and
the existing stable filter keys. Add English and Myanmar labels for product
name, five views, filter reset, and view descriptions.

- [ ] **Step 4: Run focused shell and translation tests**

Run: `.venv/bin/python -m pytest tests/test_shell.py tests/test_i18n.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the shell**

```bash
git add payment_dashboard/ui/shell.py payment_dashboard/i18n.py tests/test_shell.py tests/test_i18n.py
git commit -m "feat: add dashboard navigation shell"
```

### Task 2: Dark Theme and Shared Plotly Styling

**Files:**
- Create: `payment_dashboard/ui/chart_theme.py`
- Modify: `payment_dashboard/ui/style.py`
- Modify: `payment_dashboard/ui/charts.py`
- Modify: `payment_dashboard/ui/sections.py`
- Modify: `payment_dashboard/ui/optimization.py`
- Test: `tests/test_chart_theme.py`
- Test: `tests/test_style.py`
- Test: `tests/test_charts.py`

**Interfaces:**
- Produces: `apply_chart_theme(figure: go.Figure, *, show_legend: bool | None = None) -> go.Figure`.
- Consumes: existing Plotly figures without changing their traces or source data.

- [ ] **Step 1: Write failing theme tests**

```python
def test_chart_theme_uses_transparent_dark_layout() -> None:
    figure = apply_chart_theme(go.Figure())
    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.font.color == "#F8FAFC"
    assert figure.layout.xaxis.gridcolor == "#24364B"


def test_page_css_uses_approved_dark_tokens() -> None:
    assert "--canvas: #07111F" in PAGE_CSS
    assert "--surface: #0D1B2A" in PAGE_CSS
    assert "prefers-reduced-motion: reduce" in PAGE_CSS
    assert "#fffaf4" not in PAGE_CSS.lower()
```

- [ ] **Step 2: Run theme tests and confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_chart_theme.py tests/test_style.py tests/test_charts.py -q`

Expected: FAIL because the shared helper and approved dark CSS do not exist.

- [ ] **Step 3: Implement chart presentation helper**

```python
def apply_chart_theme(
    figure: go.Figure, *, show_legend: bool | None = None
) -> go.Figure:
    layout: dict[str, object] = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#F8FAFC", "family": "Inter, sans-serif"},
        "hoverlabel": {"bgcolor": "#122235", "font_color": "#F8FAFC"},
        "margin": {"l": 40, "r": 20, "t": 56, "b": 40},
    }
    if show_legend is not None:
        layout["showlegend"] = show_legend
    figure.update_layout(**layout)
    figure.update_xaxes(gridcolor="#24364B", zerolinecolor="#24364B")
    figure.update_yaxes(gridcolor="#24364B", zerolinecolor="#24364B")
    return figure
```

Call the helper at the end of every chart constructor and after inline figures
are created in section and optimization renderers. Replace `PAGE_CSS` with dark
tokens, dark Streamlit widgets/tables/forms, compact panels, horizontal
navigation styling, semantic status classes, two/one-column breakpoints, table
overflow containment, keyboard focus, and reduced-motion rules.

- [ ] **Step 4: Run focused presentation tests**

Run: `.venv/bin/python -m pytest tests/test_chart_theme.py tests/test_style.py tests/test_charts.py tests/test_optimization_ui.py -q`

Expected: PASS.

- [ ] **Step 5: Commit visual-system changes**

```bash
git add payment_dashboard/ui/chart_theme.py payment_dashboard/ui/style.py payment_dashboard/ui/charts.py payment_dashboard/ui/sections.py payment_dashboard/ui/optimization.py tests/test_chart_theme.py tests/test_style.py tests/test_charts.py tests/test_optimization_ui.py
git commit -m "feat: apply dark fintech visual system"
```

### Task 3: Focused View Composition

**Files:**
- Create: `payment_dashboard/ui/views.py`
- Modify: `payment_dashboard/ui/sections.py`
- Test: `tests/test_views.py`

**Interfaces:**
- Produces: `render_overview(snapshot: DashboardSnapshot, language: Language) -> None`, `render_gateways(snapshot: DashboardSnapshot, language: Language) -> None`, `render_routing_lab(report: OptimizationReport, language: Language) -> None`, and `render_transactions(snapshot: DashboardSnapshot, language: Language) -> None`.
- Consumes: existing section renderers and `render_optimization_report`; does not access repositories.

- [ ] **Step 1: Write failing view-composition tests**

```python
def test_overview_renders_operational_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    for name in (
        "render_kpis",
        "render_success_trend",
        "render_gateway_health",
        "render_recent_transactions",
    ):
        monkeypatch.setattr(views, name, lambda *args, _name=name, **kwargs: calls.append(_name))
    render_overview(snapshot, "en")
    assert calls == [
        "render_kpis",
        "render_success_trend",
        "render_gateway_health",
        "render_recent_transactions",
    ]


def test_gateways_does_not_render_transaction_table(monkeypatch: pytest.MonkeyPatch) -> None:
    recent = Mock()
    monkeypatch.setattr(views, "render_recent_transactions", recent)
    render_gateways(snapshot, "en")
    recent.assert_not_called()
```

- [ ] **Step 2: Run view tests and confirm missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_views.py -q`

Expected: FAIL because `payment_dashboard.ui.views` does not exist.

- [ ] **Step 3: Implement view composition**

```python
def render_overview(snapshot: DashboardSnapshot, language: Language) -> None:
    render_kpis(snapshot, language)
    trend, health = st.columns((1.7, 1.0))
    with trend:
        render_success_trend(snapshot, language)
    with health:
        render_gateway_health(snapshot.alerts, language)
    render_recent_transactions(snapshot.transactions, language, limit=8)


def render_gateways(snapshot: DashboardSnapshot, language: Language) -> None:
    render_gateway_performance(snapshot, language)
    render_failure_analysis(snapshot, language)
    render_gateway_health(snapshot.alerts, language)
```

Transactions renders the full paginated table plus interpretation guide. Routing
Lab delegates to `render_optimization_report`. Empty snapshots use
`render_empty_state` inside the active analytical view.

- [ ] **Step 4: Run focused view tests**

Run: `.venv/bin/python -m pytest tests/test_views.py tests/test_app.py -q`

Expected: PASS.

- [ ] **Step 5: Commit focused views**

```bash
git add payment_dashboard/ui/views.py payment_dashboard/ui/sections.py tests/test_views.py
git commit -m "feat: compose focused dashboard views"
```

### Task 4: Active-View Application Orchestration

**Files:**
- Modify: `payment_dashboard/app.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_admin_ui.py`

**Interfaces:**
- Consumes: Task 1 `DashboardView`, `FILTERED_VIEWS`, `render_top_navigation`, and `render_filter_bar`; Task 3 view renderers.
- Preserves: `_load_valid_snapshot`, `_load_optimization_contexts`, `_build_optimization_report`, pagination callbacks, MongoDB diagnostics, and `render_admin_panel` contracts.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_overview_does_not_build_routing_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "render_top_navigation", lambda language: DashboardView.OVERVIEW)
    build = Mock(side_effect=AssertionError("routing must be lazy"))
    monkeypatch.setattr(app, "_build_optimization_report", build)
    app.render_app()
    build.assert_not_called()


def test_routing_view_uses_unfiltered_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "render_top_navigation", lambda language: DashboardView.ROUTING)
    filters = Mock()
    monkeypatch.setattr(app, "render_filter_bar", filters)
    app.render_app()
    filters.assert_not_called()


def test_admin_view_does_not_render_analytical_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "render_top_navigation", lambda language: DashboardView.ADMIN)
    overview = Mock()
    monkeypatch.setattr(app, "render_overview", overview)
    app.render_app()
    overview.assert_not_called()
```

- [ ] **Step 2: Run orchestration tests and confirm old eager rendering fails**

Run: `.venv/bin/python -m pytest tests/test_app.py tests/test_admin_ui.py -q`

Expected: FAIL because the current `render_app` renders every section and builds routing evidence eagerly.

- [ ] **Step 3: Refactor `render_app` around the active view**

```python
view = render_top_navigation(language)
filters = (
    render_filter_bar(language, _reset_transaction_page, _reset_repository_filters)
    if view in FILTERED_VIEWS
    else DashboardFilters()
)
snapshot, page_number, total_pages = _load_valid_snapshot(
    filters, requested_page, language
)

if view is DashboardView.OVERVIEW:
    render_overview(snapshot, language)
elif view is DashboardView.GATEWAYS:
    render_gateways(snapshot, language)
elif view is DashboardView.ROUTING:
    optimization_frame, source = _load_optimization_contexts(snapshot, language)
    render_routing_lab(_build_optimization_report(optimization_frame, source), language)
elif view is DashboardView.TRANSACTIONS:
    render_transactions(snapshot, language)
else:
    render_admin_panel(database, snapshot.source, snapshot.transactions, language, password_hash)
```

Only Transactions renders pagination. Keep MongoDB error classification around
the exact view load that can fail. Keep hard lineage validation visible as an
error. Remove the old page title/description/hero duplication from the body and
render source state in the shell.

- [ ] **Step 4: Run application and admin tests**

Run: `.venv/bin/python -m pytest tests/test_app.py tests/test_admin_ui.py tests/test_shell.py tests/test_views.py -q`

Expected: PASS.

- [ ] **Step 5: Commit orchestration**

```bash
git add payment_dashboard/app.py tests/test_app.py tests/test_admin_ui.py
git commit -m "feat: isolate dashboard workflows by view"
```

### Task 5: Full Verification and Browser QA

**Files:**
- Modify: `scripts/smoke_dashboard.py`
- Modify: `tests/test_smoke_dashboard.py`
- Modify: `README.md`

**Interfaces:**
- Consumes the completed dashboard; produces no new runtime interface.

- [ ] **Step 1: Extend the smoke contract**

Add assertions that the browser can select each top-level view, the Overview
loads without a horizontal page scrollbar at desktop and narrow widths, and the
Admin view exposes login without rendering Overview KPI cards.

```python
for label in ("Overview", "Gateways", "Routing Lab", "Transactions", "Admin"):
    page.get_by_text(label, exact=True).click()
    page.wait_for_timeout(100)
assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
```

- [ ] **Step 2: Run smoke tests and confirm old expectations fail**

Run: `.venv/bin/python -m pytest tests/test_smoke_dashboard.py -q`

Expected: FAIL until the smoke helpers recognize the top-navigation shell.

- [ ] **Step 3: Update smoke helpers and README UI description**

Update browser helpers for the new stable navigation labels. Document the five
views, compact filter bar, dark command-center palette, and unchanged synthetic
routing disclaimer in README.

- [ ] **Step 4: Run all automated gates**

Run: `make check`

Expected: Ruff passes, strict mypy passes, and the complete pytest suite passes
with only the two documented optional live tests skipped.

- [ ] **Step 5: Run formatting and diff checks**

Run: `.venv/bin/ruff format --check payment_dashboard tests scripts && git diff --check`

Expected: all files formatted and no whitespace errors.

- [ ] **Step 6: Run the browser smoke test**

Run: `.venv/bin/python scripts/smoke_dashboard.py`

Expected: all five views render and desktop/narrow screenshots complete without
horizontal page overflow or uncaught Streamlit exceptions.

- [ ] **Step 7: Commit verification updates**

```bash
git add scripts/smoke_dashboard.py tests/test_smoke_dashboard.py README.md
git commit -m "test: verify dark dashboard navigation"
```
