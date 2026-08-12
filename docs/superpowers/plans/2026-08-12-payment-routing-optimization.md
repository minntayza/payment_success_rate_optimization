# Payment Routing Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing synthetic monitoring dashboard into a reproducible constrained payment-routing benchmark that compares an MILP allocation with four baseline policies while repairing the project's data-safety, monitoring, and quality gaps.

**Architecture:** Preserve the Kaggle CSV as immutable transaction context, remove prohibited fields during preparation, and create a separate routing benchmark containing public candidate features and hidden potential outcomes. Pure policy, solver, and evaluation modules produce a typed `OptimizationReport`; Streamlit only renders the report. Existing monitoring remains separate and receives a leakage-free historical baseline.

**Tech Stack:** Python 3.11+, pandas 2.2, NumPy 2.1, SciPy 1.14 (`scipy.optimize.milp`), Streamlit 1.40, Plotly 5.24, PyMongo 4.10, pytest 8.3, Ruff, mypy.

## Global Constraints

- Keep the source CSV unchanged and ignored by Git.
- Label all gateway alternatives and optimizer results as a `SYNTHETIC BENCHMARK`.
- Never expose a potential outcome to a routing policy before its decision is fixed.
- Never store, render, audit, prompt, or export `PIN Code` or `pin_code`.
- Use chronological 60/20/20 development, validation, and test splits.
- Each transaction must receive exactly one eligible gateway unless its time bucket is explicitly infeasible.
- No silent eligibility, availability, capacity, or fee-ceiling violations.
- Keep default tests offline and credential-free.
- Preserve unrelated existing user changes.

---

### Task 1: Establish data safety and strict source validation

**Files:**
- Modify: `payment_dashboard/config.py`
- Modify: `payment_dashboard/data_loader.py`
- Modify: `payment_dashboard/load_mongodb.py`
- Modify: `payment_dashboard/mongodb.py`
- Modify: `payment_dashboard/transaction_service.py`
- Modify: `payment_dashboard/ui/admin.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_data_loader.py`
- Modify: `tests/test_load_mongodb.py`
- Modify: `tests/test_mongodb.py`
- Modify: `tests/test_mongodb_repository.py`
- Modify: `tests/test_transaction_service.py`
- Modify: `tests/test_admin_ui.py`

**Interfaces:**
- Produces: `validate_raw_transactions(frame: pd.DataFrame) -> None`
- Produces: `validate_prepared_transactions(frame: pd.DataFrame) -> None`
- Produces: `load_transactions(path: str | Path, require_gateway: bool = True) -> pd.DataFrame` with prohibited columns removed
- Produces: `PUBLIC_TRANSACTION_PROJECTION: dict[str, int]`

- [ ] **Step 1: Write failing source-validation and PIN-removal tests**

```python
@pytest.mark.parametrize("value", ["maybe", 2, -1, None])
def test_raw_validation_rejects_invalid_fraud_flags(sample_transactions, value):
    frame = sample_transactions.assign(**{"Fraud Flag": value})
    with pytest.raises(DataValidationError, match="Fraud Flag"):
        validate_raw_transactions(frame)


def test_loader_removes_pin_column(tmp_path, sample_transactions):
    path = tmp_path / "transactions.csv"
    sample_transactions.to_csv(path, index=False)
    loaded = load_transactions(path, require_gateway=False)
    assert "PIN Code" not in loaded
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the APIs and behavior are missing**

Run: `.venv/bin/python -m pytest tests/test_data_loader.py -q`

- [ ] **Step 3: Split raw/prepared validation and reject invalid categories, non-finite numerics, blank IDs, invalid booleans, timestamps, gateways, and simulation metadata**

```python
def validate_raw_transactions(frame: pd.DataFrame) -> None:
    _validate_common(frame)


def validate_prepared_transactions(frame: pd.DataFrame) -> None:
    _validate_common(frame)
    _validate_gateway_and_simulation_metadata(frame)
```

Use `np.isfinite()` for amount, latency, and bandwidth. Normalize accepted fraud values to pandas boolean only after validation. Drop `PIN Code` immediately after reading and before returning the frame.

- [ ] **Step 4: Write failing persistence and UI tests proving PINs cannot cross a boundary**

```python
def test_frame_to_documents_never_serializes_pin(sample_transactions):
    prepared = sample_transactions.drop(columns=["PIN Code"]).assign(
        **{"Bank Gateway": "Gateway A", "Simulation Version": "routing-v1"}
    )
    assert all("pin_code" not in row for row in frame_to_documents(prepared))


