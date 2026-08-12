# Analysis Validity Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the synthetic payment-routing benchmark internally valid, auditable, statistically honest, and consistent across pandas, MongoDB, and Streamlit.

**Architecture:** Treat complete UTC time buckets as the indivisible unit for chronological splitting, capacity enforcement, incidents, and bootstrap resampling. Separate public route candidates from hidden potential outcomes with validated immutable contracts, evaluate every policy bucket-by-bucket, and persist a content-addressed benchmark run before rendering it. Keep operational alerting independent, but require pandas and MongoDB to implement the same reference-window contract.

**Tech Stack:** Python 3.11+, pandas 2.2, NumPy 2.1, SciPy `milp`, PyMongo 4.10, Streamlit 1.40, pytest, Ruff, strict mypy.

## Global Constraints

- Gateway results remain explicitly synthetic and must never be described as measurements of real processors.
- Each transaction has four versioned candidate routes before eligibility filtering.
- Policies cannot access `realized_success` until after their decisions are finalized.
- Development, validation, and test sets must contain disjoint complete UTC hourly buckets.
- Every policy uses identical candidates, capacities, eligibility, and hidden outcomes.
- Infeasible buckets are reported; they must not be converted into fabricated allocations or application crashes.
- Monitoring uses 50 recent attempts and at least 200 earlier reference attempts per gateway.
- The raw PIN field never enters prepared files, databases, audits, forms, prompts, or rendered output.
- All normal tests remain offline; Atlas and browser checks stay explicitly opt-in.

---

## Phase 0: Preserve and measure the current submission

### Task 1: Establish regression fixtures and a benchmark acceptance table

**Files:**
- Create: `tests/fixtures/routing_hourly_contexts.csv`
- Create: `tests/test_routing_acceptance.py`
- Modify: `docs/data-card.md`

**Interfaces:**
- Consumes: existing `generate_routing_benchmark()` and `evaluate_all_policies()`.
- Produces: a deterministic multi-hour fixture and acceptance tests reused by later tasks.

- [ ] **Step 1: Create a six-hour fixture whose bucket loads exercise capacity**

  Include at least one feasible hour, one hour where one gateway saturates, and one hour where total eligible capacity is insufficient. Use stable IDs such as `H00-T0001` and timestamps exactly on or within UTC hours.

- [ ] **Step 2: Write failing acceptance tests**

```python
def test_split_never_divides_an_hourly_bucket(hourly_contexts):
    split = chronological_bucket_split(hourly_contexts)
    bucket_sets = {
        name: set(hourly_contexts.loc[index, "Timestamp"].dt.floor("h"))
        for name, index in split.items()
    }
    assert bucket_sets["development"].isdisjoint(bucket_sets["validation"])
    assert bucket_sets["validation"].isdisjoint(bucket_sets["test"])


def test_acceptance_fixture_contains_binding_and_infeasible_buckets(hourly_contexts):
    report = build_report(hourly_contexts)
    assert report.capacity_binding_bucket_count >= 1
    assert report.infeasible_bucket_count >= 1
```

- [ ] **Step 3: Run the tests and record the expected failures**

  Run: `.venv/bin/pytest tests/test_routing_acceptance.py -q`

  Expected: failure because bucket-aware splitting and report diagnostics do not yet exist.

- [ ] **Step 4: Add an explicit acceptance table to the data card**

  State the required evidence: disjoint full buckets, at least one binding capacity, explicit infeasibility, MILP improvement over at least one feasible baseline for expected utility, and uncertainty intervals for realized comparisons.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/routing_hourly_contexts.csv tests/test_routing_acceptance.py docs/data-card.md
git commit -m "test: define routing benchmark acceptance fixture"
```

---

## Phase 1: Repair analytical validity

### Task 2: Split complete chronological buckets

**Files:**
- Modify: `payment_dashboard/routing_evaluation.py`
- Modify: `payment_dashboard/routing_models.py`
- Test: `tests/test_routing_optimization.py`
- Test: `tests/test_routing_acceptance.py`

**Interfaces:**
- Produces: `chronological_bucket_split(contexts: pd.DataFrame, frequency: str = "h") -> ChronologicalSplit`.
- `ChronologicalSplit` contains development, validation, and test transaction-ID tuples plus timestamp boundaries and row counts.

- [ ] **Step 1: Test that tied hours cannot cross split boundaries**

```python
def test_chronological_split_keeps_complete_hours_together(contexts):
    split = chronological_bucket_split(contexts)
    memberships = {
        transaction_id: period
        for period, ids in split.transaction_ids_by_period().items()
        for transaction_id in ids
    }
    for _, rows in contexts.groupby(contexts["Timestamp"].dt.floor("h")):
        assert len({memberships[value] for value in rows["Transaction ID"]}) == 1
