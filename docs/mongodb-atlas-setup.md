# MongoDB Atlas Setup

This academic application stores only simulated transactions in MongoDB Atlas.
Public visitors can analyze active documents. A single password-protected
administrator can create, edit, and soft-delete them.

## 1. Create the Atlas deployment

1. Create a free MongoDB Atlas project and cluster.
2. Under **Database Access**, create a dedicated database user. Grant read/write
   access only to the `payment_success_demo` database.
3. Under **Network Access**, allow the narrowest address range practical. Streamlit
   Community Cloud may require temporary `0.0.0.0/0`; use a strong generated
   database password if so.
4. Copy the Python driver connection URI and URL-encode special characters in its
   username or password.

## 2. Generate the administrator password hash

Run this locally. The prompt hides the plaintext password and prints only its
salted encoded hash:

```bash
.venv/bin/python -c 'from getpass import getpass; from payment_dashboard.admin_auth import hash_password; print(hash_password(getpass("Admin password: ")))' 
```

Copy the resulting `pbkdf2_sha256$...` value. Do not store the plaintext password.

## 3. Configure and import

Set secrets in the terminal used for the initial import:

```bash
export MONGODB_URI='mongodb+srv://app-user:password@cluster.example.mongodb.net/'
export MONGODB_DATABASE='payment_success_demo'
export ADMIN_PASSWORD_HASH='pbkdf2_sha256$600000$...'
make prepare
make load-mongodb
```

The importer validates the prepared CSV, creates indexes, and upserts each
transaction by `transaction_id`, so it is safe to rerun.

## 4. Configure Streamlit Community Cloud

Open **Settings → Secrets** and add:

```toml
MONGODB_URI = "mongodb+srv://app-user:password@cluster.example.mongodb.net/"
MONGODB_DATABASE = "payment_success_demo"
ADMIN_PASSWORD_HASH = "pbkdf2_sha256$600000$..."
ADMIN_SUBJECT = "shared-demo-admin"
```

Keep existing AI settings separately. `ADMIN_PASSWORD_HASH` is one shared demo
credential, not an individual user account; `ADMIN_SUBJECT` is its shared audit
label. Failed-login counts and cooldown are stored in MongoDB, so a new browser
does not reset them. Reboot the app after saving.

## 5. Verify behavior

1. Confirm public dashboard data loads without an administrator login.
2. Expand the administrator manager and verify a wrong password is rejected.
3. Sign in, create a clearly marked simulated record, edit it, and soft-delete it.
4. Confirm the record disappears from analytics without being physically deleted.
5. Confirm `transaction_audit_log` contains INSERT, UPDATE, and SOFT_DELETE events
   attributed to the configured shared subject.

Dataset re-import preserves soft deletions, updates active matching records,
inserts new records, leaves absent records unchanged, and writes
`IMPORT_INSERT`/`IMPORT_UPDATE` audit events as `dataset-importer`.
   and does not contain `pin_code` in its snapshots.

When Atlas is unavailable, the dashboard uses read-only demo fallback data. Rotate
the Atlas database password and admin hash immediately if either is exposed.
