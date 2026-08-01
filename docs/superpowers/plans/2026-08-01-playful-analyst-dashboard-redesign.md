# Playful Analyst Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the bilingual Streamlit payment dashboard into the approved Playful Analyst story-first interface and generate AI briefs in the user's selected English or Myanmar language.

**Architecture:** Preserve the existing analytics, MongoDB, authentication, and Streamlit state flow. Add language-aware prompt construction in `ai_brief.py`, localized presentation copy in `i18n.py`, semantic UI wrappers in `sections.py`, and a centralized responsive design system in `style.py`; `app.py` only coordinates the new story-first order and current language.

**Tech Stack:** Python 3.11+, Streamlit, pandas, Plotly, PyMongo, Anthropic-compatible Messages API, pytest, Streamlit AppTest, Ruff.

## Global Constraints

- Preserve transaction schemas, metric definitions, MongoDB collections, administrator authorization, soft-delete behavior, AI provider configuration, and deployment architecture.
- English mode generates English AI output; Myanmar mode generates Myanmar AI output directly, without post-generation translation.
- Use a warm off-white canvas, purple primary actions, apricot emphasis, mint healthy states, and soft rose failure states.
- Keep the dark sidebar, labeled language control, and selective red-panda mascot usage.
- Critical alerts must not rely on color alone.
- Narrow layouts must stack without horizontal page scrolling.
- Preserve unrelated user changes already present in the working tree.

---

### Task 1: Language-aware AI brief generation

**Files:**
- Modify: `payment_dashboard/ai_brief.py:88-203`
- Modify: `tests/test_ai_brief.py`

**Interfaces:**
- Consumes: `Language = Literal["en", "my"]` from `payment_dashboard.i18n`.
- Produces: `build_brief_prompt(facts: Mapping[str, object], language: Language = DEFAULT_LANGUAGE) -> str` and `generate_brief(facts: Mapping[str, object], *, language: Language = DEFAULT_LANGUAGE, base_url: str | None = None, api_key: str | None = None, model: str | None = None, timeout: float = 30.0) -> str`.

- [ ] **Step 1: Write failing prompt-language tests**

Add focused tests that assert the requested output language and localized headings:

```python
def test_build_brief_prompt_requests_english_output() -> None:
    prompt = build_brief_prompt({"transaction_count": 10}, language="en")
    assert "Write in English only." in prompt
    assert "## Executive summary" in prompt


def test_build_brief_prompt_requests_myanmar_output() -> None:
    prompt = build_brief_prompt({"transaction_count": 10}, language="my")
    assert "မြန်မာဘာသာဖြင့်သာ" in prompt
    assert "## အနှစ်ချုပ်" in prompt
    assert "transaction_count" in prompt
```

- [ ] **Step 2: Run the prompt tests and verify RED**

Run: `.venv/bin/pytest tests/test_ai_brief.py -k "prompt_requests" -v`

Expected: FAIL because `build_brief_prompt()` does not accept `language` and always requests English.

- [ ] **Step 3: Implement explicit prompt templates**

Add `ENGLISH_BRIEF_INSTRUCTIONS` and `MYANMAR_BRIEF_INSTRUCTIONS`, then select one without translating facts:

```python
def build_brief_prompt(
    facts: Mapping[str, object],
    language: Language = DEFAULT_LANGUAGE,
) -> str:
    facts_json = json.dumps(facts, sort_keys=True, ensure_ascii=False)
    instructions = (
        MYANMAR_BRIEF_INSTRUCTIONS
        if language == "my"
        else ENGLISH_BRIEF_INSTRUCTIONS
    )
    return f"{instructions}\n\n<facts_json>\n{facts_json}\n</facts_json>\n"
```

Both templates must require: supplied facts only, no invented figures, simulated gateway disclaimer, concise Markdown, and the same six semantic sections. Myanmar headings are `အနှစ်ချုပ်`, `အကောင်းဆုံးနှင့် အားနည်းဆုံး Gateway`, `အဓိက မူမမှန်မှု`, `အများဆုံး ကျရှုံးသည့် အပိုင်း`, `စမ်းသပ် Routing အကြံပြုချက်`, and `ပညာရေးသရုပ်ပြ ရှင်းလင်းချက်`.

- [ ] **Step 4: Write a failing request-payload test**

Extend the existing mocked Messages API test:

```python
result = generate_brief(
    facts,
    language="my",
    base_url="https://provider.example",
    api_key="secret",
)
payload = json.loads(captured_request.data)
assert "မြန်မာဘာသာဖြင့်သာ" in payload["messages"][0]["content"]
assert result == "မြန်မာ AI အနှစ်ချုပ်"
```

- [ ] **Step 5: Pass language through `generate_brief` and verify GREEN**

Add the keyword-only `language` parameter and call `build_brief_prompt(facts, language)` when constructing the payload.

Run: `.venv/bin/pytest tests/test_ai_brief.py -v`

Expected: all AI brief unit tests PASS.

- [ ] **Step 6: Commit the AI behavior**

```bash
git add payment_dashboard/ai_brief.py tests/test_ai_brief.py
git commit -m "feat: generate AI briefs in selected language"
```

---

### Task 2: Localized story-first copy and AI presentation

**Files:**
- Modify: `payment_dashboard/i18n.py`
- Modify: `payment_dashboard/ui/sections.py:52-112`
- Modify: `tests/test_i18n.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `translate(key: str, language: Language, **values: object) -> str`, `DashboardState`, and Task 1's `generate_brief(..., language=language)`.
- Produces: `render_story_hero(state: DashboardState, database_source: str, language: Language = DEFAULT_LANGUAGE) -> None`, `render_kpis(...) -> None`, and `render_ai_operations_brief(state: DashboardState, language: Language = DEFAULT_LANGUAGE) -> None`.

- [ ] **Step 1: Add failing translation completeness tests**

Define required keys and assert both dictionaries contain non-empty text:

```python
PLAYFUL_KEYS = {
    "hero.eyebrow", "hero.title", "hero.subtitle", "hero.database_live",
    "hero.demo_mode", "actions.reset_filters", "empty.title", "empty.body",
    "ai.title", "ai.description", "ai.generate", "ai.generating",
    "ai.evidence", "ai.requires_data", "ai.invalid_response",
}


def test_playful_dashboard_copy_exists_in_both_languages() -> None:
    for language in ("en", "my"):
        assert all(translate(key, language).strip() for key in PLAYFUL_KEYS)
```

- [ ] **Step 2: Run the translation test and verify RED**

Run: `.venv/bin/pytest tests/test_i18n.py -k playful -v`

Expected: FAIL with missing translation keys.

- [ ] **Step 3: Add English and Myanmar copy**

Add all `PLAYFUL_KEYS` plus localized hero format values. Use friendly but neutral wording; gateway names and numeric values remain unchanged. English hero title: `"{successful:,} payments made it through ✦"`. Myanmar hero title: `"ငွေပေးချေမှု {successful:,} ခု အောင်မြင်ခဲ့သည် ✦"`.

- [ ] **Step 4: Write failing section rendering tests**

Use mocked Streamlit calls to check the hero wrapper, five KPI labels, and Myanmar AI language propagation:

```python
def test_ai_brief_passes_selected_language(monkeypatch, dashboard_state) -> None:
    generated = MagicMock(return_value="မြန်မာ AI အနှစ်ချုပ်")
    monkeypatch.setattr(sections_module, "generate_brief", generated)
    # Mock button=True, spinner/container/expander as nullcontext, and output calls.
    render_ai_operations_brief(dashboard_state, language="my")
    assert generated.call_args.kwargs["language"] == "my"
```

Also assert switching language invalidates an earlier brief by including language in the stored fingerprint value.

- [ ] **Step 5: Implement semantic story, KPI, and AI wrappers**

Render stable HTML hooks using `st.markdown(..., unsafe_allow_html=True)`:

```python
def render_story_hero(state, database_source, language=DEFAULT_LANGUAGE):
    metrics = summary_metrics(state.display_frame)
    successful = metrics["transaction_count"] - metrics["failed_count"]
    status_key = "hero.database_live" if database_source == "mongodb" else "hero.demo_mode"
    st.markdown(
        build_story_hero_html(successful, metrics, status_key, language),
        unsafe_allow_html=True,
    )
