# Payment Dashboard Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make simulated gateway performance meaningful and reproducible, bound MongoDB reads, expose degraded mode honestly, guarantee usable bilingual briefs, remove duplicate build output, and prove behavior with layered tests.

**Architecture:** Keep Streamlit shell. Add controlled simulation plus repository contract separating demo pandas analytics from MongoDB aggregation. Return one typed dashboard snapshot to UI; AI path returns validated structured result or deterministic fallback.

**Tech Stack:** Python 3.11+, pandas, NumPy, PyMongo, Streamlit, pytest, Ruff.

## Global Constraints

- Preserve Streamlit architecture; no REST/frontend rewrite.
- Gateway and outcome data remain simulated, seeded, versioned, and labeled.
- MongoDB transaction page size defaults to 50 and stays bounded.
- Default tests require no network or secrets.
- Only aggregate facts may leave application for AI generation.
- Preserve unrelated dirty files and never commit `.streamlit/secrets.toml`.
- Use test-first red-green-refactor flow and focused Conventional Commits.

---

### Task 1: Controlled payment simulation

**Files:**
- Create: `payment_dashboard/simulation.py`
- Modify: `payment_dashboard/config.py`
- Modify: `payment_dashboard/prepare_data.py`
- Modify: `payment_dashboard/load_mongodb.py`
- Test: `tests/test_simulation.py`
- Test: `tests/test_prepare_data.py`

**Interfaces:**
- Consumes: source DataFrame using existing Kaggle column names and `DEFAULT_SEED`.
- Produces: `simulate_transactions(frame: pd.DataFrame, seed: int = DEFAULT_SEED) -> pd.DataFrame` and `SIMULATION_VERSION: str`.
- Output adds `Source Transaction Status`, replaces `Transaction Status` with simulated status, and adds `Simulation Version`.

- [ ] **Step 1: Write deterministic and probability tests**

```python
def test_simulation_is_deterministic(transactions: pd.DataFrame) -> None:
    first = simulate_transactions(transactions, seed=42)
    second = simulate_transactions(transactions, seed=42)
    pd.testing.assert_frame_equal(first, second)


def test_simulation_preserves_source_status(transactions: pd.DataFrame) -> None:
    result = simulate_transactions(transactions, seed=42)
    assert result["Source Transaction Status"].tolist() == transactions[
        "Transaction Status"
    ].tolist()
    assert set(result["Transaction Status"]) <= {"Success", "Failed"}
    assert result["Simulation Version"].eq(SIMULATION_VERSION).all()


def test_gateway_a_outperforms_gateway_d_on_large_sample(
    large_transactions: pd.DataFrame,
) -> None:
    result = simulate_transactions(large_transactions, seed=42)
    rates = result.groupby("Bank Gateway")["Transaction Status"].apply(
        lambda values: values.eq("Success").mean()
    )
    assert rates["Gateway A"] > rates["Gateway D"]
```

- [ ] **Step 2: Run tests and confirm red**

Run: `.venv/bin/pytest tests/test_simulation.py tests/test_prepare_data.py -q`  
Expected: FAIL because `payment_dashboard.simulation` and new metadata do not exist.

- [ ] **Step 3: Implement minimal simulation**

Use configured gateway base rates and additive risk adjustments for device, type, UTC hour, and amount band. Clamp probabilities to `[0.55, 0.99]`. Sort stably by timestamp, use one `np.random.default_rng(seed)`, assign gateways, draw outcomes, and preserve original status. Change `prepare_file()` invariants to verify source-status preservation instead of forbidding outcome changes. Extend Mongo document mapping/import fields for source status and simulation version.

- [ ] **Step 4: Run focused and preparation tests**

Run: `.venv/bin/pytest tests/test_simulation.py tests/test_prepare_data.py tests/test_load_mongodb.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/simulation.py payment_dashboard/config.py payment_dashboard/prepare_data.py payment_dashboard/load_mongodb.py tests/test_simulation.py tests/test_prepare_data.py tests/test_load_mongodb.py
git commit -m "feat: add controlled payment simulation"
```

### Task 2: Typed dashboard repository contract

**Files:**
- Create: `payment_dashboard/dashboard_repository.py`
- Modify: `payment_dashboard/models.py`
- Test: `tests/test_dashboard_repository.py`

**Interfaces:**
- Produces `DashboardFilters`, `PageRequest`, `DataSource`, `DashboardSnapshot`, and `DashboardRepository` protocol.
- Produces `PandasDashboardRepository(frame: pd.DataFrame).fetch(filters, page) -> DashboardSnapshot`.
- `DashboardSnapshot` contains `metrics`, `gateway_summary`, `trend`, `failure_summary`, `alerts`, `transactions`, `total_transactions`, `source`, `simulation_version`, and `diagnostic`.

