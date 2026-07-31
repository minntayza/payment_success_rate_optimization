# Supabase Setup

This academic application stores simulated transactions in Supabase PostgreSQL.
Public visitors can read active records; only approved users authenticated through
Supabase Auth can create, edit, or soft-delete them. Row-level security (RLS)
enforces these rules in PostgreSQL.

## 1. Create and initialize the project

1. Create a Supabase project and wait for provisioning to finish.
2. Open **SQL Editor**, paste [`sql/schema.sql`](../sql/schema.sql), and run it.
3. Confirm that `transactions`, `admin_users`, and `transaction_audit_log` appear
   in Table Editor with row-level security enabled.

## 2. Create the administrator

1. In **Authentication → Users**, create an email/password user.
2. Copy the user's UUID.
3. Run this in SQL Editor, replacing the example UUID:

```sql
insert into public.admin_users (user_id)
values ('00000000-0000-0000-0000-000000000000');
```

The email alone is not authorization. The Auth UUID must exist in `admin_users`.

## 3. Import the prepared dataset

Find the Project URL, anonymous key, and service-role key in Supabase project
settings. Export the keys only in the terminal used for the import:

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=your-local-service-role-key
make prepare
make load-supabase
unset SUPABASE_SERVICE_ROLE_KEY
```

The importer validates the entire prepared CSV and upserts by transaction ID.
Never commit the service-role key or add it to Streamlit Community Cloud.

## 4. Configure application secrets

For local use, provide `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the shell or an
untracked `.streamlit/secrets.toml`. In Streamlit Community Cloud, open the app's
**Settings → Secrets** and add:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-public-anon-key"
```

Reboot the application after saving. The service-role key must not be present.

## 5. Verify security and behavior

1. Open the public dashboard and confirm data loads without signing in.
2. Confirm editing is unavailable until the approved administrator signs in.
3. Create a clearly marked simulated test transaction, edit it, then soft-delete
   it after confirming the warning.
4. Confirm the soft-deleted row disappears from dashboard analytics.
5. Inspect `transaction_audit_log` for INSERT, UPDATE, and SOFT_DELETE records.
6. Try a write with an anonymous Supabase session and confirm RLS rejects it.

If Supabase is unavailable, the dashboard switches to deterministic demo fallback
data and disables editing. Rotate any key that is accidentally exposed.
