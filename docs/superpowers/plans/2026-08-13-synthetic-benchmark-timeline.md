# Synthetic Benchmark Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the advertised 1,000-row prepared dataset produce a valid, complete-hour chronological routing benchmark while preserving its source timestamps.

**Architecture:** Routing simulation adds a deterministic `Benchmark Timestamp` to a copied context frame and uses it for hourly gateway state, capacity, splitting, and displayed benchmark decisions. Source `Timestamp` remains immutable and is persisted beside benchmark time for traceability. Versioned configuration records the timeline transformation and recalibrated synthetic capacities.

**Tech Stack:** Python 3.11+, pandas, NumPy, SciPy MILP, pytest, Streamlit

## Global Constraints

- Source `Timestamp` must never be overwritten.
- Benchmark timestamps start at `2025-01-01T00:00:00Z` and advance by exactly 60 seconds in stable source timestamp and transaction-ID order.
- Gateway hourly capacities are 25, 37, 30, and 47 for Gateways A-D.
- Chronological splits contain disjoint, complete benchmark-hour buckets.
- The existing minimum-three-bucket guard remains.
- UI and documentation must call the transformed timeline synthetic.

---

### Task 1: Benchmark timeline contract

**Files:**
- Modify: `tests/test_routing_optimization.py`
- Modify: `payment_dashboard/routing_config.py`
- Modify: `payment_dashboard/routing_simulation.py`
- Modify: `payment_dashboard/routing_models.py`

**Interfaces:**
- Produces: `add_benchmark_timestamps(contexts: pd.DataFrame) -> pd.DataFrame`
- Produces: `BENCHMARK_TIMESTAMP_COLUMN`, `BENCHMARK_TIMELINE_START`, `BENCHMARK_TIMELINE_FREQUENCY`, and `ROUTING_TIMELINE_VERSION`

- [ ] **Step 1: Write failing tests for deterministic benchmark timestamps**

Add tests asserting that source timestamps remain unchanged, benchmark timestamps are UTC and 60 seconds apart, shuffled input produces the same transaction-to-benchmark-time mapping, and candidates preserve `source_timestamp`.

- [ ] **Step 2: Verify the new tests fail**

Run: `.venv/bin/pytest tests/test_routing_optimization.py -q`

Expected: failure because `Benchmark Timestamp` and `source_timestamp` do not exist.

- [ ] **Step 3: Implement the minimal timeline transformation**

Define versioned constants in `routing_config.py`. Add `add_benchmark_timestamps` in `routing_simulation.py`, call it before candidate construction, use benchmark time for `timestamp` and `time_bucket`, preserve source time as `source_timestamp`, and require both timestamp columns in `RoutingBenchmark` validation.

- [ ] **Step 4: Verify Task 1 tests pass**

Run: `.venv/bin/pytest tests/test_routing_optimization.py -q`

### Task 2: Correct chronological evaluation

**Files:**
- Modify: `tests/test_routing_acceptance.py`
- Modify: `payment_dashboard/routing_evaluation.py`

**Interfaces:**
- Consumes: `BENCHMARK_TIMESTAMP_COLUMN`
- Produces: `chronological_split(contexts: pd.DataFrame) -> dict[str, pd.Index]` returning indices from the supplied frame

- [ ] **Step 1: Write failing shuffled-input split tests**

Add assertions that development ends before validation starts, validation ends before test starts, and no benchmark hour crosses a split after context rows are shuffled without resetting semantic identity.

- [ ] **Step 2: Verify the split test fails**

Run: `.venv/bin/pytest tests/test_routing_acceptance.py -q`

Expected: failure because reset RangeIndex values are applied to the unsorted frame.

- [ ] **Step 3: Implement original-index-preserving splitting**

Sort without resetting the index, derive buckets from `Benchmark Timestamp`, return the sorted frame's original indices, and calculate report boundaries from `Benchmark Timestamp`.

- [ ] **Step 4: Verify routing acceptance tests pass**

Run: `.venv/bin/pytest tests/test_routing_acceptance.py -q`

### Task 3: Real prepared-dataset acceptance and capacity calibration

**Files:**
- Modify: `tests/test_routing_acceptance.py`
- Modify: `payment_dashboard/routing_config.py`

**Interfaces:**
- Consumes: prepared contexts with two source-hour buckets
- Produces: a report containing at least three benchmark-hour buckets and capacity evidence

- [ ] **Step 1: Write a failing prepared-data-shaped acceptance test**

Build 1,000 deterministic contexts spanning two source hours, run `PandasRoutingRepository` with a temporary run root, and assert report construction succeeds with strict chronological split boundaries and at least one binding-capacity bucket.

- [ ] **Step 2: Verify the acceptance test fails before capacity/timeline integration is complete**

Run: `.venv/bin/pytest tests/test_routing_acceptance.py -q`

- [ ] **Step 3: Apply version-2 hourly capacities**

Set Gateway A-D capacities to `25`, `37`, `31`, and `47`, and bump routing simulation/state versions so persisted artifacts cannot be confused with version 1.

- [ ] **Step 4: Verify the acceptance test passes**

Run: `.venv/bin/pytest tests/test_routing_acceptance.py -q`

### Task 4: Persistence and disclosure

**Files:**
- Modify: `tests/test_routing_run_store.py`
- Modify: `tests/test_optimization_ui.py`
- Modify: `payment_dashboard/routing_repository.py`
- Modify: `payment_dashboard/routing_models.py`
- Modify: `payment_dashboard/ui/optimization.py`
- Modify: `README.md`
- Modify: `docs/data-card.md`

**Interfaces:**
- Consumes: timeline constants and contexts containing both timestamp columns
- Produces: manifest timeline configuration and `source_label="synthetic temporally expanded benchmark"`

- [ ] **Step 1: Write failing persistence and UI disclosure tests**

Assert the manifest configuration records timeline version/start/frequency and rendered UI copy contains “synthetic timeline”.

- [ ] **Step 2: Verify disclosure tests fail**

Run: `.venv/bin/pytest tests/test_routing_run_store.py tests/test_optimization_ui.py -q`

- [ ] **Step 3: Implement manifest metadata and source labeling**

Add timeline metadata in `PandasRoutingRepository.build_report`, set the report source label, and render an explicit synthetic-timeline caption. Update README and the dataset card with the transformation and capacity assumptions.

- [ ] **Step 4: Verify disclosure tests pass**

Run: `.venv/bin/pytest tests/test_routing_run_store.py tests/test_optimization_ui.py -q`

### Task 5: Full verification

**Files:**
- Modify only files required by discovered regressions

- [ ] **Step 1: Run focused routing tests**

Run: `.venv/bin/pytest tests/test_routing_optimization.py tests/test_routing_acceptance.py tests/test_routing_run_store.py tests/test_optimization_ui.py -q`

- [ ] **Step 2: Run repository checks**

Run: `make check`

- [ ] **Step 3: Verify the advertised prepared dataset manually**

Run a temporary-root script that loads `data/processed/transactions_with_gateways.csv`, builds the report, and prints source-bucket count, benchmark-bucket count, split boundaries, and binding/infeasible counts. Expected: two source buckets, at least three benchmark buckets, strict split ordering, and successful report construction.
