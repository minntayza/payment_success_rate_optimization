# Synthetic Payment Routing Optimization Design

**Date:** 2026-08-12
**Status:** Approved for implementation planning

## Goal

Convert the existing synthetic payment monitoring dashboard into a defensible
academic payment-routing optimization project. The system will choose one of
four eligible synthetic gateways for each transaction to maximize expected
payment value while respecting processing-cost, latency, and capacity
constraints. It will evaluate the optimized allocation against explicit
baseline policies on an untouched chronological test period.

The project will remain a synthetic benchmark. It will not claim that its
gateway results measure real payment processors or that its recommendations
should be used for production financial routing.

## Source Data and Provenance

The existing Kaggle transaction CSV remains the immutable source dataset. Its
transaction fields provide the contexts to route, including timestamp, amount,
transaction type, device, fraud flag, latency, and network attributes. The
source transaction outcome is retained as `Source Transaction Status` for
descriptive analysis, but it is not treated as the outcome of any synthetic
gateway.

Preparation will record an input manifest containing the exact dataset URL,
license, expected filename, row count, SHA-256 checksum, and retrieval date.
The repository will include a data card describing provenance, field meanings,
synthetic extensions, limitations, and prohibited interpretations.

`PIN Code` is excluded from all prepared data, optimization inputs, database
documents, forms, audit records, logs, prompts, and dashboard output. Sender and
receiver account IDs are not optimization features and are excluded from public
dashboard queries. The raw source CSV remains ignored by Git.

## Optimization Dataset

The preparation pipeline produces two derived datasets.

### Transaction contexts

One row per source transaction with a stable transaction ID and normalized UTC
timestamp. It contains only fields required for analysis or routing. The source
status is retained under its explicit source name and is never overwritten by a
gateway simulation.

### Candidate routes

One row for every transaction and gateway pair. With four gateways, each source
transaction produces four candidate rows. Each candidate contains:

- transaction ID;
- gateway ID;
- eligibility;
- expected success probability;
- fixed and percentage processing fee;
- expected latency in milliseconds;
- available capacity for the transaction's time bucket;
- gateway operational-state version;
- a deterministic potential outcome used only during evaluation.

Candidate generation uses a documented seed and simulation version. Identical
input data, configuration, and seed produce identical candidate datasets.

The routing policy may use context, eligibility, expected probability, fee,
latency, and capacity. It must never receive the deterministic potential outcome
before selecting a gateway. Evaluation joins that outcome only after a policy
has returned its decisions.

## Gateway Model

The benchmark defines Gateway A-D as neutral synthetic labels. No gateway is
universally best.

- Gateway A has relatively high general approval probability, higher cost, and
  lower capacity.
- Gateway B has lower latency and higher capacity but weaker performance during
  configured overnight periods.
- Gateway C has lower cost and stronger performance for configured mobile and
  local transaction contexts but greater operational variability.
- Gateway D has stronger performance for configured high-value transfers and
  higher latency.

Gateway state changes in fixed UTC time buckets. The state can alter
availability, capacity, latency, fee, and success probability. A deterministic
incident schedule introduces documented degraded periods so that a static
gateway choice is not optimal for every transaction.

All base rates, adjustments, fee formulas, capacity limits, incident periods,
probability clamps, and random seeds live in versioned configuration. The data
card and dashboard explain them as benchmark assumptions rather than observed
facts.

## Objective and Constraints

For every time bucket, the optimizer assigns each transaction to exactly one
eligible gateway. The objective maximizes the total expected utility:

```text
expected utility =
    success_value * expected_success_probability
    - fee_weight * expected_processing_fee
    - latency_weight * expected_latency_ms
```

The initial benchmark uses documented default weights. Validation-period
analysis may select among a small, predeclared grid of weight configurations;
the untouched test period cannot influence weight selection.

The allocation is subject to these hard constraints:

- every transaction receives exactly one gateway;
- an ineligible or unavailable gateway receives no transaction;
- assignments do not exceed a gateway's capacity in a time bucket;
- an optional bucket-level fee ceiling is respected when enabled;
- the solver must report infeasibility rather than silently violating a hard
  constraint.

