# Bilingual Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an English-default top-of-page toggle that translates all dashboard presentation text into Burmese without changing transaction data or analytics.

**Architecture:** A new `i18n.py` module owns supported languages, translation keys, and English fallback behavior. The app selects a language once and passes it explicitly through sidebar, section, and chart renderers; data values and internal DataFrame columns remain unchanged.

**Tech Stack:** Python 3.11+, Streamlit 1.40+, Plotly 5.24+, pandas 2.2+, pytest 8.3+, Ruff

## Global Constraints

- English is the default language for every new Streamlit session.
- The language toggle appears above the dashboard title and switches immediately.
- Translate presentation text only; never translate stored category values or internal columns.
- Unknown languages and missing Burmese values fall back to English.
- Add no localization framework, web font, network service, or persistent preference.
- Keep existing analytical calculations and simulated gateway behavior unchanged.

---

### Task 1: Translation Core

**Files:**
- Create: `payment_dashboard/i18n.py`
- Create: `tests/test_i18n.py`

**Interfaces:**
- Produces: `Language = Literal["en", "my"]`
- Produces: `DEFAULT_LANGUAGE: Final[Language] = "en"`
- Produces: `SUPPORTED_LANGUAGES: Final[tuple[Language, ...]]`
- Produces: `translate(key: str, language: str = DEFAULT_LANGUAGE, **values: object) -> str`

- [ ] **Step 1: Write failing translation tests**

```python
from payment_dashboard.i18n import (
    DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, TRANSLATIONS, translate,
)

def test_translation_catalogs_have_matching_keys() -> None:
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["my"])

def test_english_is_default_and_burmese_is_supported() -> None:
    assert DEFAULT_LANGUAGE == "en"
    assert SUPPORTED_LANGUAGES == ("en", "my")
    assert translate("dashboard.title") == "Payment Success Monitor"
    assert translate("dashboard.title", "my") == "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်"

def test_unknown_language_and_blank_translation_fall_back_to_english() -> None:
    assert translate("dashboard.title", "fr") == "Payment Success Monitor"
    assert translate("test.fallback", "my") == "Fallback"
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run: `.venv/bin/python -m pytest tests/test_i18n.py -q`
Expected: FAIL because `payment_dashboard.i18n` does not exist.

- [ ] **Step 3: Implement the catalog and lookup**

Create both catalogs with identical semantic keys grouped by `language`,
`dashboard`, `sidebar`, `kpi`, `health`, `charts`, `sections`, `table`,
`guide`, and `errors`. Include every visible literal currently found in
`app.py`, `ui/sections.py`, and `ui/charts.py`, plus:

```python
from typing import Final, Literal

Language = Literal["en", "my"]
DEFAULT_LANGUAGE: Final[Language] = "en"
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("en", "my")

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "dashboard.title": "Payment Success Monitor",
        "language.label": "Language",
        "language.english": "English",
        "language.burmese": "မြန်မာ",
        "test.fallback": "Fallback",
    },
    "my": {
        "dashboard.title": "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်",
        "language.label": "ဘာသာစကား",
        "language.english": "English",
        "language.burmese": "မြန်မာ",
        "test.fallback": "",
    },
}

def translate(key: str, language: str = DEFAULT_LANGUAGE, **values: object) -> str:
    english = TRANSLATIONS["en"].get(key, key)
    localized = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, english)
    template = localized or english
    return template.format(**values)
```

- [ ] **Step 4: Run focused tests and lint**

Run: `.venv/bin/python -m pytest tests/test_i18n.py -q`
Expected: PASS.

Run: `.venv/bin/ruff check payment_dashboard/i18n.py tests/test_i18n.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/i18n.py tests/test_i18n.py
git commit -m "feat: add bilingual translation catalog"
```

### Task 2: Localized Charts

**Files:**
- Modify: `payment_dashboard/ui/charts.py`
- Create: `tests/test_charts.py`

**Interfaces:**
- Consumes: `translate(key: str, language: str = "en", **values: object) -> str`
- Produces: all four chart builders with an optional `language: str = "en"`

- [ ] **Step 1: Add failing tests for chart titles and unchanged categories**

```python
def test_gateway_chart_localizes_title_without_changing_categories(
    dashboard_fixture: pd.DataFrame,
) -> None:
    chart = gateway_success_chart(dashboard_fixture, language="my")
    assert chart.layout.title.text == "ဂိတ်ဝေးအလိုက် အောင်မြင်နှုန်း"
    assert set(chart.data[0].x) <= set(dashboard_fixture["Bank Gateway"])

def test_failure_chart_defaults_to_english(dashboard_fixture: pd.DataFrame) -> None:
    chart = failure_breakdown_chart(
        dashboard_fixture, "Device Used", "Device", language="en"
    )
    assert chart.layout.title.text == "Failures by device"