```

- [ ] **Step 2: Implement a bucket-boundary split**

  Sort unique UTC buckets, assign the earliest approximately 60% to development, the next approximately 20% to validation, and the remainder to test. Never slice rows directly. Reject datasets with fewer than three distinct buckets.

- [ ] **Step 3: Replace every positional `.iloc` split consumer**

  Filter candidates and outcomes by transaction IDs from `ChronologicalSplit`. Report actual row counts and timestamp boundaries; do not claim exact 60/20/20 row ratios when bucket preservation changes them.

- [ ] **Step 4: Run focused tests**

  Run: `.venv/bin/pytest tests/test_routing_optimization.py tests/test_routing_acceptance.py -q`

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/routing_evaluation.py payment_dashboard/routing_models.py tests/test_routing_optimization.py tests/test_routing_acceptance.py
git commit -m "fix: split routing evaluation by complete time buckets"
```

### Task 3: Make gateway state stable by time bucket

**Files:**
- Modify: `payment_dashboard/routing_config.py`
- Modify: `payment_dashboard/routing_simulation.py`
- Test: `tests/test_routing_optimization.py`

**Interfaces:**
- Produces: `gateway_state(bucket: pd.Timestamp, gateway_id: str) -> GatewayState`.
- `GatewayState` contains `available`, `capacity`, `success_adjustment`, `latency_multiplier`, and `state_version`.

- [ ] **Step 1: Write invariance tests**

```python
def test_gateway_state_is_constant_within_bucket(contexts):
    benchmark = generate_routing_benchmark(contexts)
    grouped = benchmark.candidates.groupby(["time_bucket", "gateway_id"])
    for _, rows in grouped:
        assert rows["available"].nunique() == 1
        assert rows["capacity"].nunique() == 1
        assert rows["state_version"].nunique() == 1


def test_inserting_an_earlier_transaction_does_not_shift_later_incidents(contexts):
    before = generate_routing_benchmark(contexts).candidates
    after = generate_routing_benchmark(add_earlier_context(contexts)).candidates
    assert_state_columns_equal_for_shared_keys(before, after)
```

- [ ] **Step 2: Replace `position % 24` incidents**

  Derive incidents from an explicit versioned schedule keyed by UTC bucket and gateway. Keep the schedule in `routing_config.py`; do not derive state from row order.

- [ ] **Step 3: Validate candidate invariants before returning**

  Require exactly four unique `(transaction_id, gateway_id)` rows per transaction, one constant state per `(time_bucket, gateway_id)`, finite non-negative fees/latencies, probabilities in `[0, 1]`, positive integer capacities, and one simulation/state version.

- [ ] **Step 4: Run focused tests and lint**

  Run: `.venv/bin/pytest tests/test_routing_optimization.py -q && make lint`

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/routing_config.py payment_dashboard/routing_simulation.py tests/test_routing_optimization.py
git commit -m "fix: model gateway incidents as stable bucket state"
```

### Task 4: Enforce hidden-outcome and period contracts

**Files:**
- Modify: `payment_dashboard/routing_models.py`
- Modify: `payment_dashboard/routing_simulation.py`
- Modify: `payment_dashboard/routing_evaluation.py`
- Test: `tests/test_routing_optimization.py`

**Interfaces:**
- Produces: validated `CandidateRoutes` and `PotentialOutcomes` wrappers.
- Produces: `join_selected_outcomes(decisions, outcomes, allowed_transaction_ids)`.

- [ ] **Step 1: Write tests for malformed and leaking inputs**

```python
def test_policy_candidates_reject_realized_outcome_column(candidates):
    with pytest.raises(EvaluationLeakageError):
        CandidateRoutes(candidates.assign(realized_success=True))


def test_evaluation_rejects_outcomes_outside_test_period(benchmark, split):
    with pytest.raises(EvaluationLeakageError):
        join_selected_outcomes(decisions, benchmark.potential_outcomes, split.test_ids)
