# Supabase Editable Transactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store simulated payment transactions in Supabase PostgreSQL and let authenticated, approved administrators create, edit, and soft-delete them without disrupting the public dashboard or its demo fallback.

**Architecture:** Streamlit uses the Supabase anonymous client for public reads and Supabase Auth sessions for administrator writes. PostgreSQL RLS and triggers enforce authorization, soft deletion, timestamps, and audit logging; Python modules map SQL rows to the dashboard's existing DataFrame contract and isolate authentication, persistence, and UI concerns.

**Tech Stack:** Python 3.11+, Streamlit 1.40, pandas 2.2, Supabase Python client 2.x, Supabase Auth, PostgreSQL, pytest, Ruff

## Global Constraints

- Use only simulated Kaggle-derived or deterministic demo data; never store real payment or customer data.
- Keep public analytics readable without authentication and restrict every mutation with PostgreSQL RLS.
- Never ship or commit a Supabase service-role key; the deployed app uses only `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- Preserve the current deterministic demo fallback and disable editing whenever fallback data is active.
- Soft-delete transactions; do not expose permanent deletion through the application.
- Preserve current English/Burmese dashboard behavior and keep generated AI briefs in English.
- Preserve unrelated working-tree changes, especially `payment_dashboard/ui/sections.py`, `.DS_Store` files, and `build/`.

---

### Task 1: PostgreSQL Schema, RLS, and Audit Trail

**Files:**
- Create: `sql/schema.sql`
- Create: `tests/test_sql_schema.py`

**Interfaces:**
- Consumes: Supabase-provided `auth.uid()` and `auth.users`.
- Produces: `public.transactions`, `public.admin_users`, `public.transaction_audit_log`, RLS policies, timestamp/audit triggers, and no client-facing hard-delete policy.

- [ ] **Step 1: Write failing schema contract tests**

```python
from pathlib import Path


SCHEMA = Path("sql/schema.sql")


def test_schema_defines_secured_transaction_tables() -> None:
    sql = SCHEMA.read_text().lower()
    assert "create table if not exists public.transactions" in sql
    assert "create table if not exists public.admin_users" in sql
    assert "create table if not exists public.transaction_audit_log" in sql
    assert "enable row level security" in sql
    assert "auth.uid()" in sql
    assert "is_deleted boolean not null default false" in sql


def test_schema_has_no_transaction_delete_policy() -> None:
    sql = SCHEMA.read_text().lower()
    assert "for delete" not in sql
    assert "transaction_audit_log" in sql
    assert "create trigger" in sql
```

- [ ] **Step 2: Run tests and verify the missing-file failure**

Run: `.venv/bin/pytest tests/test_sql_schema.py -v`
Expected: FAIL because `sql/schema.sql` does not exist.

- [ ] **Step 3: Add the complete idempotent SQL schema**

Define SQL-friendly transaction columns for all 15 CSV fields, including
`transaction_id text primary key`, `transaction_amount numeric(12,2)`,
`transaction_timestamp timestamptz`, `fraud_flag boolean`, `latency_ms numeric`,
`bank_gateway text`, audit metadata, and check constraints for status, type,
device, gateway, non-negative amount, and non-negative latency. Add:

```sql
alter table public.transactions enable row level security;

create policy "active transactions are publicly readable"
on public.transactions for select
using (is_deleted = false);

create policy "admins insert transactions"
on public.transactions for insert to authenticated
with check (exists (
  select 1 from public.admin_users a where a.user_id = auth.uid()
));

create policy "admins update transactions"
on public.transactions for update to authenticated
using (exists (
  select 1 from public.admin_users a where a.user_id = auth.uid()
))
with check (exists (
  select 1 from public.admin_users a where a.user_id = auth.uid()
));
```

Add partial and composite indexes for active timestamp queries and
`(bank_gateway, transaction_status)`. Add `security definer` trigger functions
with a fixed `search_path` to set actor/timestamp fields and append immutable
JSONB old/new values to the audit table. Revoke audit-log mutation from
`anon` and `authenticated`.

- [ ] **Step 4: Run the schema tests**

Run: `.venv/bin/pytest tests/test_sql_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the schema contract**

```bash
git add sql/schema.sql tests/test_sql_schema.py
git commit -m "feat: define secured Supabase transaction schema"
```

