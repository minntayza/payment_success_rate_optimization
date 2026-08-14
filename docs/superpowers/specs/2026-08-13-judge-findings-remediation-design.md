# Judge Findings Remediation Design

## Goal

Remove the remaining implementation artifacts and data-quality defects identified
by the judge while keeping the project honest about what it is: a controlled
synthetic routing experiment, not evidence about real payment processors.

## Benchmark integrity

Counterfactual outcomes will be generated independently for each
`(simulation_version, seed, transaction_id, gateway_id)` key. A cryptographic
digest will map that key to a uniform value, so inserting, deleting, or reordering
unrelated transactions cannot rewrite an existing key's outcome.

Heuristic policies will retain every decision made before an unrouteable
transaction. Only that transaction and any later genuinely unrouteable
transactions remain unassigned; one failure will not erase valid work. The
best-static gateway will be selected on development data by the same expected
utility used to score all policies, not success probability alone.

Weight selection will not tune against one realized Bernoulli draw. Candidate
weights will be scored on validation candidates by expected business utility,
including the unassigned penalty. Because those probabilities are simulator
assumptions, the final report will also include a seed-stability and probability-
stress sensitivity table. This evidence tests robustness inside the simulator;
the UI and documentation must continue to reject real-world or causal claims.

## Data integrity

All UI mutation numeric fields must be finite and non-negative, matching CSV
validation. Dataset import is a synchronization operation with explicit rules:

- existing soft-deleted records remain deleted;
- active matching records are updated;
- new records are inserted active;
- records absent from the import are preserved and reported, not silently deleted;
- every inserted or updated record receives a sanitized import audit event.

Import audit identity is the fixed service principal `dataset-importer`. Import
events and transaction mutations must share the database transaction when the
deployment supports transactions.

## Shared demo administration

This project will not pretend to provide multi-user identity. The UI and docs
will call it a shared demo administrator. Successful sessions use a configurable
`ADMIN_SUBJECT`, defaulting to `shared-demo-admin`; audit records identify that
shared credential, not a human.

Failed-login state will be stored in MongoDB under the password-hash fingerprint,
so opening a new browser session does not reset the five-attempt/five-minute
cooldown. If MongoDB is unavailable, administration is already disabled because
mutations require the live source; there is no session-only security fallback.

## Localization and documentation

All optimization headings, captions, table column labels, and warnings will flow
through the existing English/Myanmar translation catalog. The support guide will
state that the gateway baseline excludes the latest monitoring window. Deployment
documentation will explain shared-admin semantics and the MongoDB-backed lockout.

## Verification

Tests must prove key-stable outcomes, retained heuristic decisions, objective-
aware static selection, expected-value weight selection, sensitivity evidence,
finite mutation validation, deletion-preserving audited imports, cross-session
lockout, Myanmar optimization copy, and corrected documentation behavior. The
final gate is Ruff, strict mypy, the complete offline pytest suite, and a fresh
built-in benchmark run.

## Explicit residual limitation

Even after these changes, the optimizer still operates on hand-authored gateway
assumptions and is evaluated inside that simulator. Sensitivity analysis makes
the synthetic conclusion less brittle; it does not create empirical gateway
calibration, causal evidence, or production-routing validity.
