# Remaining Integrity Repairs Design

## Goal

Close every unresolved finding from the second judge review without weakening the
project's central disclosure: this is a synthetic academic routing benchmark, not
evidence about real gateways or a production routing system.

## Gateway state and degraded-period evidence

Gateway state becomes an explicit three-state domain model:

- `normal`: routable at the profile's normal probability, latency, and capacity;
- `degraded`: routable with a versioned probability penalty, latency multiplier,
  and reduced positive capacity;
- `unavailable`: not routable and has zero effective capacity.

The state configuration must define degraded and unavailable incident hours
separately. Candidate rows carry `operational_state`, while the existing
`available` field remains the hard eligibility boundary. `is_degraded` is true
only for routable degraded rows. At least one evaluation-period transaction must
be assigned through a degraded gateway in the built-in benchmark, otherwise the
degraded-period evidence is reported as unavailable rather than implied to be a
successful analysis.

## Import and audit integrity

The dataset importer must use an explicit safe projection when reading existing
transactions. It must never read or copy `pin_code`, account identifiers, or
other fields unnecessary for reconciliation into audit snapshots. A shared audit
sanitizer removes `_id`, `pin_code`, and prohibited aliases defensively before
any old or new document is stored.

Import and interactive mutation audit events use one schema: `changed_at`,
`transaction_id`, `action`, `actor`, `actor_role`, `old_document`, and
`new_document`. Import mutation and audit writes continue to share a MongoDB
transaction when sessions are available. The existing deletion-preserving import
semantics remain unchanged.

## Solver input validation

`RoutingBenchmark` rejects non-finite probabilities, fees, latency, and capacity
before any policy or solver runs. Probabilities must be finite and within
`[0, 1]`; fees and latency must be finite and non-negative; capacity must be a
finite positive integer. Boolean eligibility and availability fields must contain
only non-null booleans. Invalid input raises `ValueError` with a field-specific
diagnostic and is never converted into a solver failure.

## Monitoring evidence

Both pandas and MongoDB alert paths return the same evidence contract for each
gateway:

- baseline and recent counts;
- baseline and recent start/end timestamps;
- baseline and recent success rates;
- percentage-point difference;
- a 95% confidence interval for the difference of independent proportions;
- sufficiency and alert flags.

The recent window contains the latest 50 attempts and the baseline contains only
earlier attempts with at least 200 rows. An alert requires both the configured
practical drop threshold and a confidence interval whose lower bound is above
zero. The UI displays counts, boundaries, rates, difference, interval, and status.
Pandas and MongoDB results must be contract-compatible.

## Genuine sensitivity rerouting

Probability stress scenarios operate on complete candidate tables, not on routes
already selected. For each predeclared shift (`-0.03`, `+0.03`), the benchmark:

1. copies the test candidate table and applies the clipped probability shift;
2. reruns greedy and MILP allocation using the selected weights;
3. recomputes expected utility from the new decisions;
4. reports changed-route counts and the MILP advantage.

Outcome-seed scenarios keep candidate probabilities fixed, regenerate only hidden
potential outcomes, and recompute realized utility for the fixed policy decisions.
The UI labels these separately as allocation sensitivity and outcome sensitivity.
Neither is described as real-world robustness.

## Simulation lineage

Prepared and live datasets must contain exactly one nonblank simulation version.
Mixed versions are rejected during validation rather than summarized under the
first row's label. Empty datasets may use the existing explicit empty/legacy
diagnostic but cannot silently invent lineage for populated rows.

## Persisted-data minimization

Routing run contexts contain only the fields required to reproduce candidate
generation and chronological evaluation:

- `Transaction ID`;
- source `Timestamp`;
- `Benchmark Timestamp`;
- `Transaction Amount`;
- `Transaction Type`;
- `Device Used`.

Sender/receiver IDs, geolocation, source outcome, fraud flag, PIN, and dashboard
latency are excluded. The persisted manifest records the context column list,
simulation/state/timeline versions, seed, weights, source label, split boundaries,
and artifact digests. Loading still verifies every digest.

## Documentation and repository readiness

README and data-card version statements must match `routing-benchmark-v4` and
describe the three gateway states, minimized run artifacts, monitoring interval,
and rerouting sensitivity semantics. Source code and tests must pass the exact
configured Ruff formatting scope. Incidental `.DS_Store` files remain excluded
from commits.

## Testing and acceptance

Tests must prove:

- legacy PIN/account fields cannot enter import audit records;
- import and CRUD audit records share `changed_at`;
- NaN and infinities are rejected for every numeric routing input;
- degraded gateways are routable and produce non-empty degraded-period evidence;
- unavailable gateways remain impossible to select;
- alert windows are non-overlapping and expose counts, boundaries, and intervals;
- statistically uncertain drops do not alert;
- probability stress reruns policies and can change routes;
- mixed simulation versions are rejected;
- persisted contexts contain exactly the approved columns;
- runtime and documentation versions agree.

Completion requires `make lint`, Ruff format check, strict mypy, the complete
offline pytest suite, package build, clean-checkout verification, and a fresh
1,000-row benchmark evidence run. If network isolation prevents an isolated
build, the limitation must be reported rather than represented as a code pass.

## Residual limitations

All probabilities, gateway states, fees, latency, capacities, and outcomes remain
hand-authored synthetic assumptions. The repaired evidence can establish internal
software and simulator consistency only. It cannot establish calibration, causal
effects, or production suitability.