### Task 2: Supabase Configuration and Read Adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `payment_dashboard/app.py:17-22,119-142`
- Create: `payment_dashboard/database.py`
- Create: `tests/test_database.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, Supabase rows from `transactions`.
- Produces: `DatabaseResult(frame: pd.DataFrame, source: Literal["supabase", "fallback"], message: str | None)`, `create_client_from_env() -> Client | None`, `rows_to_frame(rows: list[dict[str, object]]) -> pd.DataFrame`, and `load_dashboard_transactions(fallback: Callable[[], pd.DataFrame]) -> DatabaseResult`.

- [ ] **Step 1: Write failing mapping, configuration, and fallback tests**

```python
def test_rows_to_frame_preserves_dashboard_contract(transaction_row):
    frame = rows_to_frame([transaction_row])
    assert frame.loc[0, "Transaction ID"] == "TX-1"
    assert frame.loc[0, "Bank Gateway"] == "Gateway A"
    assert str(frame["Timestamp"].dtype).startswith("datetime64")


def test_load_dashboard_transactions_uses_fallback_on_query_error(monkeypatch, frame):
    monkeypatch.setattr(database, "create_client_from_env", lambda: BrokenClient())
    result = load_dashboard_transactions(lambda: frame)
    assert result.source == "fallback"
    assert result.frame.equals(frame)
    assert result.message
```

Also extend the Streamlit-secrets test to assert that `SUPABASE_URL` and
`SUPABASE_ANON_KEY` are included in `CLOUD_SETTING_KEYS`.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `.venv/bin/pytest tests/test_database.py tests/test_app.py -v`
Expected: FAIL because the database adapter and Supabase secret keys are absent.

- [ ] **Step 3: Add the Supabase dependency and adapter**

Add `supabase>=2.15,<3` to `pyproject.toml` and pin the resolved compatible 2.x
version in `requirements.txt`. Implement a single `COLUMN_MAP` between SQL names
and all current CSV display names. `rows_to_frame` must call
`validate_transactions(..., require_gateway=True)`, coerce types identically to
`load_transactions`, and sort chronologically. The query must be:

```python
response = (
    client.table("transactions")
    .select("*")
    .eq("is_deleted", False)
    .order("transaction_timestamp")
    .execute()
)
```

Catch Supabase/network exceptions at the adapter boundary, log only exception
types, and return the supplied fallback with a safe message. Add both Supabase
keys to `CLOUD_SETTING_KEYS`.

- [ ] **Step 4: Install and verify the adapter**

Run: `.venv/bin/pip install -e '.[dev]'`
Run: `.venv/bin/pytest tests/test_database.py tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the read path**

```bash
git add pyproject.toml requirements.txt payment_dashboard/database.py payment_dashboard/app.py tests/test_database.py tests/test_app.py
git commit -m "feat: load dashboard transactions from Supabase"
```

### Task 3: Authentication and Validated Transaction Mutations

**Files:**
- Create: `payment_dashboard/auth.py`
- Create: `payment_dashboard/transaction_service.py`
- Create: `tests/test_auth.py`
- Create: `tests/test_transaction_service.py`

**Interfaces:**
- Consumes: Supabase `Client`, Auth email/password, dashboard-format transaction mappings.
- Produces: `AuthState(user_id: str, email: str, access_token: str)`, `sign_in(client, email, password) -> AuthState`, `sign_out(client) -> None`, `is_admin(client, user_id) -> bool`, `validate_transaction(values, *, partial=False) -> dict[str, object]`, `create_transaction(client, values) -> None`, `update_transaction(client, transaction_id, values) -> None`, and `soft_delete_transaction(client, transaction_id) -> None`.

- [ ] **Step 1: Write failing authentication and validation tests**

```python
def test_sign_in_returns_safe_auth_state(fake_client):
    state = sign_in(fake_client, "admin@example.com", "secret")
    assert state.user_id == "user-1"
    assert state.email == "admin@example.com"
    assert "secret" not in repr(state)


def test_validation_rejects_negative_amount(valid_values):
    valid_values["Transaction Amount"] = -1
    with pytest.raises(TransactionValidationError, match="non-negative"):
        validate_transaction(valid_values)


def test_soft_delete_uses_update_not_delete(fake_client):
    soft_delete_transaction(fake_client, "TX-1")
    assert fake_client.deleted is False
    assert fake_client.updated == {"is_deleted": True}
```

