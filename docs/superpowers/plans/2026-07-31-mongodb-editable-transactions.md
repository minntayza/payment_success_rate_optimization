# MongoDB Editable Transactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Supabase/PostgreSQL data and authentication stack with MongoDB Atlas and a hashed single-administrator password while preserving editable simulated transactions, audit history, bilingual UI, and read-only fallback.

**Architecture:** PyMongo provides Atlas connections, indexed document reads, bulk imports, and guarded mutations. A standard-library PBKDF2-SHA256 module verifies an encoded password hash from Streamlit Secrets; analytics continue to consume the existing validated DataFrame contract.

**Tech Stack:** Python 3.11+, Streamlit, pandas, PyMongo 4.x, MongoDB Atlas, hashlib/hmac, pytest, Ruff

## Global Constraints

- Use simulated academic data only.
- Store `MONGODB_URI`, `MONGODB_DATABASE`, and `ADMIN_PASSWORD_HASH` only in environment/Streamlit Secrets.
- Never render or log credentials, hashes, raw provider errors, or payment PIN values.
- Preserve soft deletion, audit events, bilingual controls, AI brief behavior, and deterministic fallback.
- Remove current Supabase runtime code, dependencies, SQL schema, tests, and active setup documentation.
- Preserve unrelated working-tree changes in `payment_dashboard/ui/sections.py`, `.DS_Store`, and `build/`.

---

### Task 1: Password Hashing and Session Authentication

**Files:**
- Create: `payment_dashboard/admin_auth.py`
- Create: `tests/test_admin_auth.py`
- Delete: `payment_dashboard/auth.py`
- Delete: `tests/test_auth.py`

**Interfaces:**
- Produces: `hash_password(password: str, *, salt: bytes | None = None) -> str`, `verify_password(password: str, encoded: str) -> bool`, and `hash_fingerprint(encoded: str) -> str`.

- [ ] Write failing tests proving deterministic salted hashes, correct/incorrect verification, malformed-hash rejection, and stable fingerprints that never contain the hash.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest tests/test_admin_auth.py -v`; expect import failure.
- [ ] Implement `pbkdf2_sha256$600000$<base64 salt>$<base64 derived key>` with `os.urandom(16)`, `hashlib.pbkdf2_hmac`, strict parsing, and `hmac.compare_digest`.
- [ ] Run the focused tests and Ruff; expect PASS.
- [ ] Remove Supabase auth files and commit with `feat: add hashed administrator authentication`.

### Task 2: MongoDB Connection, Indexes, Reads, and Mapping

**Files:**
- Create: `payment_dashboard/mongodb.py`
- Create: `tests/test_mongodb.py`
- Delete: `payment_dashboard/database.py`
- Delete: `tests/test_database.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `MongoResources(client, database)`, `DatabaseResult(frame, source: Literal["mongodb", "fallback"], message)`, `create_resources_from_env()`, `ensure_indexes(database)`, `documents_to_frame(documents)`, and `load_dashboard_transactions(fallback)`.

- [ ] Write failing tests for missing configuration, active query `{"is_deleted": {"$ne": True}}`, chronological sort, all four indexes, DataFrame conversion, and safe fallback on failure.
- [ ] Run focused tests and confirm missing-module failure.
- [ ] Add `pymongo>=4.10,<5`, remove `supabase`, create a short-timeout client, ping Atlas, create unique/query indexes, map the existing 15 fields, validate, and return safe fallback messages.
- [ ] Run focused tests and Ruff; expect PASS.
- [ ] Commit with `feat: load dashboard transactions from MongoDB`.

### Task 3: MongoDB Mutations, Soft Delete, and Audit Log

**Files:**
- Modify: `payment_dashboard/transaction_service.py`
- Replace: `tests/test_transaction_service.py`

**Interfaces:**
- Consumes: PyMongo database and existing UI-format values.
- Produces: `create_transaction(database, values, actor="administrator")`, `update_transaction(database, transaction_id, values, actor="administrator")`, and `soft_delete_transaction(database, transaction_id, actor="administrator")`.

- [ ] Write failing tests asserting `insert_one`, `$set` updates, no transaction-ID changes, soft-delete timestamps, no `delete_one`, and matching INSERT/UPDATE/SOFT_DELETE audit documents with PIN omitted from snapshots.
- [ ] Run focused tests and confirm failures against Supabase behavior.
- [ ] Preserve current validation, convert timestamps to UTC datetimes, use guarded MongoDB writes, catch duplicate IDs, and insert sanitized audit snapshots. Attempt `with_transaction`; fall back only for topology/transaction-unavailable errors.
- [ ] Run focused tests and Ruff; expect PASS.
- [ ] Commit with `feat: add audited MongoDB transaction mutations`.

### Task 4: MongoDB Importer and Streamlit Admin Integration

**Files:**
- Create: `payment_dashboard/load_mongodb.py`
- Create: `tests/test_load_mongodb.py`
- Delete: `payment_dashboard/load_supabase.py`
- Delete: `tests/test_load_supabase.py`
- Modify: `payment_dashboard/ui/admin.py`
- Modify: `tests/test_admin_ui.py`
- Modify: `payment_dashboard/app.py`
- Modify: `tests/test_app.py`
- Modify: `payment_dashboard/i18n.py`
- Modify: `Makefile`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `frame_to_documents(frame)`, `import_transactions(path, database, batch_size=200)`, CLI `payment-load-mongodb`, and `render_admin_panel(database, source, frame, language)`.

- [ ] Write failing importer and UI tests for deterministic `UpdateOne(..., upsert=True)`, fallback editing disabled, correct password unlock, wrong password rejection, session invalidation after hash change, logout, and MongoDB source naming.
- [ ] Run focused tests and verify failures.
- [ ] Implement batched `bulk_write`, index creation, `make load-mongodb`, password-only login, hash fingerprint session state, MongoDB mutation calls, new cloud secret keys, and direct-entrypoint module ordering. Remove email/Supabase-specific UI and commands.
- [ ] Run focused tests, full AppTest integration, and Ruff; expect PASS.
- [ ] Commit with `feat: integrate MongoDB administrator workflow`.

### Task 5: Remove Supabase Artifacts, Document Atlas, and Verify

**Files:**
- Delete: `sql/schema.sql`
- Delete: `tests/test_sql_schema.py`
- Delete: `docs/supabase-setup.md`
- Create: `docs/mongodb-atlas-setup.md`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: current Atlas setup, hash-generation, import, Streamlit Cloud, security, and recovery instructions.

- [ ] Write failing configuration tests requiring MongoDB keys/guide and forbidding active Supabase dependency/configuration references.
- [ ] Run focused tests and verify failures.
- [ ] Document Atlas cluster/user/network setup, least-privilege URI, hash generation without printing plaintext, `make load-mongodb`, Streamlit Secrets, CRUD/audit verification, fallback mode, and credential rotation. Remove Supabase runtime guidance.
- [ ] Install dependencies with `.venv/bin/pip install -e '.[dev]'`.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q`, `.venv/bin/ruff check payment_dashboard tests`, targeted `ruff format --check`, `git diff --check HEAD`, and a headless Streamlit smoke test.
- [ ] Commit with `docs: replace Supabase setup with MongoDB Atlas` and push `main` after fresh verification.