- [ ] **Step 1: Write repository contract tests**

```python
def test_pandas_repository_filters_and_pages(prepared_fixture: pd.DataFrame) -> None:
    repository = PandasDashboardRepository(prepared_fixture)
    snapshot = repository.fetch(
        DashboardFilters(gateways=("Gateway A",)),
        PageRequest(number=1, size=2),
    )
    assert snapshot.source is DataSource.DEMO
    assert len(snapshot.transactions) <= 2
    assert snapshot.total_transactions >= len(snapshot.transactions)
    assert set(snapshot.transactions["Bank Gateway"]) <= {"Gateway A"}


def test_page_size_is_bounded() -> None:
    with pytest.raises(ValueError, match="page size"):
        PageRequest(number=1, size=501)
```

- [ ] **Step 2: Run contract tests and confirm red**

Run: `.venv/bin/pytest tests/test_dashboard_repository.py -q`  
Expected: FAIL because repository types do not exist.

- [ ] **Step 3: Implement contract and pandas adapter**

Use frozen dataclasses and `DataSource(str, Enum)` with `LIVE` and `DEMO`. Validate page number `>= 1`, size `1..100`, and date range order. Reuse existing analytics, filter, and alert functions inside pandas adapter. Stable page sort: timestamp descending, transaction ID ascending.

- [ ] **Step 4: Run repository and analytics tests**

Run: `.venv/bin/pytest tests/test_dashboard_repository.py tests/test_analytics.py tests/test_alerting.py tests/test_integration.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/dashboard_repository.py payment_dashboard/models.py tests/test_dashboard_repository.py
git commit -m "feat: define dashboard repository contract"
```

### Task 3: MongoDB aggregation and pagination

**Files:**
- Modify: `payment_dashboard/mongodb.py`
- Test: `tests/test_mongodb.py`
- Test: `tests/test_mongodb_repository.py`

**Interfaces:**
- Consumes Task 2 types.
- Produces `MongoDashboardRepository(database: Any).fetch(filters: DashboardFilters, page: PageRequest) -> DashboardSnapshot`.
- Produces `classify_mongodb_error(exc: Exception) -> str` returning safe categories only.

- [ ] **Step 1: Write Mongo pipeline and bounded-page tests**

```python
def test_mongo_repository_uses_aggregation_and_bounded_page(database) -> None:
    snapshot = MongoDashboardRepository(database).fetch(
        DashboardFilters(statuses=("Failed",)),
        PageRequest(number=2, size=50),
    )
    pipeline = database["transactions"].aggregate_calls[0]
    assert pipeline[0]["$match"]["is_deleted"] == {"$ne": True}
    assert snapshot.source is DataSource.LIVE
    assert database["transactions"].find_called is False
    assert len(snapshot.transactions) <= 50


def test_indexes_cover_dashboard_queries(database) -> None:
    ensure_indexes(database)
    assert (("is_deleted", 1), ("transaction_timestamp", -1)) in database[
        "transactions"
    ].created_indexes
```

- [ ] **Step 2: Run Mongo tests and confirm red**

Run: `.venv/bin/pytest tests/test_mongodb.py tests/test_mongodb_repository.py -q`  
Expected: FAIL because current loader calls unbounded `find()` and returns `DatabaseResult`.

- [ ] **Step 3: Implement aggregation repository**

Build validated `$match` from filters. Use `$facet` or focused pipelines for metrics, gateway, trend, failure, total count, and page results. Use page `$sort`, `$skip`, `$limit`; never materialize unbounded cursor. Create compound indexes matching active timestamp and filter dimensions. Catch only PyMongo configuration/connection/query exceptions at repository-selection boundary; remove broad `except Exception` fallback.

- [ ] **Step 4: Run Mongo and mutation tests**

Run: `.venv/bin/pytest tests/test_mongodb.py tests/test_mongodb_repository.py tests/test_transaction_service.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/mongodb.py tests/test_mongodb.py tests/test_mongodb_repository.py
git commit -m "feat: aggregate and paginate MongoDB dashboard data"
```

### Task 4: Explicit live and degraded UI states

**Files:**
- Modify: `payment_dashboard/app.py`
- Modify: `payment_dashboard/ui/sections.py`
- Modify: `payment_dashboard/ui/admin.py`
- Modify: `payment_dashboard/i18n.py`
- Test: `tests/test_app.py`
- Test: `tests/test_admin_ui.py`