def test_public_projection_is_an_allowlist():
    assert PUBLIC_TRANSACTION_PROJECTION["transaction_id"] == 1
    assert "pin_code" not in PUBLIC_TRANSACTION_PROJECTION
    assert "sender_account_id" not in PUBLIC_TRANSACTION_PROJECTION
```

- [ ] **Step 5: Remove PIN mappings, serialization, form controls, fixtures, and broad Mongo transaction projection**

Implement the public projection as an explicit inclusion map and apply it in the paginated `$project` stage. Remove `pin_code` from audit sanitization because the field must no longer enter mutation payloads at all.

- [ ] **Step 6: Run all affected tests, then the full offline suite**

Run: `.venv/bin/python -m pytest tests/test_data_loader.py tests/test_load_mongodb.py tests/test_mongodb.py tests/test_mongodb_repository.py tests/test_transaction_service.py tests/test_admin_ui.py -q`

Run: `make test`

- [ ] **Step 7: Commit the independently testable data-safety change**

```bash
git add payment_dashboard tests
git commit -m "fix: remove sensitive fields and validate transaction data"
```

---

### Task 2: Add routing domain types and versioned gateway configuration

**Files:**
- Create: `payment_dashboard/routing_models.py`
- Create: `payment_dashboard/routing_config.py`
- Create: `tests/test_routing_models.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `GatewayProfile`, `ObjectiveWeights`, `RoutingBenchmark`, `AllocationResult`, `PolicyMetrics`, `OptimizationReport`
- Produces: `GATEWAY_PROFILES: tuple[GatewayProfile, ...]`
- Produces: `ROUTING_SIMULATION_VERSION: str`

- [ ] **Step 1: Write failing model-invariant tests**

```python
def test_objective_weights_reject_negative_values():
    with pytest.raises(ValueError, match="non-negative"):
        ObjectiveWeights(success_value=100, fee_weight=-1, latency_weight=0.01)


def test_gateway_profiles_have_unique_ids_and_tradeoffs():
    ids = [profile.gateway_id for profile in GATEWAY_PROFILES]
    assert ids == ["Gateway A", "Gateway B", "Gateway C", "Gateway D"]
    assert len({profile.fixed_fee for profile in GATEWAY_PROFILES}) > 1
    assert len({profile.base_latency_ms for profile in GATEWAY_PROFILES}) > 1
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_routing_models.py -q`

- [ ] **Step 3: Implement frozen dataclasses with constructor validation**

```python
@dataclass(frozen=True)
class ObjectiveWeights:
    success_value: float = 100.0
    fee_weight: float = 1.0
    latency_weight: float = 0.01


@dataclass(frozen=True)
class RoutingBenchmark:
    contexts: pd.DataFrame
    candidates: pd.DataFrame
    potential_outcomes: pd.DataFrame
    simulation_version: str
```

`AllocationResult` contains `policy_name`, `decisions`, `objective_value`, `is_feasible`, and `diagnostic`. `OptimizationReport` contains split boundaries, weights, policy metrics, decisions, comparison rows, and simulation version.

- [ ] **Step 4: Add bounded SciPy dependency and run model tests**

Add `scipy>=1.14,<2` to project and runtime requirements. Install through the editable development package, then run the focused tests.

Run: `.venv/bin/python -m pip install -e '.[dev]'`

Run: `.venv/bin/python -m pytest tests/test_routing_models.py -q`

- [ ] **Step 5: Commit the domain contract**

```bash
git add pyproject.toml requirements.txt payment_dashboard/routing_models.py payment_dashboard/routing_config.py tests/test_routing_models.py
git commit -m "feat: define payment routing domain model"
```

---

### Task 3: Generate deterministic candidate routes and hidden outcomes

**Files:**
- Create: `payment_dashboard/routing_simulation.py`
- Create: `tests/test_routing_simulation.py`

**Interfaces:**
- Consumes: `GatewayProfile`, `RoutingBenchmark`, `GATEWAY_PROFILES`
- Produces: `generate_routing_benchmark(contexts: pd.DataFrame, seed: int = 42) -> RoutingBenchmark`
- Produces: `validate_candidate_routes(candidates: pd.DataFrame) -> None`

- [ ] **Step 1: Write failing determinism, cardinality, separation, and non-dominance tests**

