"""Password hashing helpers for the single academic-demo administrator."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ReturnDocument

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16
MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN = timedelta(minutes=5)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a salted, encoded PBKDF2-SHA256 password hash."""
    if not password:
        raise ValueError("Password must not be empty")
    actual_salt = salt if salt is not None else os.urandom(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), actual_salt, ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(actual_salt).decode("ascii")
    key_text = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"{ALGORITHM}${ITERATIONS}${salt_text}${key_text}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password without raising on malformed encoded values."""
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_text)
        if iterations != ITERATIONS:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def hash_fingerprint(encoded: str) -> str:
    """Return a non-reversible identifier used to invalidate old sessions."""
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def login_allowed(
    database: Any,
    fingerprint: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether the shared credential is outside its server lockout."""
    current = now or datetime.now(UTC)
    collection = database["admin_login_throttle"]
    state = collection.find_one({"_id": fingerprint})
    if not state:
        return True
    locked_until = state.get("locked_until")
    if not isinstance(locked_until, datetime) or locked_until <= current:
        if isinstance(locked_until, datetime):
            collection.delete_one({"_id": fingerprint})
        return True
    return False


def record_failed_login(
    database: Any,
    fingerprint: str,
    *,
    now: datetime | None = None,
) -> None:
    """Atomically count a shared-credential failure and apply the cooldown."""
    current = now or datetime.now(UTC)
    collection = database["admin_login_throttle"]
    state = collection.find_one_and_update(
        {"_id": fingerprint},
        {
            "$inc": {"attempts": 1},
            "$setOnInsert": {"locked_until": None},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if int(state.get("attempts", 0)) >= MAX_LOGIN_ATTEMPTS:
        collection.update_one(
            {"_id": fingerprint},
            {"$set": {"locked_until": current + LOGIN_COOLDOWN}},
        )


def clear_login_failures(database: Any, fingerprint: str) -> None:
    """Clear shared throttle state after successful authentication."""
    database["admin_login_throttle"].delete_one({"_id": fingerprint})
