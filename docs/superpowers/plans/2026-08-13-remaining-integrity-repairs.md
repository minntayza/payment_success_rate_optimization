# Remaining Integrity Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the remaining security, validation, analytical-evidence, lineage, persistence, and repository-readiness findings from the second judge review.

**Architecture:** Preserve the existing routing module boundaries. Extend gateway configuration with explicit operational states, centralize audit sanitization, strengthen typed benchmark validation, enrich the shared alert contract, rerun policies for probability stress, and minimize persisted contexts at the repository boundary.

**Tech Stack:** Python 3.11+, pandas, NumPy, SciPy MILP, PyMongo, Streamlit, pytest, Ruff, mypy.

## Global Constraints

- Preserve all pre-existing uncommitted work and incidental `.DS_Store` changes.
- Use red-green TDD for every behavioral repair.
- Keep the standard test suite offline.
- Never persist PINs or unnecessary account identifiers.
- Keep all claims explicitly limited to the synthetic benchmark.
- Runtime and documentation must identify `routing-benchmark-v4` consistently.

---

### Task 1: Import audit safety and schema parity

**Files:**
- Modify: `tests/test_load_mongodb.py`
- Modify: `tests/test_transaction_service.py`
- Modify: `payment_dashboard/load_mongodb.py`
- Modify: `payment_dashboard/transaction_service.py`

**Interfaces:**
- Produces: `sanitize_audit_document(document: Mapping[str, object] | None) -> dict[str, object] | None`
- Import audit events use `changed_at` and the same snapshot sanitizer as CRUD events.

- [ ] Add a failing import test with legacy `pin_code`, sender, and receiver fields and assert none enter audit snapshots.
- [ ] Add a failing test asserting import and CRUD events both use `changed_at`, never `timestamp`.
- [ ] Run the focused tests and verify the expected failures.
- [ ] Add the shared sanitizer and a reconciliation-safe existing-document projection.
- [ ] Apply the shared audit schema to importer events.
- [ ] Run importer and transaction-service tests.

### Task 2: Reject non-finite routing inputs

**Files:**
- Modify: `tests/test_routing_optimization.py`
- Modify: `payment_dashboard/routing_models.py`

**Interfaces:** `RoutingBenchmark.__post_init__` rejects invalid numeric and boolean candidate values before allocation.

- [ ] Add parameterized failing tests for NaN/infinite probability, fee, latency, and capacity.
- [ ] Add failing tests for fractional/non-positive capacity and nullable/non-boolean flags.
- [ ] Run the focused tests and verify validation currently accepts the corrupt values.
- [ ] Implement finite, range, integer, and boolean validation with field-specific errors.
- [ ] Run all routing model/optimizer tests.

### Task 3: Three-state gateway operations

**Files:**
- Modify: `tests/test_routing_acceptance.py`
- Modify: `tests/test_routing_optimization.py`
- Modify: `payment_dashboard/routing_config.py`
- Modify: `payment_dashboard/routing_simulation.py`
- Modify: `payment_dashboard/routing_models.py`
- Modify: `payment_dashboard/routing_evaluation.py`

**Interfaces:**
- `GatewayState.operational_state` is `normal`, `degraded`, or `unavailable`.
- Degraded rows remain available with reduced capacity/probability and higher latency.
- Unavailable rows have `available=False` and zero effective capacity.

- [ ] Add failing tests for routable degraded state and prohibited unavailable state.
- [ ] Add a failing built-in-report assertion requiring non-empty degraded evidence.
- [ ] Run tests and confirm the current binary state fails.
- [ ] Implement disjoint degraded/unavailable schedules and state effects.
- [ ] Carry `operational_state` into candidates and compute degraded metrics from selected routes.
- [ ] Run routing acceptance and evaluation tests.

### Task 4: Complete alert evidence contract

**Files:**
- Modify: `tests/test_alerting.py`
- Modify: `tests/test_mongodb_repository.py`
- Modify: `tests/test_charts.py`
- Modify: `payment_dashboard/alerting.py`
- Modify: `payment_dashboard/mongodb.py`
- Modify: `payment_dashboard/ui/sections.py`