```

- [ ] **Step 2: Introduce narrow wrapper types**

  Copy input frames on construction, validate required/forbidden columns and unique keys, and expose copies to callers. Policies receive only `CandidateRoutes`; only evaluation receives `PotentialOutcomes`.

- [ ] **Step 3: Restrict outcome joins**

  Before merging, verify that decision transaction IDs equal the evaluable assigned IDs, are a subset of test IDs, and have unique `(transaction_id, gateway_id)` keys. Filter outcomes to the allowed test IDs before joining.

- [ ] **Step 4: Run tests and type checking**

  Run: `.venv/bin/pytest tests/test_routing_optimization.py -q && make typecheck`

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/routing_models.py payment_dashboard/routing_simulation.py payment_dashboard/routing_evaluation.py tests/test_routing_optimization.py
git commit -m "fix: enforce routing outcome leakage boundaries"
```

### Task 5: Evaluate policies independently per bucket

**Files:**
- Modify: `payment_dashboard/routing_models.py`
- Modify: `payment_dashboard/routing_optimizer.py`
- Modify: `payment_dashboard/routing_policies.py`
- Modify: `payment_dashboard/routing_evaluation.py`
- Test: `tests/test_routing_optimization.py`
- Test: `tests/test_routing_acceptance.py`

**Interfaces:**
- Produces: `BucketAllocationResult` with bucket, decisions, feasibility, unassigned IDs, binding constraints, and diagnostic.
- Produces: `PolicyAllocationResult` containing all bucket results without throwing away successful buckets.

- [ ] **Step 1: Write known-optimum, fee-scope, and infeasibility tests**

```python
def test_fee_ceiling_is_enforced_per_bucket(two_bucket_candidates):
    result = optimize_routes(two_bucket_candidates, weights, fee_ceiling=10.0)
    for bucket in result.feasible_buckets:
        assert bucket.decisions["expected_fee"].sum() <= 10.0


def test_infeasible_bucket_does_not_discard_feasible_bucket(mixed_candidates):
    result = optimize_routes(mixed_candidates, weights)
    assert result.bucket("2025-01-01T10:00Z").is_feasible
    assert not result.bucket("2025-01-01T11:00Z").is_feasible
    assert result.unassigned_count > 0
```

- [ ] **Step 2: Move MILP construction inside a bucket loop**

  Build assignment, capacity, and optional fee constraints separately for each bucket. Use gateway-ID ordering for deterministic tie-breaking. Distinguish invalid input, infeasible allocation, and solver failure.

- [ ] **Step 3: Give all baselines the same bucket contract**

  Random, round-robin, best-static, and greedy policies must receive the same bucket candidates and return the same result type. Preserve feasible buckets when a later bucket is infeasible.

- [ ] **Step 4: Stop raising on expected infeasibility**

  Evaluation should aggregate successful decisions and explicit unassigned volume. Raise only for invalid contracts or solver failures, not for a legitimately infeasible bucket.

- [ ] **Step 5: Prove the fixture contains meaningful optimization**

  Assert that capacity binds and that MILP expected utility is strictly greater than at least one feasible baseline. Do not require realized success to be greater in a single random draw.

- [ ] **Step 6: Run focused tests**

  Run: `.venv/bin/pytest tests/test_routing_optimization.py tests/test_routing_acceptance.py -q`

- [ ] **Step 7: Commit**

```bash
git add payment_dashboard/routing_models.py payment_dashboard/routing_optimizer.py payment_dashboard/routing_policies.py payment_dashboard/routing_evaluation.py tests/test_routing_optimization.py tests/test_routing_acceptance.py
git commit -m "fix: evaluate routing policies per constrained bucket"
```

### Task 6: Use validation for declared weight selection

**Files:**
- Modify: `payment_dashboard/routing_config.py`
- Modify: `payment_dashboard/routing_evaluation.py`
- Modify: `payment_dashboard/routing_models.py`
- Test: `tests/test_routing_optimization.py`

**Interfaces:**
- Produces: `select_objective_weights(validation_candidates, grid) -> WeightSelection`.
- `WeightSelection` records the predeclared grid, validation scores, deterministic tie-break rule, and selected weights.

- [ ] **Step 1: Define a small fixed grid in configuration**

  Keep success value fixed and predeclare a small set of fee and latency weights. Do not generate candidates after seeing test results.

- [ ] **Step 2: Write a test proving test outcomes cannot change selected weights**

