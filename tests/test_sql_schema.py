from pathlib import Path

SCHEMA = Path("sql/schema.sql")


def test_schema_defines_secured_transaction_tables() -> None:
    sql = SCHEMA.read_text().lower()
    assert "create table if not exists public.transactions" in sql
    assert "create table if not exists public.admin_users" in sql
    assert "create table if not exists public.transaction_audit_log" in sql
    assert sql.count("enable row level security") >= 3
    assert "auth.uid()" in sql
    assert "is_deleted boolean not null default false" in sql


def test_schema_has_no_transaction_delete_policy() -> None:
    sql = SCHEMA.read_text().lower()
    assert "for delete" not in sql
    assert "create trigger transactions_audit_trigger" in sql
    assert "create trigger transactions_metadata_trigger" in sql


def test_schema_indexes_active_dashboard_queries() -> None:
    sql = SCHEMA.read_text().lower()
    assert "where is_deleted = false" in sql
    assert "bank_gateway, transaction_status" in sql