Test blank IDs, invalid timestamp/status/gateway, missing required fields,
duplicate insert error translation, rejected non-admin lookup, and safe auth errors.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `.venv/bin/pytest tests/test_auth.py tests/test_transaction_service.py -v`
Expected: FAIL because both modules are absent.

- [ ] **Step 3: Implement auth and mutation services**

Use `client.auth.sign_in_with_password({"email": email, "password": password})`
and query `admin_users` for the returned UUID. Store only the minimal auth state in
Streamlit session state at the UI boundary. Convert display names to SQL names via
the shared mapping in `database.py`. Create with `.insert(payload)`, edit with
`.update(payload).eq("transaction_id", transaction_id)`, and soft-delete only with:

```python
client.table("transactions").update({"is_deleted": True}).eq(
    "transaction_id", transaction_id
).execute()
```

Map expected uniqueness, validation, authentication, and authorization failures
to typed application exceptions with safe messages; do not expose raw responses.

- [ ] **Step 4: Run service tests and lint**

Run: `.venv/bin/pytest tests/test_auth.py tests/test_transaction_service.py -v`
Run: `.venv/bin/ruff check payment_dashboard/auth.py payment_dashboard/transaction_service.py`
Expected: all PASS.

- [ ] **Step 5: Commit authenticated mutations**

```bash
git add payment_dashboard/auth.py payment_dashboard/transaction_service.py tests/test_auth.py tests/test_transaction_service.py
git commit -m "feat: add authenticated transaction mutations"
```

### Task 4: Deterministic Supabase Importer

**Files:**
- Create: `payment_dashboard/load_supabase.py`
- Create: `tests/test_load_supabase.py`
- Modify: `pyproject.toml`
- Modify: `Makefile`

**Interfaces:**
- Consumes: prepared CSV, local-only `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`.
- Produces: `frame_to_rows(frame: pd.DataFrame) -> list[dict[str, object]]`, `import_transactions(path: Path, client: Client, batch_size: int = 200) -> int`, and CLI command `payment-load-supabase`.

- [ ] **Step 1: Write failing importer tests**

```python
def test_frame_to_rows_serializes_timestamp_and_boolean(prepared_frame):
    row = frame_to_rows(prepared_frame)[0]
    assert row["transaction_timestamp"].endswith("00:00")
    assert isinstance(row["fraud_flag"], bool)


def test_import_upserts_in_batches(fake_client, prepared_csv):
    count = import_transactions(prepared_csv, fake_client, batch_size=2)
    assert count == 3
    assert [len(batch) for batch in fake_client.batches] == [2, 1]
```

- [ ] **Step 2: Run importer tests and verify failures**

Run: `.venv/bin/pytest tests/test_load_supabase.py -v`
Expected: FAIL because the importer is absent.

- [ ] **Step 3: Implement a local-only validated upsert importer**

Load with `load_transactions(path, require_gateway=True)`, serialize all values,
and upsert batches with `on_conflict="transaction_id"`. The CLI must refuse to run
without both URL and service-role key, print only imported row counts, and never
print credentials. Register it in `[project.scripts]` and add a `make load-supabase`
target that invokes the module against `data/processed/transactions_with_gateways.csv`.

- [ ] **Step 4: Run importer tests**

Run: `.venv/bin/pytest tests/test_load_supabase.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the importer**

```bash
git add payment_dashboard/load_supabase.py tests/test_load_supabase.py pyproject.toml Makefile
git commit -m "feat: import prepared transactions into Supabase"
```

### Task 5: Administrator Streamlit Interface and App Integration

**Files:**
- Create: `payment_dashboard/ui/admin.py`
- Create: `tests/test_admin_ui.py`
- Modify: `payment_dashboard/app.py:24-60,119-129,241-288`
- Modify: `payment_dashboard/i18n.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_i18n.py`

**Interfaces:**
- Consumes: `DatabaseResult`, auth functions, mutation functions, Supabase client, current language.
- Produces: `render_admin_panel(client: Client | None, database_source: str, language: Language) -> bool`, returning `True` when a mutation requires data refresh.

- [ ] **Step 1: Write failing UI and integration tests**

```python
def test_fallback_mode_disables_transaction_editing(app_test):
    app_test.run()
    assert app_test.info[0].value
    assert not any(button.label == "Save transaction" for button in app_test.button)