```python
def test_weight_selection_is_independent_of_test_outcomes(benchmark):
    first = evaluate_all_policies(benchmark, weight_grid=DEFAULT_WEIGHT_GRID)
    mutated = replace_test_outcomes_only(benchmark)
    second = evaluate_all_policies(mutated, weight_grid=DEFAULT_WEIGHT_GRID)
    assert first.weight_selection.selected == second.weight_selection.selected
```

- [ ] **Step 3: Select weights using validation candidates and expected utility**

  Use no realized test outcomes. Resolve equal validation scores using the declared grid order and record the complete selection table in the report.

- [ ] **Step 4: Run tests**

  Run: `.venv/bin/pytest tests/test_routing_optimization.py -q`

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/routing_config.py payment_dashboard/routing_evaluation.py payment_dashboard/routing_models.py tests/test_routing_optimization.py
git commit -m "feat: select routing weights on validation buckets"
```

### Task 7: Add complete metrics and bucket-bootstrap uncertainty

**Files:**
- Modify: `payment_dashboard/routing_models.py`
- Modify: `payment_dashboard/routing_evaluation.py`
- Create: `payment_dashboard/routing_statistics.py`
- Test: `tests/test_routing_statistics.py`
- Test: `tests/test_routing_acceptance.py`

**Interfaces:**
- Produces: `block_bootstrap_policy_difference(evaluated, baseline, metric, seed, samples=2000) -> ConfidenceInterval`.
- Expands `PolicyMetrics` with realized utility, utilization, violations, infeasible/unassigned counts, degraded/normal metrics, and denominators.

- [ ] **Step 1: Write deterministic statistical tests**

  Test a constant difference whose 95% interval must collapse to that constant, deterministic output for a fixed seed, and resampling of whole `time_bucket` groups rather than rows.

- [ ] **Step 2: Implement realized utility**

```python
realized_utility = (
    weights.success_value * evaluated["realized_success"].astype(float)
    - weights.fee_weight * evaluated["expected_fee"]
    - weights.latency_weight * evaluated["expected_latency_ms"]
)
```

- [ ] **Step 3: Implement full policy diagnostics**

  Include assigned and unassigned denominators, success count/rate, expected and realized utility, total fee, cost per success represented as `None` when there are zero successes, mean/P95 latency, gateway utilization, capacity/availability/eligibility violations, feasible/infeasible buckets, and normal/degraded results.

- [ ] **Step 4: Bootstrap differences against every baseline**

  Resample test-period buckets with replacement using a fixed reporting seed. Report absolute difference, relative difference only when the baseline denominator is nonzero, and percentile 95% intervals. Label the result “uncertain” whenever the interval contains zero.

- [ ] **Step 5: Run tests**

  Run: `.venv/bin/pytest tests/test_routing_statistics.py tests/test_routing_acceptance.py -q`

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/routing_models.py payment_dashboard/routing_evaluation.py payment_dashboard/routing_statistics.py tests/test_routing_statistics.py tests/test_routing_acceptance.py
git commit -m "feat: report routing diagnostics and uncertainty"
```

---

## Phase 2: Repair data management and operational consistency

### Task 8: Persist content-addressed benchmark runs

**Files:**
- Create: `payment_dashboard/routing_run_store.py`
- Modify: `payment_dashboard/routing_repository.py`
- Modify: `payment_dashboard/app.py`
- Test: `tests/test_routing_run_store.py`
- Test: `tests/test_optimization_ui.py`

**Interfaces:**
- Produces: `BenchmarkRunManifest` containing run ID, source digest, configuration digest, simulation/state versions, seed, split boundaries, selected weights, timestamps, and artifact digests.
- Produces: `RoutingRunStore.save(run) -> BenchmarkRunManifest` and `load(run_id) -> PersistedBenchmarkRun`.

- [ ] **Step 1: Write round-trip and tamper-detection tests**

  Save contexts, candidates, hidden outcomes, decisions, comparison metrics, and manifest into a temporary run directory. Assert round-trip equality and rejection when any artifact digest changes.

- [ ] **Step 2: Define canonical digests**

  Sort each frame by stable keys, serialize with explicit column order and timestamp format, hash the bytes with SHA-256, and derive `run_id` from source/configuration/seed digests.

- [ ] **Step 3: Separate sensitive outcome storage**

  Store public candidates and hidden outcomes as separate artifacts. The dashboard repository may read the evaluated report but must never expose unselected potential outcomes.

