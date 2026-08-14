# Routing Evidence Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the routing benchmark demonstrate a genuine global-allocation advantage, evaluate uncertainty with contiguous time blocks, and use full active MongoDB history whenever the operational dashboard is live.

**Architecture:** Keep transaction sourcing separate from dashboard pagination while sharing the same configured backend. Preserve the synthetic benchmark boundary: source transactions come from MongoDB or demo data, while gateway alternatives remain versioned simulation assumptions. Compare every policy on an aligned chronological test horizon and use a circular moving-block bootstrap.

**Tech Stack:** Python 3.11+, pandas, NumPy, SciPy MILP, PyMongo, Streamlit, pytest.

## Global Constraints

- Work on the existing `main` worktree and preserve unrelated user changes.
- Use full active MongoDB history, independent of dashboard filters and pagination.
- Never silently replace a failed live optimization read with demo data.
- Write and run a failing regression test before each production behavior change.
- Keep the benchmark explicitly labeled synthetic.

---

### Task 1: Chronological split contract

**Files:**
- Modify: `tests/test_routing_optimization.py`
- Verify: `payment_dashboard/routing_evaluation.py`

**Interfaces:**
- Consumes: `chronological_split(contexts: pd.DataFrame) -> dict[str, pd.Index]`
- Produces: regression coverage proving returned labels select the correct rows after shuffle plus `reset_index(drop=True)`.

- [ ] Add a test whose hand-derived expected development, validation, and test transaction IDs remain chronological after a shuffled/reset input.
- [ ] Run the test and confirm it passes only because the earlier index fix is present.
- [ ] Keep the existing implementation if the public-boundary regression passes.

### Task 2: Demonstrable MILP allocation value

**Files:**
- Modify: `tests/test_routing_acceptance.py`
- Modify: `payment_dashboard/routing_simulation.py`
- Modify: `payment_dashboard/routing_config.py`
- Modify: `payment_dashboard/ui/optimization.py`
- Modify: `tests/test_optimization_ui.py`

**Interfaces:**
- Consumes: `generate_routing_benchmark(contexts, seed=42)` and `evaluate_all_policies(...)`.
- Produces: a versioned, bounded amount-sensitive Gateway C mobile uplift that creates heterogeneous marginal value under scarce capacity.

- [ ] Tighten the 1,000-row acceptance test to require MILP expected utility above greedy and different route decisions.
- [ ] Run it and confirm the current equal decisions fail.
- [ ] Replace Gateway C's flat mobile uplift with `0.04 + 0.12 * min(amount, 2500) / 2500`, then bump the simulation version.
- [ ] Run the focused acceptance test and confirm both policies remain feasible while MILP wins.
- [ ] Add a UI regression for an explicit MILP-versus-greedy expected-utility advantage and render that value.

### Task 3: Honest moving-block uncertainty

**Files:**
- Modify: `tests/test_routing_statistics.py`
- Modify: `payment_dashboard/routing_statistics.py`
- Modify: `payment_dashboard/routing_evaluation.py`
- Modify: `payment_dashboard/ui/optimization.py`
- Modify: `tests/test_optimization_ui.py`

**Interfaces:**
- Consumes: policy decision frames with `time_bucket` and a numeric metric.
- Produces: `block_bootstrap_policy_difference(..., block_length: int | None = None)` using circular contiguous blocks and union-aligned buckets.

- [ ] Add a test where alternating bucket differences collapse under length-two contiguous blocks.
- [ ] Add a test where policies have different bucket sets and the missing side is aligned to zero.
- [ ] Run both and confirm IID resampling/equal-set validation fails.
- [ ] Implement circular moving-block resampling with chronological union alignment and validated block length.
- [ ] Generate intervals for every baseline and render estimate, lower bound, upper bound, and zero inclusion in the UI.
- [ ] Run statistics, evaluation, and UI tests.

### Task 4: Same-source full-history optimization

**Files:**
- Modify: `tests/test_mongodb_repository.py`
- Modify: `payment_dashboard/mongodb.py`
- Modify: `tests/test_app.py`
- Modify: `payment_dashboard/app.py`
- Modify: `payment_dashboard/routing_repository.py`

**Interfaces:**
- Produces: `MongoDashboardRepository.fetch_routing_contexts() -> pd.DataFrame` over all active documents, sorted deterministically and projected through the public transaction schema.
- Produces: `_load_optimization_contexts(snapshot, language) -> tuple[pd.DataFrame, str]` selecting the same backend as monitoring.

- [ ] Add a repository test proving deleted records are excluded and all active records—not one page—are returned chronologically.
- [ ] Run it and confirm the method is missing.
- [ ] Implement the active-history aggregation and schema conversion.
- [ ] Add app tests proving live snapshots use Mongo history, demo snapshots use the local frame, and live read failures do not fall back silently.
- [ ] Run them and confirm current `_load_demo_frame` wiring fails.
- [ ] Wire report construction to the same source and expose the source label in the UI.

### Task 5: Verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/data-card.md`

- [ ] Document full-history sourcing, synthetic gateway assumptions, moving-block uncertainty, and the specific MILP-versus-greedy acceptance criterion.
- [ ] Run focused tests after every task.
- [ ] Run `make lint`, strict type checking, and the full pytest suite.
- [ ] Inspect the final diff to ensure unrelated dirty files were not changed by this work.