**Interfaces:** Pandas and MongoDB alert records expose counts, four UTC boundaries, two rates, drop, 95% difference interval, sufficiency, and alert status.

- [ ] Add failing pandas tests for boundaries, interval values, and uncertain-drop suppression.
- [ ] Add failing Mongo contract/parity tests for the new fields.
- [ ] Add a failing UI test proving counts, periods, and interval are visible.
- [ ] Implement a shared independent-proportions interval helper and enriched pandas records.
- [ ] Extend the Mongo aggregation and frame contract with equivalent calculations.
- [ ] Render the complete evidence table.
- [ ] Run alert, Mongo, and chart tests.

### Task 5: Genuine probability rerouting sensitivity

**Files:**
- Modify: `tests/test_routing_statistics.py`
- Modify: `tests/test_routing_optimization.py`
- Modify: `tests/test_optimization_ui.py`
- Modify: `payment_dashboard/routing_repository.py`
- Modify: `payment_dashboard/ui/optimization.py`
- Modify: `payment_dashboard/i18n.py`

**Interfaces:** Sensitivity rows include `scenario_type`, policy utilities, advantage, and changed-route counts; probability scenarios rerun greedy and MILP on shifted test candidates.

- [ ] Add a failing fixture where a probability shift changes at least one allocation.
- [ ] Add a failing test that probability scenarios call routing again and report changed routes.
- [ ] Add a failing UI assertion separating allocation and outcome sensitivity.
- [ ] Refactor sensitivity construction to accept test candidates and rerun both policies.
- [ ] Retain fixed-decision outcome-seed evaluation as a separately labeled scenario.
- [ ] Update localized copy and run sensitivity/UI tests.

### Task 6: Enforce one simulation lineage

**Files:**
- Modify: `tests/test_data_loader.py`
- Modify: `tests/test_mongodb_repository.py`
- Modify: `payment_dashboard/data_loader.py`
- Modify: `payment_dashboard/mongodb.py`

**Interfaces:** Every populated validated dataset contains exactly one nonblank `Simulation Version`; mixed versions raise `DataValidationError`.

- [ ] Add failing prepared-data and Mongo-frame tests containing two valid but different versions.
- [ ] Run them and verify mixed lineage is currently accepted.
- [ ] Enforce a single version in the shared validation boundary.
- [ ] Remove first-row-only metadata assumptions where necessary.
- [ ] Run loader and Mongo repository tests.

### Task 7: Minimize persisted contexts and complete manifests

**Files:**
- Modify: `tests/test_routing_run_store.py`
- Modify: `tests/test_routing_optimization.py`
- Modify: `payment_dashboard/routing_repository.py`
- Modify: `payment_dashboard/routing_run_store.py`

**Interfaces:** Persisted context artifacts contain exactly the six approved columns; manifest configuration records context columns and all model version identifiers.

- [ ] Add a failing run-store test proving account and unrelated fields are absent.
- [ ] Add a failing manifest test for context-column and state/timeline versions.
- [ ] Run focused tests and verify full contexts are currently persisted.
- [ ] Select the approved columns before `RoutingRunStore.save`.
- [ ] Extend configuration lineage without changing content addressing.
- [ ] Run repository and run-store tests.

### Task 8: Documentation, formatting, and complete verification

**Files:**
- Modify: `README.md`
- Modify: `docs/data-card.md`
- Modify: source/tests reported by Ruff formatting

- [ ] Add or update documentation assertions for benchmark v4 and three-state/sensitivity semantics.
- [ ] Correct stale version language and data-governance descriptions.
- [ ] Run Ruff formatting across `payment_dashboard`, `tests`, and `scripts`.
- [ ] Run `make lint`, Ruff format check, `make typecheck`, and `make test`.
- [ ] Run `.venv/bin/python -m build` and `VERIFY_DIRTY=1 make verify-clean`; distinguish environment failures from code failures.
- [ ] Run a fresh 1,000-row benchmark and verify capacity, degraded evidence, sensitivity rerouting, intervals, and minimized persisted contexts.
- [ ] Inspect `git diff --check` and final status without touching `.DS_Store` files.
