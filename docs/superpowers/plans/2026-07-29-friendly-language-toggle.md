# Friendly Language Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing English/Burmese toggle into a labeled, accessible card with blue English styling and gold Burmese styling.

**Architecture:** Keep Streamlit's native toggle and stable `language_toggle` key. Add status translations in the central catalog, render the control inside a bordered Streamlit container, and scope state-dependent CSS to the container that owns the bilingual toggle.

**Tech Stack:** Python 3.11+, Streamlit 1.40+, pytest 8.3+, Ruff, local CSS

## Global Constraints

- English remains the off/default state; Burmese remains the on state.
- Preserve the exact widget key `language_toggle`.
- Show `Language / ဘာသာစကား` and the current-language status.
- Use blue `#2563EB` for English and gold `#D4A017` for Burmese.
- Preserve replay position, filters, and date range across language changes.
- Keep the native keyboard-accessible toggle; add no JavaScript or external assets.
- Scope styles so no unrelated Streamlit controls change.

---

### Task 1: Language-Control Copy

**Files:**
- Modify: `payment_dashboard/i18n.py`
- Modify: `tests/test_i18n.py`

**Interfaces:**
- Consumes: `translate(key: str, language: str = "en", **values: object) -> str`
- Produces: `language.control_label` and `language.current` in both catalogs

- [ ] **Step 1: Write failing catalog tests**

```python
def test_language_control_copy_is_bilingual() -> None:
    assert translate("language.control_label", "en") == "Language / ဘာသာစကား"
    assert translate("language.control_label", "my") == "Language / ဘာသာစကား"
    assert translate("language.current", "en", name="English") == (
        "Current: English"
    )
    assert translate("language.current", "my", name="မြန်မာ") == (
        "လက်ရှိ: မြန်မာ"
    )
```

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/python -m pytest tests/test_i18n.py -q`  
Expected: FAIL because the two keys are missing.

- [ ] **Step 3: Add matching catalog entries**

```python
"language.control_label": "Language / ဘာသာစကား",
"language.current": "Current: {name}",
```

Use the same control label in Burmese and `လက်ရှိ: {name}` for its status.

- [ ] **Step 4: Run tests and lint**

Run: `.venv/bin/python -m pytest tests/test_i18n.py -q`  
Run: `.venv/bin/ruff check payment_dashboard/i18n.py tests/test_i18n.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/i18n.py tests/test_i18n.py
git commit -m "feat: add language control copy"
```

### Task 2: Friendly Toggle Card

**Files:**
- Modify: `payment_dashboard/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: Task 1 translation keys
- Produces: `_render_language_toggle() -> Language`

- [ ] **Step 1: Add failing renderer tests**

Extend the current toggle test with Streamlit spies:

```python
def test_language_toggle_has_label_status_and_stable_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toggle = MagicMock(return_value=False)
    captions: list[str] = []
    monkeypatch.setattr(st, "toggle", toggle)
    monkeypatch.setattr(st, "caption", captions.append)

    assert _render_language_toggle() == "en"
    assert toggle.call_args.kwargs["key"] == "language_toggle"
    assert toggle.call_args.args[0] == "Language / ဘာသာစကား"
    assert captions == ["Current: English"]
```

Add a Burmese-state case that returns `"my"` and renders `လက်ရှိ: မြန်မာ`.

- [ ] **Step 2: Verify focused tests fail**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`  
Expected: FAIL because the status and card are absent.

- [ ] **Step 3: Render the native control inside a card**

Use `with st.container(border=True):`, render the translated control label on
the native toggle, and render the translated status beneath it. Do not change
the widget key, boolean-to-language mapping, placement before `st.title`, or
state-preservation callbacks.

- [ ] **Step 4: Run app and integration tests**

Run: `.venv/bin/python -m pytest tests/test_app.py tests/test_integration.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/app.py tests/test_app.py
git commit -m "feat: add friendly language toggle card"
```

### Task 3: Scoped Blue-and-Gold Styling

**Files:**
- Modify: `payment_dashboard/ui/style.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: native toggle with accessible name `Language / ဘာသာစကား`
- Produces: mode-specific local CSS scoped to the containing bordered block

- [ ] **Step 1: Add a failing CSS regression test**

```python
def test_language_toggle_css_is_scoped_and_uses_approved_colors() -> None:
    assert "#2563EB" in PAGE_CSS
    assert "#D4A017" in PAGE_CSS
    assert "Language / ဘာသာစကား" in PAGE_CSS
    assert ":checked" in PAGE_CSS
    assert ":focus-visible" in PAGE_CSS
```

- [ ] **Step 2: Verify the CSS test fails**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`  
Expected: FAIL because the approved colors and scoped selectors are absent.

- [ ] **Step 3: Add scoped state styling**

Target only the bordered Streamlit block containing
`input[aria-label="Language / ဘာသာစကား"]` using `:has(...)`. Give the card a
blue accent when unchecked and gold when checked. Style the native toggle track
and add a visible `:focus-visible` outline. Include light/dark-compatible border
and text colors; do not globally style all checkboxes or toggles.

- [ ] **Step 4: Run automated verification**

Run: `make format`  
Run: `make lint`  
Run: `make test`  
Expected: all commands PASS with no warnings.

- [ ] **Step 5: Run browser verification**

Start with: `ARROW_DEFAULT_MEMORY_POOL=system make run`

Verify at `http://localhost:8501`:

1. Card appears above the dashboard title.
2. English is default and uses blue `#2563EB`.
3. Burmese uses gold `#D4A017`.
4. Label and current-language status are visible.
5. Keyboard focus is visible.
6. Existing filter selections survive both transitions.
7. No console errors or Python crash occurs.

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/ui/style.py tests/test_app.py
git commit -m "style: color the bilingual language control"
```