```

Give KPI containers keys `kpi_transactions`, `kpi_success`, `kpi_failed`, `kpi_latency`, and `kpi_alerts`. Change AI rendering to localized strings and `generate_brief(facts, language=language)`. Fingerprint `{"language": language, "facts": facts}` so English text never remains visible after switching to Myanmar.

- [ ] **Step 6: Run focused section and localization tests**

Run: `.venv/bin/pytest tests/test_i18n.py tests/test_app.py -k "playful or hero or kpis or ai_brief" -v`

Expected: PASS.

- [ ] **Step 7: Commit localized presentation**

```bash
git add payment_dashboard/i18n.py payment_dashboard/ui/sections.py tests/test_i18n.py tests/test_app.py
git commit -m "feat: add bilingual story-first dashboard sections"
```

---

### Task 3: Playful Analyst responsive design system

**Files:**
- Modify: `payment_dashboard/ui/style.py`
- Modify: `tests/test_style.py`

**Interfaces:**
- Consumes: stable `playful-hero`, `status-pill`, `kpi-*`, `ai_brief_result`, and Streamlit `data-testid` hooks from Task 2.
- Produces: `PAGE_CSS` implementing the approved color system, component states, and responsive layout.

- [ ] **Step 1: Write failing CSS contract tests**

```python
def test_playful_theme_exposes_design_tokens_and_component_hooks() -> None:
    for token in (
        "--plum: #6c5ce7", "--apricot: #ffb86c", "--mint: #dff7eb",
        "--rose: #ffe1e8", "--ink: #2b2141", "--canvas: #fffaf4",
    ):
        assert token in PAGE_CSS
    for hook in (".playful-hero", ".status-pill", "kpi_success", "ai_brief_result"):
        assert hook in PAGE_CSS


def test_playful_theme_has_narrow_layout_rules() -> None:
    assert "@media (max-width: 768px)" in PAGE_CSS
    assert "overflow-x: hidden" in PAGE_CSS
```

- [ ] **Step 2: Run style tests and verify RED**

Run: `.venv/bin/pytest tests/test_style.py -v`

Expected: FAIL because the new tokens and hooks are absent.

- [ ] **Step 3: Replace ad-hoc colors with scoped design tokens**

At the start of `PAGE_CSS`, define:

```css
:root {
  --plum: #6c5ce7;
  --plum-dark: #4e3db8;
  --apricot: #ffb86c;
  --mint: #dff7eb;
  --rose: #ffe1e8;
  --ink: #2b2141;
  --muted: #6f667d;
  --canvas: #fffaf4;
  --surface: #ffffff;
  --sidebar: #2b2141;
  --radius-lg: 22px;
  --shadow-soft: 0 12px 35px rgba(43, 33, 65, 0.10);
}
```

Scope main text to dark colors and sidebar text to white. Style the hero gradient, status pill, five metric cards with distinct accent borders, primary/secondary buttons, alerts with icon-safe contrast, AI result card, dataframes, expanders, inputs, and sidebar groups. Keep focus outlines visible with at least `2px` width.

- [ ] **Step 4: Add responsive rules**

At `max-width: 768px`, reduce hero and card padding, stack custom grids, allow long Myanmar copy to wrap, hide decorative hero shapes, and prevent page-level horizontal overflow. Do not hide filters, status text, or table data.

- [ ] **Step 5: Verify CSS tests and formatting**

Run: `.venv/bin/pytest tests/test_style.py -v`

Run: `.venv/bin/ruff check payment_dashboard/ui/style.py tests/test_style.py`

Expected: PASS.

- [ ] **Step 6: Commit the visual system**

```bash
git add payment_dashboard/ui/style.py tests/test_style.py
git commit -m "feat: apply playful analyst visual system"
```

---

### Task 4: Story-first composition, sidebar guidance, and empty state

**Files:**
- Modify: `payment_dashboard/app.py:124-326`
- Modify: `payment_dashboard/ui/sections.py:115-239`
- Modify: `payment_dashboard/i18n.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_integration.py`

**Interfaces:**
- Consumes: Task 2's `render_story_hero(...)`, bilingual AI renderer, existing `build_dashboard_state(...)`, filter values, MongoDB `DatabaseResult`, and administrator panel.
- Produces: story-first `render_app()`, `render_empty_state(language: Language) -> None`, and a sidebar reset callback that clears only filter widget state.

- [ ] **Step 1: Write failing composition and empty-state tests**

Patch render functions to append names and assert the story order:

```python
assert calls == [
    "hero", "kpis", "ai", "gateway_health", "gateway_performance",
    "success_trend", "failure_analysis", "recent", "guide",
]
```

Add an empty-frame test asserting `render_empty_state(language)` runs and later chart/table renderers do not. Add a bilingual sidebar test asserting the reset button label is localized.

- [ ] **Step 2: Run focused app tests and verify RED**

Run: `.venv/bin/pytest tests/test_app.py tests/test_integration.py -k "composition or empty_state or reset" -v`

Expected: FAIL because the hero, reset action, and semantic empty state do not exist.

- [ ] **Step 3: Implement the approved page order**

After building `DashboardState`, call:

```python
render_story_hero(state, database_result.source, language)
render_kpis(state, language)
render_ai_operations_brief(state, language)
render_gateway_health(state.alerts, language)
```

If the display frame is empty, call `render_empty_state(language)` and return. Otherwise render gateway performance, paired trend/failure sections, recent transactions, guide, and finally the administrator panel in a separated container. Keep authentication and mutation calls unchanged.

- [ ] **Step 4: Add safe filter reset behavior**

Give filter widgets explicit keys and create:

```python
FILTER_WIDGET_KEYS = (
    "gateway_filter", "transaction_type_filter", "device_filter",
    "status_filter", "date_filter",
)