Optimization runs independently for bounded chronological time buckets using a
mixed-integer linear program. `scipy.optimize.milp` is the intended solver so
the implementation remains local and open source. Deterministic tie-breaking
uses gateway ID after equal objective values.

If a bucket is infeasible because total eligible capacity is below transaction
volume, the benchmark records the bucket as infeasible and does not fabricate a
valid allocation. Dashboard and evaluation outputs show the affected volume.

## Baseline Policies

The optimized policy is compared with four baselines operating under the same
eligibility and capacity constraints:

1. **Uniform random:** seeded random selection among feasible gateways.
2. **Round robin:** deterministic rotation through feasible gateways.
3. **Best static:** one gateway chosen from the development period, with
   deterministic feasible spillover when it is unavailable or full.
4. **Greedy success:** select the feasible gateway with the highest expected
   success probability for each transaction without globally optimizing cost
   and latency.

Every policy receives the same candidate rows and potential outcomes. No policy
may use realized test outcomes while routing.

## Chronological Evaluation

Transactions are sorted by UTC timestamp and transaction ID, then split once:

- first 60%: development period;
- next 20%: validation and objective-weight selection;
- final 20%: untouched evaluation period.

The split is chronological, never random. Simulation configuration is fixed
before evaluating the final period. The report includes the exact timestamp
boundaries and sample sizes.

Each policy is evaluated on:

- realized success rate and successful-payment count;
- expected and realized total utility;
- total processing fee and cost per successful payment;
- average and P95 latency;
- assignment volume and utilization by gateway;
- unavailable or ineligible assignment violations;
- capacity violations;
- infeasible and unassigned transaction counts;
- performance during normal and degraded gateway periods;
- absolute and relative change from every baseline.

Bootstrap confidence intervals are calculated by resampling chronological time
buckets rather than individual rows, preserving within-bucket dependence. The
report distinguishes practical improvement from sampling uncertainty.

## Monitoring Corrections

The existing operational monitoring remains secondary to the routing
optimization. Its baseline is corrected so the recent window never overlaps
the reference history.

For each gateway, the latest 50 active routed attempts form the recent window.
The baseline contains only earlier attempts and requires at least 200 rows.
Alert output includes baseline and recent sample sizes, time boundaries, rates,
percentage-point change, and uncertainty. Future transactions cannot change a
historical alert calculation.

## Architecture

The project adds focused modules rather than placing solver logic in Streamlit:

- `routing_models.py` defines gateway profiles, candidate routes, objective
  weights, routing decisions, and evaluation result types.
- `routing_simulation.py` produces deterministic gateway states, candidate
  routes, and hidden potential outcomes from transaction contexts.
- `routing_policies.py` implements random, round-robin, static, and greedy
  baselines behind one policy interface.
- `routing_optimizer.py` constructs and solves bounded MILP allocations.
- `routing_evaluation.py` performs chronological splits, joins hidden outcomes
  after decisions, calculates metrics, and produces policy comparisons.
- `routing_repository.py` defines the snapshot contract consumed by the UI.
- `analytics.py` retains pure descriptive calculations.
- `alerting.py` owns leakage-free monitoring calculations.
- `app.py` coordinates repositories, state, and rendering but contains no
  simulation formulas or solver construction.

Existing oversized UI and MongoDB modules may be split only where required to
add these boundaries. Unrelated redesign is outside scope.

## Data Flow

```text
Immutable source CSV
        |
        v
Validation, sensitive-field removal, provenance check
        |
        v
Normalized transaction contexts
        |
        v
Versioned gateway-state and candidate-route simulation
        |
        +--> hidden potential outcomes (evaluation only)
        |
        +--> chronological development / validation / test split
                    |
                    +--> baseline policies
                    |
                    +--> constrained MILP optimizer
                              |
                              v
                    decisions joined to hidden outcomes
                              |
                              v
                    comparison report and dashboard
```

## Dashboard

The optimization dashboard becomes the main product story and displays:

- a persistent `SYNTHETIC BENCHMARK` source label;
- objective weights and active constraints;
- policy comparison for success, fee, latency, and utility;
- gateway allocation and capacity utilization;
- normal-period and degraded-period performance;
- infeasible and unassigned transaction counts;
- chronological cumulative utility or success comparison;
- example decisions with context, eligible alternatives, selected gateway, and
  objective contribution;
- the simulation version and evaluation-period boundaries.

The UI never exposes potential outcomes for unselected gateways as facts about
real processors. It labels optimizer results as results of the configured
synthetic benchmark.

## Data Management and Security

MongoDB transaction pages use explicit safe-field projections. Mutation and
audit writes execute in one MongoDB transaction so both succeed or both roll
back. Service functions receive an authenticated principal object rather than
an arbitrary actor string.

The shared-password administrator remains demo-only and is labeled accordingly.
Production identity, roles, MFA, and public write access are outside this
optimization change. Public deployments should disable mutation controls unless
a production identity boundary is introduced separately.

## Validation and Error Handling

Raw and prepared schemas are validated separately. Validation rejects missing
required fields, duplicate or blank IDs, invalid categories, invalid fraud
flags, non-finite or negative numeric values, invalid timestamps, unknown
gateways, missing simulation metadata, and unsafe prohibited fields.

Solver errors have explicit categories: invalid input, infeasible allocation,
solver failure, and evaluation leakage violation. The application does not
convert programming errors into demo results. User-facing errors exclude
secrets, raw database exceptions, and hidden potential outcomes.

## Testing

Offline automated tests cover:

- source validation and complete PIN removal;
- deterministic gateway states, candidates, and outcomes;
- documented gateway probability, fee, latency, and capacity rules;
- the requirement that no gateway is universally dominant;
- one feasible assignment per transaction;
- eligibility, availability, fee, and capacity constraints;
- deterministic solver tie-breaking;
- explicit infeasibility reporting;
- prohibition on potential-outcome access before routing;
- baseline policy behavior under identical constraints;
- chronological split boundaries and no future-data leakage;
- metric and confidence-interval calculations;
- optimizer comparison on a small fixture with a known optimum;
- leakage-free alert baselines;
- safe MongoDB projections and atomic audit behavior;
- pandas and MongoDB snapshot-contract parity;
- Streamlit rendering of synthetic labels, constraints, and comparisons.

Optional live Atlas and browser smoke tests remain separately gated. The normal
test suite performs no network calls and reads no credentials.

## Quality Gates

The implementation is complete only when all of these pass:

```bash
make lint
.venv/bin/ruff format --check payment_dashboard tests scripts
make typecheck
make test
.venv/bin/python -m build
make verify-clean
```

Strict mypy errors in application code are fixed, `make typecheck` is part of
the documented workflow, redundant packaging metadata is removed, and CI runs
the offline quality gates from a clean checkout.

## Acceptance Criteria

- The immutable source data is traceable through a verified provenance manifest.
- No prepared artifact, database document, form, audit record, prompt, or public
  query contains a PIN.
- Every transaction has four versioned candidate gateway rows before eligibility
  filtering.
- Gateway tradeoffs vary by context and time; no gateway is universally best.
- The optimizer assigns exactly one feasible gateway per transaction or reports
  the transaction in an explicitly infeasible bucket.
- Capacity and eligibility constraints have zero silent violations.
- Potential outcomes are inaccessible until after routing decisions are fixed.
- Policy selection uses only development and validation periods.
- Final metrics use the untouched chronological test period.
- Optimized results are compared with all four baselines using identical inputs.
- Dashboard and report disclose objective weights, constraints, uncertainty,
  simulation version, and synthetic limitations.
- Monitoring baselines exclude recent-window and future transactions.
- Offline tests, lint, formatting, type checking, package build, and clean
  checkout verification pass.

## Non-Goals

- Claiming observed performance for real gateways, banks, PSPs, or acquirers.
- Production payment execution or storage of real cardholder data.
- Learning causal gateway effects from the Kaggle source outcome.
- Deep reinforcement learning or an autonomous online routing agent.
- Production-grade identity, PCI-DSS compliance, or financial deployment.
- Replacing Streamlit with a separate frontend or API platform.