**Interfaces:**
- Consumes `DashboardRepository.fetch()` and `DashboardSnapshot`.
- Produces `_load_snapshot(...) -> DashboardSnapshot` and `_render_source_status(snapshot, language) -> None`.
- Retry button key: `database_retry`; page state key: `transaction_page`.

- [ ] **Step 1: Write degraded-state and pagination UI tests**

```python
def test_degraded_mode_is_explicit_and_disables_editing(monkeypatch) -> None:
    app = AppTest.from_file("streamlit_app.py")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    app.run()
    assert any("DEMO" in item.value for item in app.markdown)
    assert any("simulated demo data" in item.value.lower() for item in app.warning)
    assert app.button(key="database_retry")


def test_transaction_page_changes_without_full_reload(monkeypatch) -> None:
    app = AppTest.from_file("streamlit_app.py")
    app.run()
    assert app.number_input(key="transaction_page").value == 1
```

- [ ] **Step 2: Run AppTest cases and confirm red**

Run: `.venv/bin/pytest tests/test_app.py tests/test_admin_ui.py -q`  
Expected: FAIL because source badges, retry control, and page control do not exist.

- [ ] **Step 3: Integrate repositories and degraded UX**

Replace full-frame load path with repository selection and snapshot fetch. Render localized persistent warning and repeated `LIVE`/`DEMO` badges. Retry clears Streamlit data/resource caches and reruns. Show safe diagnostic category in expander. Pass `None` database and fallback source to admin panel so mutations stay disabled. Render recent page plus page/total controls.

- [ ] **Step 4: Run UI and localization tests**

Run: `.venv/bin/pytest tests/test_app.py tests/test_admin_ui.py tests/test_i18n.py tests/test_style.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/app.py payment_dashboard/ui/sections.py payment_dashboard/ui/admin.py payment_dashboard/i18n.py tests/test_app.py tests/test_admin_ui.py tests/test_i18n.py
git commit -m "feat: expose dashboard data source and degraded mode"
```

### Task 5: Structured AI brief with retry and local fallback

**Files:**
- Modify: `payment_dashboard/ai_brief.py`
- Modify: `payment_dashboard/ui/sections.py`
- Modify: `payment_dashboard/i18n.py`
- Test: `tests/test_ai_brief.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces `BriefContent(summary: str, risks: tuple[str, ...], actions: tuple[str, ...], evidence: tuple[str, ...])`.
- Produces `BriefResult(content: BriefContent, origin: Literal["ai", "local"])`.
- Produces `generate_brief_result(facts, language, ..., attempts=2) -> BriefResult`.
- Produces `build_local_brief(facts, language) -> BriefContent`.

- [ ] **Step 1: Write structured-response, retry, and fallback tests**

```python
def test_generate_brief_returns_validated_structure(monkeypatch, facts) -> None:
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", valid_json_response)
    result = generate_brief_result(facts, base_url="https://provider", api_key="x")
    assert result.origin == "ai"
    assert result.content.summary
    assert result.content.actions


def test_retry_exhaustion_returns_local_brief(monkeypatch, facts) -> None:
    monkeypatch.setattr(
        ai_brief.urllib.request,
        "urlopen",
        Mock(side_effect=URLError("offline")),
    )
    result = generate_brief_result(
        facts, base_url="https://provider", api_key="x", attempts=2
    )
    assert result.origin == "local"
    assert result.content.summary


def test_auth_error_does_not_retry(monkeypatch, facts) -> None:
    provider = Mock(side_effect=http_error(401))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)
    result = generate_brief_result(facts, base_url="https://provider", api_key="x")
    assert provider.call_count == 1
    assert result.origin == "local"