```python
def test_benchmark_has_four_candidates_per_transaction(sample_contexts):
    benchmark = generate_routing_benchmark(sample_contexts, seed=7)
    assert len(benchmark.candidates) == len(sample_contexts) * 4
    assert "potential_outcome" not in benchmark.candidates
    assert len(benchmark.potential_outcomes) == len(sample_contexts) * 4


def test_no_gateway_is_universally_best(sample_contexts):
    candidates = generate_routing_benchmark(sample_contexts, seed=7).candidates
    winners = candidates.loc[
        candidates.groupby("transaction_id")["expected_utility_hint"].idxmax(),
        "gateway_id",
    ]
    assert winners.nunique() >= 3
```

- [ ] **Step 2: Run tests and confirm missing simulation failure**

Run: `.venv/bin/python -m pytest tests/test_routing_simulation.py -q`

- [ ] **Step 3: Implement deterministic time-bucket state and four-way candidate expansion**

Compute `time_bucket` with UTC hourly flooring. Apply documented transaction/gateway interactions for amount, type, device, and hour. Calculate expected fee and latency, clamp probabilities, and generate deterministic availability, capacity, and incident states.

- [ ] **Step 4: Generate potential outcomes through a separate RNG stream and return them in a separate frame**

```python
outcomes = candidate_keys.assign(
    realized_success=outcome_rng.random(len(candidates))
    < candidates["expected_success_probability"].to_numpy()
)
public_candidates = candidates.drop(columns=["realized_success"])
```

- [ ] **Step 5: Add validation for exact candidate keys, finite values, probability bounds, nonnegative fees/latency/capacity, and simulation version**

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_routing_simulation.py -q`

```bash
git add payment_dashboard/routing_simulation.py tests/test_routing_simulation.py
git commit -m "feat: generate deterministic gateway candidates"
```

---

### Task 4: Implement capacity-aware baseline policies

**Files:**
- Create: `payment_dashboard/routing_policies.py`
- Create: `tests/test_routing_policies.py`

**Interfaces:**
- Produces: `route_random(candidates: pd.DataFrame, seed: int) -> AllocationResult`
- Produces: `route_round_robin(candidates: pd.DataFrame) -> AllocationResult`
- Produces: `route_best_static(candidates: pd.DataFrame, gateway_id: str) -> AllocationResult`
- Produces: `route_greedy_success(candidates: pd.DataFrame) -> AllocationResult`

- [ ] **Step 1: Write failing tests for one assignment, eligibility, capacity, deterministic routing, and infeasibility**

```python
@pytest.mark.parametrize("policy", [route_round_robin, route_greedy_success])
def test_policy_respects_capacity_and_eligibility(candidate_fixture, policy):
    result = policy(candidate_fixture)
    assert result.is_feasible
    assert result.decisions["transaction_id"].is_unique
    assert result.decisions["eligible"].all()
    usage = result.decisions.groupby(["time_bucket", "gateway_id"]).size()
    assert (usage <= result.decisions.groupby(["time_bucket", "gateway_id"])["capacity"].first()).all()
```

- [ ] **Step 2: Run tests and confirm missing-policy failure**

Run: `.venv/bin/python -m pytest tests/test_routing_policies.py -q`

- [ ] **Step 3: Implement one shared deterministic feasible allocator and the four ordering strategies**

The helper receives candidates in policy order, assigns only gateways with remaining capacity, and returns an explicit infeasible result when a transaction has no feasible candidate. Random routing uses a local seeded generator; it never mutates global RNG state.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_routing_policies.py -q`

```bash
git add payment_dashboard/routing_policies.py tests/test_routing_policies.py
git commit -m "feat: add constrained routing baselines"
```

---

### Task 5: Implement the MILP optimizer

**Files:**
- Create: `payment_dashboard/routing_optimizer.py`
- Create: `tests/test_routing_optimizer.py`

**Interfaces:**
- Consumes: `ObjectiveWeights`, `AllocationResult`
- Produces: `optimize_routes(candidates: pd.DataFrame, weights: ObjectiveWeights, fee_ceiling: float | None = None) -> AllocationResult`

- [ ] **Step 1: Write a failing known-optimum test**

```python
def test_optimizer_selects_known_global_optimum(known_optimum_candidates):
    result = optimize_routes(
        known_optimum_candidates,
        ObjectiveWeights(success_value=100, fee_weight=1, latency_weight=0),
    )
    assert result.is_feasible
    assert result.decisions.set_index("transaction_id")["gateway_id"].to_dict() == {
        "T1": "Gateway B",
        "T2": "Gateway A",
    }
```

- [ ] **Step 2: Write failing tests for capacity, eligibility, fee ceiling, deterministic ties, and explicit infeasibility**