def test_admin_create_requests_refresh(monkeypatch, authenticated_state):
    monkeypatch.setattr(admin, "create_transaction", Mock())
    assert render_admin_panel(fake_client, "supabase", "en") is True
```

Add tests for failed login, non-admin rejection, logout, edit prepopulation, delete
confirmation, translated static labels, and cache clearing after a successful write.

- [ ] **Step 2: Run UI tests and verify failures**

Run: `.venv/bin/pytest tests/test_admin_ui.py tests/test_app.py tests/test_i18n.py -v`
Expected: FAIL because the admin UI and translations are absent.

- [ ] **Step 3: Implement the admin panel and integrate the database result**

Render an `Admin Transaction Manager` expander after the language control. When
logged out, show email and password inputs with the password masked. After login,
verify `admin_users` membership before rendering tabs for Add, Edit, and Delete.
Use select boxes for constrained values, numeric inputs with minimum zero, a
timestamp input, and explicit confirmation before soft deletion. Never place auth
tokens or passwords in rendered text.

Update `_load_data` to return `DatabaseResult`; display a translated fallback
notice when `source == "fallback"`; pass `.frame` to existing analytics; invoke
the admin panel only after secrets are applied. On `True`, clear only the cached
transaction query and call `st.rerun()`. Register new modules in the direct
Streamlit Cloud bootstrap list so `payment_dashboard/app.py` remains a valid
deployment entry point.

- [ ] **Step 4: Run UI tests and a local Streamlit smoke test**

Run: `.venv/bin/pytest tests/test_admin_ui.py tests/test_app.py tests/test_i18n.py -v`
Run: `.venv/bin/streamlit run payment_dashboard/app.py --server.headless true`
Expected: tests PASS and Streamlit starts without import or secrets errors.

- [ ] **Step 5: Commit the admin experience**

```bash
git add payment_dashboard/ui/admin.py payment_dashboard/app.py payment_dashboard/i18n.py tests/test_admin_ui.py tests/test_app.py tests/test_i18n.py
git commit -m "feat: add administrator transaction manager"
```

### Task 6: Documentation, Full Verification, and Supabase Setup

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `AGENTS.md`
- Create: `docs/supabase-setup.md`

**Interfaces:**
- Consumes: completed schema, importer, Streamlit application, Supabase project.
- Produces: reproducible setup instructions and verified local/deployed behavior.

- [ ] **Step 1: Add configuration regression checks**

Extend existing configuration tests to assert `.env.example` includes only
`SUPABASE_URL` and `SUPABASE_ANON_KEY` for runtime, documents the local-only
`SUPABASE_SERVICE_ROLE_KEY`, and that committed files contain no actual key values.

- [ ] **Step 2: Run the checks and verify documentation gaps**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL until the examples and documentation are updated.

- [ ] **Step 3: Document exact Supabase setup and recovery steps**

Document: create a Supabase project; run `sql/schema.sql` in SQL Editor; create one
email/password user; copy that user's UUID into `admin_users`; set local and
Streamlit Cloud public secrets; locally set the service-role key only for the
import command; run `make load-supabase`; verify row count; test public read,
admin login, create, edit, soft delete, and audit rows; rotate any exposed key.
State clearly that the dataset is simulated and that fallback mode is read-only.

- [ ] **Step 4: Run full automated verification**

Run: `.venv/bin/pytest`
Run: `.venv/bin/ruff check .`
Run: `.venv/bin/ruff format --check .`
Expected: all tests pass and Ruff reports no issues.

- [ ] **Step 5: Perform database and browser verification**

Against the configured Supabase project, apply the schema and importer, then verify
with an anonymous session that insert/update calls fail. Log in as the approved
administrator, create a clearly marked test transaction, edit it, soft-delete it,
confirm it disappears from public analytics, and confirm the audit table records
all three events. Verify the deployed Streamlit dashboard preserves bilingual
controls and AI Brief behavior. Do not copy secrets into logs or screenshots.

- [ ] **Step 6: Commit documentation and verification support**

```bash
git add README.md .env.example AGENTS.md docs/supabase-setup.md tests/test_config.py
git commit -m "docs: add Supabase deployment guide"
```

