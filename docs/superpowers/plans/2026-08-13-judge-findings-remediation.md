# Judge Findings Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining benchmark, data-integrity, shared-authentication, localization, and documentation defects from the judge review.

**Architecture:** Keep simulator truthfulness separate from software correctness. Make stochastic artifacts key-stable, compare policies through one utility contract, synchronize imports without destroying deletion state, store shared-admin throttling in MongoDB, and route optimization copy through the existing translation catalog.

**Tech Stack:** Python 3.11+, pandas, NumPy, SciPy MILP, PyMongo, Streamlit, pytest.

## Global Constraints

- Work on the existing `main` worktree and preserve unrelated dirty files.
- Use TDD for every behavioral change.
- Do not claim the synthetic benchmark proves real processor performance.
- Do not introduce a false multi-user identity model.
- Keep all normal tests offline; MongoDB behavior uses semantic fakes.

---

### Task 1: Key-stable counterfactual outcomes

**Files:** `tests/test_routing_optimization.py`, `payment_dashboard/routing_simulation.py`, `payment_dashboard/routing_config.py`

**Interface:** Add a private deterministic uniform helper keyed by simulation version, seed, transaction ID, and gateway ID; retain `generate_routing_benchmark(contexts, seed)`.

- [ ] Add a regression test that inserts an earlier transaction and asserts every existing candidate key retains its outcome.
- [ ] Run it and confirm sequential RNG fails.
- [ ] Implement SHA-256-derived uniforms and bump the routing simulation version.
- [ ] Run routing tests and confirm ordering-independent outcomes.

### Task 2: Fair baseline allocation

**Files:** `tests/test_routing_optimization.py`, `payment_dashboard/routing_policies.py`, `payment_dashboard/routing_evaluation.py`

**Interfaces:** `_allocate` retains feasible earlier decisions and records only actually unassigned IDs; best-static development selection maximizes mean expected utility under selected weights.

- [ ] Add a test proving one unrouteable transaction does not erase a prior decision.
- [ ] Add a test where success-only and utility-aware static choices differ.
- [ ] Run both and confirm current behavior fails.
- [ ] Continue after an unrouteable transaction and preserve accumulated decisions.
- [ ] Select static gateway using the shared utility function.
- [ ] Run routing policy and acceptance tests.

### Task 3: Robust validation and sensitivity evidence

**Files:** `tests/test_routing_optimization.py`, `payment_dashboard/routing_evaluation.py`, `payment_dashboard/routing_models.py`, `payment_dashboard/ui/optimization.py`, `tests/test_optimization_ui.py`

**Interfaces:** `select_objective_weights` scores expected validation utility; `OptimizationReport` carries seed-stability and probability-stress evidence frames.

- [ ] Add a test showing realized validation flips cannot change selected weights.
- [ ] Add deterministic sensitivity tests for multiple outcome seeds and ±0.03 clipped probability stress.
- [ ] Run them and confirm missing behavior.
- [ ] Select weights from expected utility and build the sensitivity evidence.
- [ ] Render the evidence with an explicit within-simulator disclaimer.
- [ ] Run evaluation and UI tests.

### Task 4: Finite admin mutation validation

**Files:** `tests/test_transaction_service.py`, `payment_dashboard/transaction_service.py`

- [ ] Add parameterized tests rejecting positive and negative infinity for every numeric mutation field.
- [ ] Run them and confirm positive infinity is accepted.
- [ ] Require `math.isfinite(number)` in the shared mutation validator.
- [ ] Run transaction-service and CSV-validation tests.

### Task 5: Deletion-preserving audited imports

**Files:** `tests/test_load_mongodb.py`, `payment_dashboard/load_mongodb.py`

**Interface:** import operations preserve existing deletion fields and emit `IMPORT_INSERT` or `IMPORT_UPDATE` audit records under `dataset-importer`; absent records are counted but unchanged.

- [ ] Expand the semantic import fake and add tests for deleted, active, new, and absent records.
- [ ] Run tests and confirm resurrection/missing audits.
- [ ] Replace blind bulk upserts with deletion-aware batched reconciliation and audit writes.
- [ ] Return a typed import summary and print its counts from the CLI.
- [ ] Run import and Mongo repository tests.

### Task 6: MongoDB-backed shared-admin throttling

**Files:** `tests/test_admin_ui.py`, `payment_dashboard/admin_auth.py`, `payment_dashboard/ui/admin.py`, `payment_dashboard/app.py`

**Interfaces:** authentication helpers read/update one `admin_login_throttle` document keyed by password fingerprint; the UI subject comes from `ADMIN_SUBJECT` with default `shared-demo-admin`.

- [ ] Add tests proving failures in one simulated browser session lock a second session.
- [ ] Add tests for expiry and successful-login reset.
- [ ] Run them and confirm session-state throttling fails.
- [ ] Implement atomic Mongo-backed failure counting and cooldown checks.
- [ ] Pass the live database into login rendering and label the credential shared.
- [ ] Run admin and app integration tests.

### Task 7: Optimization localization and truthful documentation

**Files:** `payment_dashboard/i18n.py`, `payment_dashboard/ui/optimization.py`, `payment_dashboard/app.py`, `tests/test_optimization_ui.py`, `docs/customer-support-guide.md`, `docs/mongodb-atlas-setup.md`, `README.md`, `docs/data-card.md`

- [ ] Add a Myanmar rendering test that rejects the current English headings.
- [ ] Run it and confirm failure.
- [ ] Add translation keys and pass `language` through the optimization renderer.
- [ ] Correct the alert baseline definition and document shared-admin/import/sensitivity semantics.
- [ ] Run UI, translation, and documentation-related tests.

### Task 8: Full verification

- [ ] Run `make lint`.
- [ ] Run `make typecheck`.
- [ ] Run `make test`.
- [ ] Run `git diff --check`.
- [ ] Execute the built-in 1,000-row benchmark and report MILP versus greedy utility, binding buckets, sensitivity results, and residual simulator limitation.
