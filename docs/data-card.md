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
its routing decisions.

The benchmark uses a chronological 60/20/20 development, validation, and test
split. It compares uniform random, round-robin, best-static, greedy-success, and
constrained MILP policies.

## Limitations

- Results cannot estimate the performance of real gateways.
- Source outcomes do not identify counterfactual gateway outcomes.
- Optimizer gains are valid only inside the documented simulator.
- Objective weights encode an academic tradeoff, not real financial value.
- The benchmark is unsuitable for production routing or causal claims.

## Benchmark acceptance evidence

The routing benchmark is considered valid only when its automated acceptance
suite demonstrates all of the following:

- development, validation, and test contain disjoint complete UTC hourly
  buckets;
- at least one evaluation bucket has a binding gateway-capacity constraint;
- infeasible buckets and their unassigned volume are reported explicitly;
- the MILP policy improves expected utility over at least one feasible baseline
  on the controlled acceptance fixture;
- realized policy comparisons include confidence intervals produced by
  resampling complete chronological buckets.

Passing software unit tests without this evidence is not sufficient to claim
that routing optimization improved payment performance.
