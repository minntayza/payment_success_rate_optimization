# Synthetic Benchmark Timeline Design

## Goal

Make the routing benchmark runnable on the advertised 1,000-row source dataset
without weakening chronological isolation or rewriting the source transaction
timestamps.

## Problem

The source data spans only two UTC hourly buckets: 983 transactions occupy the
first bucket and 17 occupy the second. A complete-bucket development,
validation, and test split therefore cannot create three disjoint periods.
Splitting rows inside an hour would remove demand from a shared capacity bucket
and invalidate the routing comparison.

## Chosen design

The routing benchmark will create a separate, deterministic `Benchmark
Timestamp` column. The original `Timestamp` remains unchanged and continues to
drive the operational dashboard. Benchmark timestamps start at
`2025-01-01T00:00:00Z` and advance by 60 seconds in stable source timestamp and
transaction-ID order. One thousand transactions therefore span more than sixteen
complete UTC hours and support bucket-preserving chronological evaluation.

This transformation is a versioned simulation assumption, not source data.
The simulator version and UI copy will identify the benchmark timeline as
synthetic.

## Data flow

1. `generate_routing_benchmark` validates and sorts source contexts.
2. A focused helper adds `Benchmark Timestamp` without changing `Timestamp`.
3. Gateway state, candidate `time_bucket`, capacity, and chronological splits
   use `Benchmark Timestamp`.
4. Candidate rows retain both `timestamp` (benchmark time) and
   `source_timestamp` for traceability.
5. Persisted context artifacts contain both timestamp columns, and the run
   manifest records the benchmark start, interval, and timeline version.
6. The optimization UI labels the source as a synthetic, temporally expanded
   local benchmark.

## Capacity assumptions

Gateway capacity remains an hourly constraint but is recalibrated for the
synthetic arrival rate of approximately 60 transactions per hour. Version 2
uses hourly capacities of 25, 37, 30, and 47 for Gateways A-D respectively
(total 139). Normal and incident buckets in the advertised test period remain
feasible, while preferred gateways can bind. These are explicitly synthetic
assumptions.

## Chronological split contract

`chronological_split` sorts by `Benchmark Timestamp` and transaction ID but
returns the original context indices. This prevents reset-index positions from
being applied to another frame. Development, validation, and test must contain
disjoint complete benchmark-hour buckets with strictly increasing boundaries.

## Failure behavior

The existing minimum-three-bucket guard remains. Empty inputs, invalid source
timestamps, or duplicate transaction IDs continue to fail validation. The app
must still show a bounded warning when a genuinely unsuitable benchmark is
provided.

## Tests

- The real prepared dataset produces at least three benchmark-hour buckets and
  builds an optimization report end to end.
- Source `Timestamp` values are unchanged after benchmark generation.
- Benchmark timestamps are deterministic, UTC, ordered, and spaced 60 seconds
  apart.
- Shuffled contexts still produce strictly chronological, disjoint splits.
- No benchmark hour appears in more than one split.
- Candidate rows preserve both source and benchmark timestamps.
- Capacity evidence includes at least one binding bucket on the controlled
  acceptance fixture.
- The manifest records timeline configuration and the UI discloses that the
  timeline is synthetic.

## Non-goals

- Claiming that benchmark timestamps, capacities, or gateway behavior are
  observed payment-processor data.
- Changing dashboard history timestamps.
- Permitting a two-bucket train/test shortcut.
- Turning the simulator into a production routing engine.

Benchmark time is deterministic for one fixed dataset snapshot. Adding or
removing a transaction changes later rank-based benchmark timestamps and must
produce a new persisted run; insertion stability is not claimed.
