# Supabase Editable Transactions Design

## Objective

Replace the deployed dashboard's primary CSV data source with a Supabase-hosted
PostgreSQL database while retaining the deterministic demo-data fallback. Public
visitors may view simulated transactions and analytics. Only approved
administrators authenticated through Supabase Auth may create, edit, or
soft-delete transactions.

## Architecture

The Streamlit application uses the Supabase URL and anonymous key from local or
Streamlit secrets. PostgreSQL Row-Level Security (RLS), rather than UI visibility,
is the authority for write access. The deployed application must not receive a
Supabase service-role key.

The implementation adds four focused modules:

- `database.py` connects to Supabase, reads active transactions, maps database
  rows to the existing DataFrame schema, and reports availability.
- `auth.py` manages Supabase email/password login, logout, session state, and
  administrator verification.
- `transaction_service.py` validates and performs create, update, and soft-delete
  operations.
- `ui/admin.py` renders the administrator login and transaction-management UI.

`sql/schema.sql` defines the database objects and security policies.
`load_supabase.py` imports the cleaned, gateway-enriched CSV as a separate
administrator operation.

## Database Model

`transactions` stores the existing 15 prepared dataset fields using SQL-friendly
column names. It also contains `is_deleted`, `created_at`, `updated_at`,
`deleted_at`, `created_by`, `updated_by`, and `deleted_by`. Transaction IDs remain
unique. Indexes cover timestamp, gateway and status, plus the active-record
predicate used by dashboard queries.

`admin_users` contains approved Supabase Auth user UUIDs. `transaction_audit_log`
records insert, update, and soft-delete events, the acting user, timestamp,
transaction ID, and old/new row values. PostgreSQL triggers maintain timestamps
and create audit entries so changes remain traceable regardless of the client.

RLS allows anonymous and authenticated clients to select only active simulated
transactions. Insert, update, and soft-delete policies require the current Auth
UUID to exist in `admin_users`. Clients receive no permanent-delete policy.

## Application Flow

On startup, Streamlit attempts to read active rows from Supabase. Successful rows
are converted to the current dashboard DataFrame contract, so charts, filters,
bilingual labels, alerts, and the AI Brief require no change to their analytical
interfaces. If Supabase is unconfigured or unavailable, the application uses the
current deterministic demo dataset and clearly labels fallback mode. Editing is
disabled in fallback mode.

The admin area is hidden behind Supabase Auth login. An approved administrator can
add a transaction, select an existing record to edit, or confirm a soft deletion.
After a successful mutation, Streamlit invalidates cached transaction data and
reruns the dashboard. A failed mutation leaves displayed data unchanged.

## Validation and Error Handling

Creates and updates require a unique, non-empty transaction ID; a valid timestamp;
non-negative amount and latency; required account identifiers; and allowed status,
transaction type, device, fraud flag, and gateway values. Validation errors are
shown in plain language. Authentication, connection, and database errors are
converted to safe UI messages that do not expose secrets or raw connection data.

## Configuration and Import

Local `.streamlit/secrets.toml` and Streamlit Community Cloud secrets provide
`SUPABASE_URL` and `SUPABASE_ANON_KEY`. These values are never committed. The
one-time importer accepts an administrator-authorized Supabase session or a
service-role key supplied only to the local command environment. It validates the
complete CSV before uploading and uses upsert semantics keyed by transaction ID so
re-running an import is deterministic.

## Testing and Acceptance Criteria

Unit tests cover row/DataFrame mapping, validation, login state, CRUD service
behavior, cache/fallback selection, and soft-delete handling. SQL-focused tests
inspect required tables, indexes, triggers, and RLS policies. Optional integration
tests run against Supabase only when test credentials are present.

The feature is accepted when the existing test suite remains green, a public user
can read but cannot mutate data, an approved administrator can create and update a
record and soft-delete it, audit entries are produced, deleted records disappear
from analytics, and the dashboard remains functional in explicit fallback mode.
