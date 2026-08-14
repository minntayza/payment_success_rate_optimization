# Dataset Card

## Source

The transaction contexts come from Kaggle's **Transaction Data for Banking
Operations**, published by Ziya under CC0. The local input is
`data/raw/transaction_data.csv`, retrieved on 2026-08-12. Its expected row count
and SHA-256 digest are recorded in `data/source-manifest.json`.

The source contains 1,000 synthetic transactions. It is not a record of real
customers, banks, gateways, or payment processors.

## Safe preparation

Preparation validates identifiers, categories, booleans, finite numeric values,
timestamps, and simulation metadata. `PIN Code` is discarded immediately and
is never written to prepared CSVs, MongoDB, audit records, AI prompts, forms, or
dashboard output. Account identifiers are not routing features and are excluded
from public MongoDB projections.

## Synthetic routing extension

Every transaction context is expanded into four candidate routes: Gateway A-D.
Candidate success probability, fee, latency, availability, eligibility, and
capacity are versioned simulation assumptions. Potential outcomes are generated
deterministically in a separate table and are joined only after a policy fixes
its routing decisions. Each draw is keyed by simulation version, seed,
transaction ID, and gateway ID, so unrelated row insertion or reordering does
not rewrite historical counterfactuals.

The source extract contains only two distinct UTC clock-hour buckets, which is
insufficient for a complete-bucket development, validation, and test split.
`routing-benchmark-v4` therefore preserves the source `Timestamp` and adds
a separate synthetic `Benchmark Timestamp`. In stable source-time and
transaction-ID order, benchmark timestamps start at `2025-01-01T00:00:00Z` and
advance by 60 seconds. This transformation is persisted in each run manifest
and must not be interpreted as observed transaction timing.

The version-4 synthetic hourly capacities are 25, 37, 10, and 47 transactions
for Gateways A-D. They are calibrated to the synthetic benchmark arrival rate
so ordinary hours are feasible while Gateway C capacity is scarce. For mobile
transactions eligible for Gateway C, its synthetic success-probability uplift
is `0.35 × min(amount, 2500) / 2500`. This creates heterogeneous marginal value:
a chronological greedy policy can use scarce capacity on an earlier transaction
that benefits less than a later transaction. These values are not processor
limits or effects inferred from the source dataset.

Gateway operations use three states. Normal and degraded states remain routable;
degraded state reduces probability and capacity and increases latency. Unavailable
state has zero effective capacity and cannot be selected. Run artifacts minimize
contexts to transaction ID, source and benchmark timestamps, amount, transaction
type, and device. Account identifiers and unrelated dashboard fields are excluded.

The benchmark uses a chronological 60/20/20 development, validation, and test
split. It compares uniform random, round-robin, best-static, same-objective
greedy-utility, and constrained MILP policies. When MongoDB is live, the context
rows are the full active MongoDB history rather than the filtered transaction
page. A live full-history read failure disables the benchmark instead of
silently switching it to demo data. Gateway alternatives remain simulated.

## Limitations

- Results cannot estimate the performance of real gateways.
- Benchmark timestamps do not represent observed transaction arrival times.
- Adding or removing a transaction creates a new rank-based benchmark timeline
  and run artifact; comparisons must use one fixed dataset snapshot.
- Source outcomes do not identify counterfactual gateway outcomes.
- Optimizer gains are valid only inside the documented simulator.
- Outcome-seed checks redraw hidden outcomes for fixed decisions. Probability
  stress checks modify complete candidate tables and rerun greedy and MILP
  allocation. Both remain in-simulator sensitivity checks and do not supply
  calibration or real processor evidence.
- Objective weights encode an academic tradeoff, not real financial value.
- The benchmark is unsuitable for production routing or causal claims.

## Benchmark acceptance evidence

The routing benchmark is considered valid only when its automated acceptance
suite demonstrates all of the following:

- development, validation, and test contain disjoint complete UTC hourly
  buckets;
- at least one evaluation bucket has a binding gateway-capacity constraint;
- infeasible buckets and their unassigned volume are reported explicitly;
- the MILP policy improves expected utility over the feasible same-objective
  greedy policy on the built-in 1,000-row demo and selects different routes;
- realized policy comparisons include confidence intervals produced by a paired
  circular moving-block bootstrap over contiguous chronological buckets, with
  missing policy buckets aligned to zero assigned utility.

Passing software unit tests without this evidence is not sufficient to claim
that routing optimization improved payment performance.