- [ ] **Step 4: Make the UI use one explicit source snapshot**

  If the displayed dashboard source is MongoDB, either build the optimization from the same safely projected snapshot or label and identify the independent benchmark run prominently. Remove the current silent local/live mismatch.

- [ ] **Step 5: Run tests**

  Run: `.venv/bin/pytest tests/test_routing_run_store.py tests/test_optimization_ui.py -q`

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/routing_run_store.py payment_dashboard/routing_repository.py payment_dashboard/app.py tests/test_routing_run_store.py tests/test_optimization_ui.py
git commit -m "feat: persist auditable routing benchmark runs"
```

### Task 9: Make pandas and MongoDB alerts identical

**Files:**
- Modify: `payment_dashboard/config.py`
- Modify: `payment_dashboard/alerting.py`
- Modify: `payment_dashboard/mongodb.py`
- Test: `tests/test_alerting.py`
- Test: `tests/test_mongodb_repository.py`

**Interfaces:**
- Uses: `ALERT_WINDOW_SIZE = 50`.
- Produces: `ALERT_BASELINE_MIN_SIZE = 200` and identical alert fields from both backends.

- [ ] **Step 1: Add parity fixtures**

  Cover 249 rows as insufficient, 250 as sufficient, tied timestamps resolved by transaction ID, exactly a ten-point drop, and a recent window whose inclusion would change the alert result.

- [ ] **Step 2: Correct pandas sufficiency**

```python
sufficient = (
    len(recent) == ALERT_WINDOW_SIZE
    and len(baseline_rows) >= ALERT_BASELINE_MIN_SIZE
)
```

- [ ] **Step 3: Correct MongoDB baseline construction**

  Sort by timestamp and transaction ID, retain the latest 50 separately, and calculate baseline count/successes only from earlier documents. Project baseline/recent counts and boundaries as well as rates.

- [ ] **Step 4: Add backend parity assertions**

  Feed identical documents to the pandas function and an aggregation-pipeline evaluator; compare every output field, including insufficient-history behavior.

- [ ] **Step 5: Run tests**

  Run: `.venv/bin/pytest tests/test_alerting.py tests/test_mongodb_repository.py -q`

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/config.py payment_dashboard/alerting.py payment_dashboard/mongodb.py tests/test_alerting.py tests/test_mongodb_repository.py
git commit -m "fix: align leakage-free alert calculations"
```

### Task 10: Replace forgeable audit actors with principals

**Files:**
- Modify: `payment_dashboard/admin_auth.py`
- Modify: `payment_dashboard/transaction_service.py`
- Modify: `payment_dashboard/ui/admin.py`
- Test: `tests/test_admin_auth.py`
- Test: `tests/test_transaction_service.py`

**Interfaces:**
- Produces: immutable `AuthenticatedPrincipal(subject: str, role: str, authenticated_at: datetime)`.
- Mutation functions require `principal: AuthenticatedPrincipal`; remove public `actor: str` parameters.

- [ ] **Step 1: Test rejection of strings and expired sessions**

  Verify mutation APIs cannot accept an arbitrary actor string, audit records use `principal.subject`, and admin sessions expire after a documented short demo duration.

- [ ] **Step 2: Return a principal from successful authentication**

  Store only a principal and authentication expiry in session state. Invalidate both when the password-hash fingerprint changes or the expiry passes.

- [ ] **Step 3: Pass principals through every mutation**

  Keep mutation and sanitized audit writes in the existing MongoDB transaction. Record subject and role, never the password or hash.

- [ ] **Step 4: Add bounded login throttling**

  Track failed attempts and a short cooldown in Streamlit session state, clearly retaining the documentation that this remains demo-only authentication.