- [ ] **Step 3: Run tests and confirm missing-optimizer failure**

Run: `.venv/bin/python -m pytest tests/test_routing_optimizer.py -q`

- [ ] **Step 4: Build a sparse MILP with one binary variable per candidate**

Construct a minimization vector from negative expected utility. Add one equality row per transaction, one upper-bound row per time-bucket/gateway capacity, and an optional fee row. Use bounds of zero for ineligible or unavailable candidates and `integrality=np.ones(candidate_count)`.

- [ ] **Step 5: Convert only successful solver output into decisions and classify infeasible versus solver failure**

Use stable candidate ordering by transaction ID and gateway ID before matrix construction. Select `x >= 0.5`, then revalidate all hard constraints independently of the solver result.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_routing_optimizer.py -q`

```bash
git add payment_dashboard/routing_optimizer.py tests/test_routing_optimizer.py
git commit -m "feat: optimize gateway allocation with milp"
```

---

### Task 6: Add chronological policy evaluation and uncertainty

**Files:**
- Create: `payment_dashboard/routing_evaluation.py`
- Create: `tests/test_routing_evaluation.py`

**Interfaces:**
- Produces: `chronological_split(contexts: pd.DataFrame) -> dict[str, pd.Index]`
- Produces: `evaluate_all_policies(benchmark: RoutingBenchmark, weights: ObjectiveWeights) -> OptimizationReport`
- Produces: `block_bootstrap_interval(decisions: pd.DataFrame, metric: str, seed: int = 42, samples: int = 1000) -> tuple[float, float]`

- [ ] **Step 1: Write failing tests for exact chronological boundaries and outcome isolation**

```python
def test_chronological_split_is_sixty_twenty_twenty(contexts):
    split = chronological_split(contexts)
    assert list(map(len, split.values())) == [6, 2, 2]
    assert contexts.loc[split["development"], "Timestamp"].max() < contexts.loc[split["validation"], "Timestamp"].min()


def test_policy_is_called_without_potential_outcomes(benchmark, spying_policy):
    evaluate_policy(benchmark, spying_policy)
    assert "realized_success" not in spying_policy.received_columns
```

- [ ] **Step 2: Run tests and confirm missing-evaluation failure**

Run: `.venv/bin/python -m pytest tests/test_routing_evaluation.py -q`

- [ ] **Step 3: Implement split, post-decision outcome join, metrics, policy comparison, and time-bucket bootstrap**

Metrics include realized success, expected/realized utility, total fee, cost per success, average/P95 latency, per-gateway utilization, hard-constraint violations, and degraded-period results.

- [ ] **Step 4: Add a test showing test outcomes cannot affect development or validation decisions**

- [ ] **Step 5: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_routing_evaluation.py -q`

```bash
git add payment_dashboard/routing_evaluation.py tests/test_routing_evaluation.py
git commit -m "feat: evaluate routing policies chronologically"
```

---

### Task 7: Correct monitoring baselines

**Files:**
- Modify: `payment_dashboard/alerting.py`
- Modify: `payment_dashboard/mongodb.py`
- Modify: `tests/test_alerting.py`
- Modify: `tests/test_mongodb_repository.py`

**Interfaces:**
- Produces: `evaluate_alerts(full_frame: pd.DataFrame, window_size: int = 50, minimum_baseline_size: int = 200, threshold: float = 0.10) -> pd.DataFrame`

- [ ] **Step 1: Replace full-history expectation tests with failing non-overlap and future-invariance tests**

```python
def test_recent_window_is_excluded_from_baseline(gateway_history):
    result = evaluate_alerts(gateway_history, window_size=50, minimum_baseline_size=200)
    row = result.set_index("Bank Gateway").loc["Gateway A"]
    assert row["baseline_count"] == len(gateway_history) - 50
    assert row["recent_count"] == 50


def test_future_rows_do_not_change_historical_alert(historical_frame, future_frame):
    before = evaluate_alerts(historical_frame)
    replayed = evaluate_alerts(pd.concat([historical_frame, future_frame]).iloc[: len(historical_frame)])
    pd.testing.assert_frame_equal(before, replayed)
```

- [ ] **Step 2: Run focused tests and confirm the existing overlapping baseline fails**

Run: `.venv/bin/python -m pytest tests/test_alerting.py -q`

- [ ] **Step 3: Implement sorted disjoint baseline/recent windows, minimum baseline size, counts, timestamps, and Wilson intervals**