def _reset_display_filters() -> None:
    for key in FILTER_WIDGET_KEYS:
        st.session_state.pop(key, None)
```

Render a localized secondary reset button after the filter group. Do not reset replay count, language, AI configuration, or administrator authentication.

- [ ] **Step 5: Add the friendly mascot empty state**

Render a semantic `.empty-state` block with a small mascot image or existing pet asset, localized title/body, and instruction to reset filters. Include meaningful alternative text and keep the mascot decorative when the text already conveys the state.

- [ ] **Step 6: Run app and integration tests**

Run: `.venv/bin/pytest tests/test_app.py tests/test_integration.py -v`

Expected: PASS with English and Myanmar filter state preserved across language switches.

- [ ] **Step 7: Commit application composition**

```bash
git add payment_dashboard/app.py payment_dashboard/ui/sections.py payment_dashboard/i18n.py tests/test_app.py tests/test_integration.py
git commit -m "feat: compose story-first payment dashboard"
```

---

### Task 5: Full verification and deployment handoff

**Files:**
- Modify if required by verification: `README.md`
- Modify if required by verification: `docs/mongodb-atlas-setup.md`

**Interfaces:**
- Consumes: completed Tasks 1-4 and existing local/Streamlit Cloud configuration.
- Produces: verified desktop/mobile bilingual dashboard and concise operator documentation.

- [ ] **Step 1: Run the complete automated suite**

Run: `PYTHONPATH=. .venv/bin/pytest -q`

Expected: all tests PASS.

- [ ] **Step 2: Run lint, formatting, and diff checks**

Run: `.venv/bin/ruff check payment_dashboard tests`

Run: `.venv/bin/ruff format --check payment_dashboard tests`

Run: `git diff --check HEAD`

Expected: all commands exit 0.

- [ ] **Step 3: Verify desktop behavior in the browser**

Run: `make run`

At `http://localhost:8501`, verify the database-live and demo-fallback status variants, filters, reset action, hero figures, five KPIs, chart ordering, AI idle/loading/success/error states, recent table, and separated administrator panel. Confirm the selected language controls both static UI and newly generated AI text.

- [ ] **Step 4: Verify narrow-screen behavior**

At a viewport near `390 × 844`, confirm cards and charts stack, Myanmar text wraps, sidebar remains usable, focus indicators are visible, and the page has no horizontal scrollbar.

- [ ] **Step 5: Update operator documentation only where behavior changed**

Document that AI output follows the active language and that changing language invalidates the previous brief. Retain existing MongoDB and Streamlit Secrets instructions exactly; never add real secret values.

- [ ] **Step 6: Re-run verification after documentation or final fixes**

Run: `PYTHONPATH=. .venv/bin/pytest -q && .venv/bin/ruff check payment_dashboard tests && .venv/bin/ruff format --check payment_dashboard tests && git diff --check HEAD`

Expected: all commands exit 0.

- [ ] **Step 7: Commit verified documentation and final adjustments**

```bash
git add README.md docs/mongodb-atlas-setup.md payment_dashboard tests
git commit -m "docs: document bilingual AI dashboard behavior"
```

Stage only files intentionally changed by this plan; do not include `.DS_Store`, `.streamlit/secrets.toml`, `.superpowers/`, generated CSVs, or `build/`.
