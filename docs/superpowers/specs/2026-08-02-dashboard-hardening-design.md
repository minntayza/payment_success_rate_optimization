# Payment Dashboard Hardening Design

**Date:** 2026-08-02  
**Status:** Approved for implementation planning

## Goal

Strengthen the academic Streamlit MVP without rewriting it as a separate client-server application. Replace meaningless random gateway comparisons with a reproducible controlled simulation, move dashboard analytics into bounded MongoDB queries, make database fallback unmistakable, harden AI brief generation, remove duplicate build output, and add layered integration coverage.

## Scope

This design addresses disadvantages 2, 3, 5, 6, 8, 9, and 10 from the project review:

1. Random gateway assignment has no meaningful optimization signal.
2. Neutral outcomes produce an unrealistic near-50% success rate.
3. MongoDB reads materialize the full active collection.
4. Broad exception handling hides database outages behind demo data.
5. AI output is unstructured and provider failures have no useful fallback.
6. Generated `build/` code duplicates the source package.
7. Tests do not prove deployed UI or optional live-service compatibility.

Admin-auth redesign and credential rotation are outside this change. Existing secret-handling rules remain mandatory.

## Architecture

Keep Streamlit as the application shell. Introduce focused boundaries:

- `simulation.py` owns deterministic gateway and outcome simulation.
- `dashboard_repository.py` defines the dashboard query/result contract and demo implementation.
- `mongodb.py` implements filtered aggregation and paginated transaction queries.
- `ai_brief.py` owns structured provider requests, validation, retry policy, and local fallback.
- `app.py` selects a repository, maintains UI state, and renders results. It must not contain MongoDB pipeline details or simulation formulas.

Normal flow:

`Streamlit filters -> repository -> MongoDB aggregation -> dashboard state -> UI`

Degraded flow:

`known MongoDB failure -> degraded state -> demo repository -> clearly labeled UI`

## Controlled Simulation

Simulation remains academic and synthetic. It must be seeded, versioned, and explained in UI and documentation.

- Assign each gateway a documented base success probability.
- Apply small, documented risk adjustments for device, transaction type, hour, and amount band.
- Clamp final success probability to a configured safe range.
- Use a seeded generator to draw `Success` or `Failed` outcomes.
- Preserve the Kaggle outcome in `source_status`; store the synthetic outcome separately as the dashboard status.
- Add `simulation_version` so regenerated datasets can be traced.
- Keep identical input, config, and seed deterministic.

Gateway performance describes the controlled simulation only. UI must not imply real bank performance or causal findings from production traffic.

## MongoDB Query Model

Dashboard filters become a validated query object shared by live and demo repositories. Results use a common dashboard snapshot shape containing KPIs, gateway aggregates, trend buckets, failure aggregates, a transaction page, total row count, source metadata, and an optional diagnostic category.

MongoDB performs server-side work:

- `$match` applies active-document and dashboard filters.
- `$group` calculates KPI, gateway, trend, and failure aggregates.
- Recent transactions use deterministic timestamp/ID sorting with `skip` and `limit`.
- Default page size is 50; page size has a bounded maximum.
- Indexes cover active status, timestamp, gateway, payment status, device, and transaction type according to query patterns.
- Application code must not call `list()` on an unbounded transaction cursor.

The demo repository implements the same contract with pandas, allowing UI and repository contract tests to run offline.

## Explicit Degraded Mode

Only known configuration, connection, timeout, and MongoDB query errors trigger demo fallback. Unexpected programming errors remain visible during development and must not be converted into fallback data.

When degraded:

- Show a persistent localized warning: MongoDB is unavailable and simulated demo data is active.
- Show a `DEMO` source badge in the hero and KPI area; live mode shows `LIVE`.
- Disable all admin mutations.
- Provide a retry button that clears cached connection/query state and reruns.
- Put safe diagnostic category and retry guidance in an expander.
- Never display credentials, connection strings, raw provider responses, or stack traces.

## Reliable AI Brief

The provider prompt requests JSON with four required sections: `summary`, `risks`, `actions`, and `evidence`. Validation enforces types, non-empty content, reasonable size, and evidence consistency with supplied aggregate facts.

Retry once with short backoff for timeouts, connection failures, HTTP 429, and HTTP 5xx. Do not retry authentication failures, invalid configuration, or other permanent 4xx responses.

If the provider remains unavailable or returns invalid content, generate a deterministic local brief from the same aggregate facts. Both provider and fallback briefs support English and Myanmar. UI labels the origin as `AI-generated` or `Local fallback`.

The cache key includes normalized filters, data/simulation version, selected language, and model. Only aggregate facts are sent to the provider; transaction rows and identifiers remain local.

## Packaging

- Remove generated `build/` output.
- Ignore `build/` so packaging cannot leave a second importable source tree.
- Ignore `.streamlit/secrets.toml` and project-local plugin/cache artifacts.
- Keep `payment_dashboard/` as the only application source package.

## Testing

Default tests remain offline and secret-free:

- Unit tests cover simulation determinism, probability rules, clamps, and version metadata.
- Repository contract tests require live and demo implementations to return equivalent shapes and filtering semantics.
- MongoDB integration tests cover pipelines, indexes, pagination, stable sorting, and soft-delete exclusion using controlled test doubles or an isolated test database.
- Streamlit AppTest covers live/degraded badges, localized fallback messaging, retry behavior, disabled editing, and language switching.
- AI contract tests cover valid JSON, malformed output, retryable HTTP/network errors, permanent authentication errors, bilingual local fallback, and cache invalidation.

Optional tests use explicit flags and existing secrets:

- `RUN_ATLAS_TESTS=1` enables live Atlas contract tests against a dedicated test collection.
- `RUN_AI_TESTS=1` enables a minimal provider contract test with bounded tokens.
- A smoke command checks the deployed page loads, exposes a source badge and KPIs, and contains no visible Streamlit exception.

`make test` never requires network access. Separate `make test-live` and `make smoke` targets document external checks.

## Acceptance Criteria

- Same input, seed, and simulation config produce identical gateway and outcome columns.
- Generated data yields plausible, documented variation instead of a neutral coin flip.
- Live dashboard metrics and charts use bounded MongoDB aggregation queries.
- Transaction table fetches 50 rows per page and exposes total/page state.
- Atlas outage produces obvious degraded mode, disables edits, and supports retry.
- AI button always produces either validated provider content or labeled local fallback.
- Generated `build/` directory is absent and ignored.
- Offline suite, Streamlit AppTest suite, Ruff, and formatting checks pass.
- Optional live Atlas, AI, and deployed smoke checks have documented commands.

## Non-Goals

- Replacing Streamlit with a JavaScript frontend or separate REST API.
- Production-grade identity, roles, MFA, or multi-admin support.
- Claiming real payment-routing optimization from simulated data.
- Training or deploying a machine-learning model.