- [ ] **Step 5: Run tests**

  Run: `.venv/bin/pytest tests/test_admin_auth.py tests/test_transaction_service.py tests/test_admin_ui.py -q`

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/admin_auth.py payment_dashboard/transaction_service.py payment_dashboard/ui/admin.py tests/test_admin_auth.py tests/test_transaction_service.py tests/test_admin_ui.py
git commit -m "fix: bind transaction audits to authenticated principals"
```

---

## Phase 3: Make the evidence visible and reproducible

### Task 11: Render the complete benchmark evidence

**Files:**
- Modify: `payment_dashboard/ui/optimization.py`
- Modify: `payment_dashboard/app.py`
- Test: `tests/test_optimization_ui.py`
- Modify: `scripts/smoke_dashboard.py`

**Interfaces:**
- Consumes: expanded `OptimizationReport` and `BenchmarkRunManifest`.

- [ ] **Step 1: Add UI contract tests**

  Require visible source/run ID, split boundaries and sample sizes, selected weights and validation evidence, constraints, infeasible/unassigned counts, policy metrics, confidence intervals, utilization, normal/degraded results, and uncertainty wording.

- [ ] **Step 2: Replace the headline comparison**

  Do not headline optimizer versus random realized success without uncertainty. Lead with expected-utility objective results and show realized differences with their bucket-bootstrap interval and “uncertain” label when appropriate.

- [ ] **Step 3: Add diagnostic sections**

  Render gateway assignment/utilization, binding constraints, infeasible buckets, degraded-period performance, cumulative utility, and representative selected decisions with eligible alternatives. Never render unselected realized outcomes.

- [ ] **Step 4: Extend browser smoke assertions**

  Require the synthetic label, run ID, test-period boundaries, uncertainty label, and infeasibility count.

- [ ] **Step 5: Run tests**

  Run: `.venv/bin/pytest tests/test_optimization_ui.py tests/test_smoke_dashboard.py -q`

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/ui/optimization.py payment_dashboard/app.py tests/test_optimization_ui.py scripts/smoke_dashboard.py
git commit -m "feat: expose complete routing benchmark evidence"
```

### Task 12: Make builds and clean verification reproducible

**Files:**
- Modify: `pyproject.toml`
- Delete: `requirements.txt`
- Modify: `scripts/verify_clean_checkout.sh`
- Create: `.github/workflows/quality.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: one dependency source plus a committed lock/constraints artifact generated by the selected locking tool.

- [ ] **Step 1: Choose one dependency authority**

  Keep project and development dependencies in `pyproject.toml`; remove the conflicting hand-maintained `requirements.txt`. Generate and commit a reproducible lock using a Python 3.11-compatible locking tool, including hashes where supported.

- [ ] **Step 2: Make clean verification accept the tree being tested**

  The script must refuse a dirty tree by default, or explicitly accept a source archive path. It must print and verify the commit SHA/run source so it cannot silently test `HEAD` while the user expects uncommitted code.

- [ ] **Step 3: Add CI for every offline gate**

```yaml
- run: make setup
- run: make lint
- run: .venv/bin/ruff format --check payment_dashboard tests scripts
- run: make typecheck
- run: make test
- run: .venv/bin/python -m build
- run: make verify-clean
```

- [ ] **Step 4: Correct README claims**

  Document bucket-preserving split ratios, weight selection, persisted run artifacts, uncertainty interpretation, and the fact that optimization results apply only to the named synthetic run.

- [ ] **Step 5: Run the full release gate**

  Run: `make lint && .venv/bin/ruff format --check payment_dashboard tests scripts && make typecheck && make test && .venv/bin/python -m build && make verify-clean`

  Expected: all commands exit zero; only explicitly gated live tests may be skipped.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml scripts/verify_clean_checkout.sh .github/workflows/quality.yml README.md
git rm requirements.txt
git commit -m "chore: make routing benchmark builds reproducible"
```

---

## Final judge's acceptance run

- [ ] Verify no hourly bucket appears in more than one chronological period.
- [ ] Verify at least one test bucket has a binding capacity constraint.
- [ ] Verify infeasible buckets are reported without discarding feasible results.
- [ ] Verify the per-bucket fee ceiling with a two-bucket counterexample.
- [ ] Verify validation, but not test outcomes, selects objective weights.
- [ ] Verify every policy sees identical candidate keys and capacities.
- [ ] Verify unselected potential outcomes never enter policy or UI objects.
- [ ] Verify optimizer expected utility beats at least one meaningful baseline on the acceptance fixture.
- [ ] Verify realized comparisons include bucket-bootstrap intervals and honest uncertainty language.
- [ ] Verify pandas and MongoDB alert outputs are identical on the same history.
- [ ] Verify every displayed report identifies its exact source/configuration/run digests.
- [ ] Verify the complete clean-checkout quality gate runs against the commit being judged.

Only after all twelve checks pass should the project claim to be a defensible synthetic routing-optimization benchmark.