- [ ] **Step 4: Update the Mongo aggregation pipeline to the same semantics and prove pandas/Mongo parity**

- [ ] **Step 5: Run focused and repository tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_alerting.py tests/test_mongodb_repository.py -q`

```bash
git add payment_dashboard/alerting.py payment_dashboard/mongodb.py tests/test_alerting.py tests/test_mongodb_repository.py
git commit -m "fix: remove look-ahead from gateway alerts"
```

---

### Task 8: Make mutations and audit events atomic

**Files:**
- Modify: `payment_dashboard/transaction_service.py`
- Modify: `payment_dashboard/ui/admin.py`
- Modify: `tests/test_transaction_service.py`
- Modify: `tests/test_admin_ui.py`

**Interfaces:**
- Produces: `AuthenticatedPrincipal(principal_id: str, display_name: str)`
- Changes: create/update/delete service functions require `principal` and accept a session-capable Mongo client

- [ ] **Step 1: Write a failing rollback test using a transaction-aware fake**

```python
def test_create_rolls_back_when_audit_insert_fails(values, transactional_database):
    transactional_database.audit.fail_insert = True
    with pytest.raises(TransactionMutationError):
        create_transaction(transactional_database, values, PRINCIPAL)
    assert transactional_database.transactions.document is None
```

- [ ] **Step 2: Run tests and confirm the current write-then-audit implementation leaves data changed**

Run: `.venv/bin/python -m pytest tests/test_transaction_service.py -q`

- [ ] **Step 3: Introduce the principal type and wrap mutation plus audit insertion in one Mongo session transaction**

Pass `session=session` to every `find_one`, `insert_one`, and `update_one` participating in the transaction. Audit snapshots use explicit safe-field allowlists.

- [ ] **Step 4: Update admin callers and label authentication as demo-only in both languages**

- [ ] **Step 5: Run affected tests and commit**

Run: `.venv/bin/python -m pytest tests/test_transaction_service.py tests/test_admin_ui.py tests/test_i18n.py -q`

```bash
git add payment_dashboard/transaction_service.py payment_dashboard/ui/admin.py tests/test_transaction_service.py tests/test_admin_ui.py tests/test_i18n.py
git commit -m "fix: make transaction audit writes atomic"
```

---

### Task 9: Add the optimization report service and dashboard

**Files:**
- Create: `payment_dashboard/routing_repository.py`
- Create: `payment_dashboard/ui/optimization.py`
- Create: `tests/test_routing_repository.py`
- Create: `tests/test_optimization_ui.py`
- Modify: `payment_dashboard/app.py`
- Modify: `payment_dashboard/i18n.py`
- Modify: `payment_dashboard/ui/style.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_i18n.py`
- Modify: `tests/test_style.py`

**Interfaces:**
- Produces: `PandasRoutingRepository.build_report(contexts: pd.DataFrame, weights: ObjectiveWeights) -> OptimizationReport`
- Produces: `render_optimization_report(report: OptimizationReport, language: Language) -> None`

- [ ] **Step 1: Write failing repository and UI contract tests**

```python
def test_repository_returns_all_policy_comparisons(contexts):
    report = PandasRoutingRepository().build_report(contexts, ObjectiveWeights())
    assert set(report.policy_metrics) == {
        "uniform_random", "round_robin", "best_static", "greedy_success", "milp_optimizer"
    }


def test_optimization_ui_discloses_synthetic_benchmark(app_test_report):
    render_optimization_report(app_test_report)
    assert "SYNTHETIC BENCHMARK" in rendered_text()
```

- [ ] **Step 2: Run focused tests and confirm missing service/UI failure**

Run: `.venv/bin/python -m pytest tests/test_routing_repository.py tests/test_optimization_ui.py -q`

- [ ] **Step 3: Implement a cached report service over prepared contexts with demo fallback**

The routing benchmark remains independent of the live Mongo dashboard repository. Cache keys include source checksum, simulation version, seed, and objective weights.

- [ ] **Step 4: Render policy KPIs, comparison table, allocation chart, capacity utilization, degraded-period comparison, chronological trend, constraints, and example decisions**

Never render unselected potential outcomes as real facts. Show split boundaries, objective weights, infeasible volume, simulation version, and the persistent synthetic label.

- [ ] **Step 5: Integrate the optimization section before secondary monitoring and add complete English/Myanmar labels**

- [ ] **Step 6: Run UI, app, translation, and style tests; commit**

Run: `.venv/bin/python -m pytest tests/test_routing_repository.py tests/test_optimization_ui.py tests/test_app.py tests/test_i18n.py tests/test_style.py -q`

```bash
git add payment_dashboard tests
git commit -m "feat: present constrained routing optimization"
```

---

### Task 10: Add provenance, reporting, and quality gates

**Files:**
- Create: `docs/data-card.md`
- Create: `data/source-manifest.json`
- Create: `payment_dashboard/analysis.py`
- Create: `tests/test_analysis.py`
- Create: `.github/workflows/ci.yml`
- Modify: `payment_dashboard/prepare_data.py`
- Modify: `README.md`
- Modify: `Makefile`
- Modify: `pyproject.toml`
- Delete: `setup.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `verify_source_manifest(path: Path, manifest_path: Path) -> None`
- Produces: `build_source_analysis(frame: pd.DataFrame) -> dict[str, pd.DataFrame | dict[str, float]]`
- Produces: Make targets `typecheck` and `check`