```

- [ ] **Step 2: Verify the new keyword argument fails**

Run: `.venv/bin/python -m pytest tests/test_charts.py -q`
Expected: FAIL with an unexpected `language` argument.

- [ ] **Step 3: Localize titles and visible axes**

Update signatures:

```python
def gateway_success_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
def gateway_volume_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
def success_trend_chart(frame: pd.DataFrame, language: str = "en") -> go.Figure:
def failure_breakdown_chart(
    frame: pd.DataFrame, dimension: str, title: str, language: str = "en"
) -> go.Figure:
```

Use `translate()` for Plotly titles and axis labels. Continue passing the
original column names to `x`, `y`, and `color`. Build the failure title with a
catalog key such as `charts.failures_by` and a translated display dimension.

- [ ] **Step 4: Run chart and analytics tests**

Run: `.venv/bin/python -m pytest tests/test_charts.py tests/test_analytics.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/ui/charts.py tests/test_charts.py
git commit -m "feat: localize dashboard charts"
```

### Task 3: Localized Dashboard Sections

**Files:**
- Modify: `payment_dashboard/ui/sections.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: localized chart builders from Task 2
- Produces: `render_kpis`, `render_gateway_health`,
  `render_gateway_performance`, `render_success_trend`,
  `render_failure_analysis`, `render_recent_transactions`, and
  `render_interpretation_guide`, each accepting `language: str = "en"`

- [ ] **Step 1: Write failing renderer tests**

```python
from unittest.mock import MagicMock

@pytest.fixture
def dashboard_state(dashboard_fixture: pd.DataFrame) -> DashboardState:
    alerts = evaluate_alerts(dashboard_fixture)
    return DashboardState(dashboard_fixture, dashboard_fixture, alerts)

def test_kpis_render_burmese_labels(
    monkeypatch: pytest.MonkeyPatch, dashboard_state: DashboardState
) -> None:
    columns = [MagicMock() for _ in range(5)]
    monkeypatch.setattr(st, "columns", lambda count: columns)
    render_kpis(dashboard_state, language="my")
    assert columns[0].metric.call_args.args[0] == "ငွေပေးချေမှုများ"

def test_gateway_health_keeps_gateway_values(
    monkeypatch: pytest.MonkeyPatch, dashboard_state: DashboardState
) -> None:
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(st, "dataframe", lambda frame, **_: captured.append(frame))
    render_gateway_health(dashboard_state.alerts, language="my")
    assert set(captured[0]["ဂိတ်ဝေး"]) == set(
        dashboard_state.alerts["Bank Gateway"]
    )
```

- [ ] **Step 2: Verify renderer tests fail**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`
Expected: FAIL because renderers do not accept `language`.

- [ ] **Step 3: Thread language through sections**

Add `language: str = "en"` to every public renderer. Replace visible literals
with `translate()` calls, pass `language` to chart builders, localize copied
table headings and display-only health statuses, and retain values copied from
the source DataFrames. Use translated Markdown strings for the interpretation
guide.

- [ ] **Step 4: Run section and chart tests**

Run: `.venv/bin/python -m pytest tests/test_app.py tests/test_charts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/ui/sections.py tests/test_app.py
git commit -m "feat: localize dashboard sections"
```

### Task 4: Top-Level Toggle and End-to-End Verification

**Files:**
- Modify: `payment_dashboard/app.py`
- Modify: `payment_dashboard/ui/style.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_integration.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `DEFAULT_LANGUAGE`, `translate()`, and localized renderers
- Produces: `_render_language_toggle() -> str`

- [ ] **Step 1: Write failing toggle and bilingual app tests**

```python
def test_language_toggle_defaults_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(st, "toggle", lambda *_, **kwargs: kwargs["value"])
    assert _render_language_toggle() == "en"

def test_burmese_mode_keeps_neutral_filter_values(
    monkeypatch: pytest.MonkeyPatch, dashboard_fixture: pd.DataFrame
) -> None:
    multiselect = MagicMock(return_value=[])
    monkeypatch.setattr(st.sidebar, "multiselect", multiselect)
    monkeypatch.setattr(st.sidebar, "slider", lambda *_, **kwargs: kwargs["value"])
    monkeypatch.setattr(
        st.sidebar, "date_input", lambda *_, **kwargs: kwargs["value"]
    )
    _render_sidebar(dashboard_fixture, language="my")
    gateway_options = multiselect.call_args_list[0].args[1]
    assert "Gateway A" in gateway_options
```

Implement the control as
`st.toggle("English / မြန်မာ", value=False, key="language_toggle")`; map
`False` to `"en"` and `True` to `"my"`.

- [ ] **Step 2: Run app tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_app.py tests/test_integration.py -q`
Expected: FAIL because the language toggle and language parameters are absent.

- [ ] **Step 3: Implement the app-level language flow**

Render the control before `st.title`, return `"en"` or `"my"`, translate page
copy and errors, pass the language to `_render_sidebar` and every section
renderer, and keep `st.set_page_config` before all other Streamlit calls. Add a
Burmese-capable font fallback to the existing CSS:

```css
html, body, [class*="css"] {
  font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", sans-serif;
}
```

Document the top-of-page language switch in `README.md`.

- [ ] **Step 4: Run full verification**

Run: `make format`
Expected: Ruff formats changed Python files.

Run: `make lint`
Expected: PASS.

Run: `make test`
Expected: all unit and integration tests PASS.

Run: `make run`
Expected: the app opens with English selected; switching to `မြန်မာ` translates
the UI while gateway and transaction category values stay unchanged.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/app.py payment_dashboard/ui/style.py \
  tests/test_app.py tests/test_integration.py README.md
git commit -m "feat: add bilingual dashboard toggle"
```
