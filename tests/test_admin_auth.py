from datetime import UTC, datetime, timedelta

from payment_dashboard.admin_auth import (
    clear_login_failures,
    hash_fingerprint,
    hash_password,
    login_allowed,
    record_failed_login,
    verify_password,
)


def test_hash_is_deterministic_with_fixed_salt() -> None:
    first = hash_password("correct horse", salt=b"0123456789abcdef")
    second = hash_password("correct horse", salt=b"0123456789abcdef")
    assert first == second
    assert first.startswith("pbkdf2_sha256$600000$")
    assert "correct horse" not in first


def test_verify_accepts_correct_and_rejects_wrong_password() -> None:
    encoded = hash_password("admin password", salt=b"0123456789abcdef")
    assert verify_password("admin password", encoded) is True
    assert verify_password("wrong", encoded) is False


def test_verify_rejects_malformed_hashes() -> None:
    assert verify_password("password", "not-a-password-hash") is False
    assert verify_password("password", "pbkdf2_sha256$bad$salt$key") is False


def test_fingerprint_is_stable_and_does_not_expose_hash() -> None:
    encoded = hash_password("password", salt=b"0123456789abcdef")
    fingerprint = hash_fingerprint(encoded)
    assert fingerprint == hash_fingerprint(encoded)
    assert encoded not in fingerprint
    assert len(fingerprint) == 16


class ThrottleCollection:
    def __init__(self) -> None:
        self.document = None

    def find_one(self, query):
        if self.document and self.document["_id"] == query["_id"]:
            return self.document
        return None

    def find_one_and_update(self, query, update, **_kwargs):
        attempts = int((self.document or {}).get("attempts", 0)) + 1
        self.document = {
            "_id": query["_id"],
            "attempts": attempts,
            "locked_until": (self.document or {}).get("locked_until"),
        }
        return self.document

    def update_one(self, query, update):
        assert self.document and self.document["_id"] == query["_id"]
        self.document.update(update["$set"])

    def delete_one(self, query):
        if self.document and self.document["_id"] == query["_id"]:
            self.document = None


def test_failed_login_throttle_is_shared_across_sessions() -> None:
    collection = ThrottleCollection()
    database = {"admin_login_throttle": collection}
    now = datetime(2025, 1, 1, tzinfo=UTC)

    for _ in range(5):
        record_failed_login(database, "credential", now=now)

    assert login_allowed(database, "credential", now=now) is False


def test_login_throttle_expires_and_success_clears_state() -> None:
    collection = ThrottleCollection()
    database = {"admin_login_throttle": collection}
    now = datetime(2025, 1, 1, tzinfo=UTC)
    for _ in range(5):
        record_failed_login(database, "credential", now=now)

    assert (
        login_allowed(
            database,
            "credential",
            now=now + timedelta(minutes=6),
        )
        is True
    )
    record_failed_login(database, "credential", now=now)
    clear_login_failures(database, "credential")
    assert collection.document is None