- [ ] **Step 1: Write failing manifest and source-analysis tests**

```python
def test_manifest_rejects_wrong_checksum(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("wrong", encoding="utf-8")
    with pytest.raises(DataValidationError, match="checksum"):
        verify_source_manifest(source, MANIFEST_PATH)


def test_source_analysis_uses_source_status(prepared_frame):
    report = build_source_analysis(prepared_frame)
    assert report["outcomes"]["status_column"] == "Source Transaction Status"
```

- [ ] **Step 2: Implement provenance verification and pure descriptive analysis without causal language**

The data card records the exact Kaggle URL, CC0 license, current source schema, synthetic additions, removal of PIN data, and limitations. The manifest uses the actual source checksum when the file is present; preparation emits a clear instruction if the local file does not match.

- [ ] **Step 3: Fix strict mypy errors and add `typecheck` and aggregate `check` Make targets**

```make
typecheck:
	$(PYTHON) -m mypy payment_dashboard

check: lint typecheck test
```

- [ ] **Step 4: Remove redundant packaging metadata and tracked `.DS_Store` files, then add clean CI**

CI installs `.[dev]` and runs Ruff check, Ruff format check, mypy, offline pytest, package build, and clean-checkout verification. It does not run Atlas, AI-provider, or deployed browser checks.

- [ ] **Step 5: Rewrite README around the synthetic routing objective, constraints, dataset provenance, evaluation split, baselines, metrics, limitations, and commands**

- [ ] **Step 6: Run every quality gate and commit**

Run: `make lint`

Run: `.venv/bin/ruff format --check payment_dashboard tests scripts`

Run: `make typecheck`

Run: `make test`

Run: `.venv/bin/python -m build`

Run: `make verify-clean`

```bash
git add .github .gitignore Makefile README.md data/source-manifest.json docs/data-card.md payment_dashboard tests pyproject.toml requirements.txt
git rm setup.py
git rm --cached .DS_Store docs/.DS_Store docs/superpowers/.DS_Store
git commit -m "chore: document and verify routing benchmark"
```

---

### Task 11: Final requirement and regression verification

**Files:**
- Review: `docs/superpowers/specs/2026-08-12-payment-routing-optimization-design.md`
- Review: all files changed by Tasks 1-10

**Interfaces:**
- Consumes all preceding interfaces.
- Produces a verified branch with no unaddressed acceptance-criteria gaps.

- [ ] **Step 1: Run the complete offline verification from the branch root**

```bash
make lint
.venv/bin/ruff format --check payment_dashboard tests scripts
make typecheck
make test
.venv/bin/python -m build
make verify-clean
```

- [ ] **Step 2: Verify sensitive-field absence**

Run: `rg -n "PIN Code|pin_code" payment_dashboard tests docs README.md`

Expected: only an explicit prohibited-field assertion or data-card explanation; no schema, payload, database mapping, form, prompt, or fixture value.

- [ ] **Step 3: Verify the spec acceptance criteria line by line against tests and implementation**

Confirm candidate cardinality, non-dominance, hard constraints, hidden outcomes, chronological evaluation, four baselines, monitoring non-overlap, disclosure, and quality gates using fresh command output.

- [ ] **Step 4: Inspect the final diff for unrelated user changes or generated data**

Run: `git status --short`

Run: `git diff --stat main...HEAD`

Run: `git diff --check main...HEAD`

- [ ] **Step 5: Commit any verification-only corrections through their own red-green cycle, then invoke the finishing-a-development-branch workflow**

No completion claim is allowed without fresh evidence from all Step 1 commands.
