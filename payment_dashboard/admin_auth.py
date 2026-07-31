"""Password hashing helpers for the single academic-demo administrator."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16


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
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def hash_fingerprint(encoded: str) -> str:
    """Return a non-reversible identifier used to invalidate old sessions."""
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