```

- [ ] **Step 2: Run AI tests and confirm red**

Run: `.venv/bin/pytest tests/test_ai_brief.py -q`  
Expected: FAIL because structured result and fallback functions do not exist.

- [ ] **Step 3: Implement robust generation**

Request JSON-only content containing four required keys. Parse text block as JSON, validate non-empty bounded strings/lists, and reject evidence contradicting supplied aggregate values. Retry timeout, `URLError`, HTTP 429, and HTTP 5xx once with injectable short sleep. Return deterministic English/Myanmar local brief on any terminal provider failure. Update UI to render sections and localized origin badge. Fingerprint includes language, model, filters, and simulation/data version.

- [ ] **Step 4: Run AI and UI tests**

Run: `.venv/bin/pytest tests/test_ai_brief.py tests/test_app.py tests/test_i18n.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/ai_brief.py payment_dashboard/ui/sections.py payment_dashboard/i18n.py tests/test_ai_brief.py tests/test_app.py tests/test_i18n.py
git commit -m "feat: make AI briefs resilient and structured"
```

### Task 6: Packaging cleanup and layered external checks

**Files:**
- Modify: `.gitignore`
- Modify: `Makefile`
- Modify: `pyproject.toml`
- Create: `tests/test_live_atlas.py`
- Create: `tests/test_live_ai.py`
- Create: `scripts/smoke_dashboard.py`
- Modify: `README.md`
- Delete: `build/`

**Interfaces:**
- `RUN_ATLAS_TESTS=1` enables dedicated live Atlas contract test.
- `RUN_AI_TESTS=1` enables bounded live provider test.
- `python scripts/smoke_dashboard.py <url>` exits nonzero on load failure, missing source badge/KPIs, or visible exception.
- Smoke command uses Playwright from dev dependencies and installed Chromium; production dependencies stay unchanged.

- [ ] **Step 1: Write guarded live tests and smoke-script unit test**

```python
@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_ATLAS_TESTS") != "1", reason="live Atlas disabled")
def test_live_atlas_repository_contract() -> None:
    resources = create_resources_from_env()
    assert resources is not None
    snapshot = MongoDashboardRepository(resources.database).fetch(
        DashboardFilters(), PageRequest(number=1, size=1)
    )
    assert snapshot.source is DataSource.LIVE


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_AI_TESTS") != "1", reason="live AI disabled")
def test_live_ai_contract() -> None:
    result = generate_brief_result(MINIMAL_FACTS, timeout=10, attempts=1)
    assert result.origin == "ai"
```

- [ ] **Step 2: Run default suite and prove live tests skip**

Run: `.venv/bin/pytest tests/test_live_atlas.py tests/test_live_ai.py -q`  
Expected: two SKIPPED results without secrets or flags.

- [ ] **Step 3: Add commands, ignores, smoke script, and docs**

Add `build/`, `.streamlit/secrets.toml`, `.agents/`, `.codex-plugins/`, and `.superpowers/` to `.gitignore`. Remove generated `build/`. Add `build>=1.2,<2` and `playwright>=1.49,<2` to dev dependencies. Add `test-live` target running integration tests with opt-in flags and `smoke` target requiring `DASHBOARD_URL`. Document simulation assumptions, degraded mode, pagination, AI fallback, and exact test commands. Smoke script launches headless Chromium, waits for Streamlit readiness, then asserts visible source badge, KPI labels, and absence of exception elements.

- [ ] **Step 4: Run packaging and command verification**

Run: `make test && make lint && .venv/bin/ruff format --check payment_dashboard tests scripts`  
Expected: PASS; live tests SKIP unless flags supplied.  
Run: `.venv/bin/python -m playwright install chromium`  
Expected: Chromium browser installed for optional smoke checks.  
Run: `.venv/bin/python -m build`  
Expected: wheel/sdist build from `payment_dashboard/` only.

- [ ] **Step 5: Commit**

```bash
git add .gitignore Makefile pyproject.toml README.md tests/test_live_atlas.py tests/test_live_ai.py scripts/smoke_dashboard.py
git commit -m "test: add layered dashboard verification"
```

### Task 7: Full migration verification

**Files:**
- Modify: `README.md`
- Modify: `docs/images/dashboard-playful-desktop.jpg`
- Modify: `docs/images/dashboard-playful-mobile.jpg`
- Test: complete `tests/` suite

**Interfaces:**
- Verifies all earlier task contracts together; introduces no new public API.

- [ ] **Step 1: Regenerate fixture data and run focused pipeline**

Run: `make prepare`  
Expected: processed CSV contains `Bank Gateway`, simulated `Transaction Status`, `Source Transaction Status`, and `Simulation Version`.

- [ ] **Step 2: Run full offline verification**

Run: `make test && make lint && .venv/bin/ruff format --check payment_dashboard tests scripts && git diff --check`  
Expected: all commands PASS.

- [ ] **Step 3: Run local Streamlit smoke**

Run: `make run` in one terminal, then `DASHBOARD_URL=http://localhost:8501 make smoke` in another.  
Expected: source badge and KPIs found; no visible exception marker.

- [ ] **Step 4: Verify browser flows manually**

Check English/Myanmar toggle, filters, transaction pagination, AI brief origin label, forced Atlas fallback warning, retry button, and disabled fallback editing at desktop and 390px viewport. Capture fresh desktop and mobile README screenshots because source badges, pagination, and brief-origin labels change visible UI.

- [ ] **Step 5: Commit migration fixes and documentation evidence**

```bash
git add payment_dashboard tests scripts README.md docs/images
git commit -m "fix: complete dashboard hardening migration"
```
