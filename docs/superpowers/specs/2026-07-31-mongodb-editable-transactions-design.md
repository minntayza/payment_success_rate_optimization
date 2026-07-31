# MongoDB Editable Transactions Design

## Objective

Replace the Supabase/PostgreSQL implementation with MongoDB Atlas while
preserving the public payment dashboard, bilingual interface, AI brief,
administrator transaction management, soft deletion, audit history, and
deterministic demo fallback. This remains an academic MVP using simulated data.

## Architecture

Streamlit connects directly to MongoDB Atlas through PyMongo. Runtime secrets
provide `MONGODB_URI`, `MONGODB_DATABASE`, and `ADMIN_PASSWORD_HASH`. The app must
never commit or render these values. Public visitors can view active transaction
analytics without authentication. A single administrator unlocks mutation controls
by entering a password verified against the stored PBKDF2-SHA256 hash.

The implementation uses focused modules:

- `mongodb.py` owns connection creation, index setup, active-document reads, and
  conversion between MongoDB documents and the existing dashboard DataFrame.
- `admin_auth.py` creates and verifies salted password hashes and manages no UI.
- `transaction_service.py` validates create/update inputs and performs MongoDB
  mutations, soft deletion, and audit recording.
- `ui/admin.py` renders login, logout, create, edit, and soft-delete controls.
- `load_mongodb.py` validates and deterministically upserts the prepared CSV.

The existing analytics modules continue consuming the same column-oriented
DataFrame contract, insulating charts and metrics from the storage change.

## Document Model and Indexes

The `transactions` collection stores SQL-friendly snake-case versions of the 15
prepared CSV fields plus `is_deleted`, `created_at`, `updated_at`, `deleted_at`,
and actor labels. Atlas indexes enforce a unique `transaction_id` and accelerate
`transaction_timestamp`, `(bank_gateway, transaction_status)`, and
`(is_deleted, transaction_timestamp)` queries.

The `transaction_audit_log` collection stores the transaction ID, action
(`INSERT`, `UPDATE`, or `SOFT_DELETE`), timestamp, actor label, and sanitized old
and new document snapshots. `app_metadata` may store importer version and dataset
metadata but is not required for dashboard operation.

## Authentication and Authorization

`admin_auth.py` uses Python's standard-library `hashlib.pbkdf2_hmac` with SHA-256,
a random salt, and a documented fixed iteration count. The encoded value contains
the algorithm, iterations, salt, and derived key. Verification uses
`hmac.compare_digest`. Only the encoded hash is stored in Streamlit Secrets.

A successful login sets a boolean and a fingerprint of the configured hash in
Streamlit session state. If the configured hash changes, the session is invalidated.
Logout removes the session immediately. The admin UI is not a database security
boundary: Atlas credentials must be scoped to the application database and network
access must be limited where deployment constraints allow. This single-password
design is appropriate only for the academic MVP.

## Reads, Mutations, and Audit Behavior

Dashboard reads query documents where `is_deleted` is not true, sort by timestamp,
and convert the result to the existing validated DataFrame. If Atlas is missing or
unavailable, the app uses deterministic demo/CSV fallback data, displays a safe
notice, and disables all editing.

Creates require a unique transaction ID. Updates preserve the original ID.
Deletion updates `is_deleted`, `deleted_at`, and actor metadata instead of removing
the document. The service attempts the transaction mutation and audit insertion in
a MongoDB session transaction. When transactions are unavailable in the chosen
Atlas topology, it performs the guarded mutation followed by audit insertion and
returns a clear safe error if auditing fails. No hard-delete operation is exposed.

Every mutation clears only transaction-data cache state and reruns Streamlit.
Provider errors are converted to user-safe messages that exclude URIs, hashes,
credentials, and raw responses.

## Import and Configuration

`load_mongodb.py` loads the prepared CSV through existing schema validation,
serializes native values, and performs batched `UpdateOne(..., upsert=True)` writes
keyed by `transaction_id`. Re-running the importer is deterministic. It also creates
required indexes. The importer uses the same `MONGODB_URI` and `MONGODB_DATABASE`
environment settings as local runtime but never prints them.

Supabase dependencies, SQL files, Auth logic, environment settings, tests, and
documentation are removed or replaced. Historical Supabase design documents remain
as project decision history, while current README and setup guidance describe only
MongoDB Atlas.

## Testing and Acceptance Criteria

Unit tests cover password hash generation and verification, configuration-change
session invalidation, document/DataFrame mapping, active-document queries, index
creation, validation, CRUD behavior, soft deletion, audit creation, deterministic
import upserts, fallback behavior, and bilingual admin labels. Fake collection and
client objects keep the default test suite independent of live Atlas credentials.
Optional integration verification uses a configured Atlas database.

The feature is accepted when all existing dashboard tests remain green; public
analytics work without administrator login; the correct password unlocks mutation
controls; an administrator can create, edit, and soft-delete a simulated record;
audit events are produced; deleted records disappear from analytics; secrets are
not committed or rendered; and explicit fallback mode remains read-only.
