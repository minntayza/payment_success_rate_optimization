from payment_dashboard.admin_auth import (
    hash_fingerprint,
    hash_password,
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
