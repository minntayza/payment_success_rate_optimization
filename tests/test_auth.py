from types import SimpleNamespace

import pytest

from payment_dashboard.auth import AuthenticationError, is_admin, sign_in, sign_out


class Auth:
    def sign_in_with_password(self, credentials):
        assert credentials["email"] == "admin@example.com"
        return SimpleNamespace(
            user=SimpleNamespace(id="user-1", email="admin@example.com"),
            session=SimpleNamespace(access_token="token-1", refresh_token="refresh-1"),
        )

    def sign_out(self):
        self.signed_out = True


def test_sign_in_returns_safe_auth_state() -> None:
    state = sign_in(SimpleNamespace(auth=Auth()), "admin@example.com", "secret")
    assert state.user_id == "user-1"
    assert state.email == "admin@example.com"
    assert "token-1" not in repr(state)
    assert "secret" not in repr(state)


def test_sign_in_rejects_incomplete_response() -> None:
    auth = SimpleNamespace(sign_in_with_password=lambda _: SimpleNamespace(user=None))
    with pytest.raises(AuthenticationError, match="Unable to sign in"):
        sign_in(SimpleNamespace(auth=auth), "admin@example.com", "wrong")


def test_is_admin_checks_current_user() -> None:
    query = SimpleNamespace(
        select=lambda _: query,
        eq=lambda column, value: query,
        limit=lambda _: query,
        execute=lambda: SimpleNamespace(data=[{"user_id": "user-1"}]),
    )
    client = SimpleNamespace(table=lambda name: query)
    assert is_admin(client, "user-1") is True


def test_sign_out_calls_supabase() -> None:
    auth = Auth()
    sign_out(SimpleNamespace(auth=auth))
    assert auth.signed_out is True
