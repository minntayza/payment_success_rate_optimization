"""Supabase authentication helpers for administrator access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AuthenticationError(RuntimeError):
    """Safe authentication failure for display in the UI."""


@dataclass(frozen=True, slots=True)
class AuthState:
    user_id: str
    email: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)


def sign_in(client: Any, email: str, password: str) -> AuthState:
    """Authenticate a Supabase user and return minimal session details."""
    try:
        response = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
        user = response.user
        session = response.session
        if user is None or session is None or not user.email:
            raise ValueError("Incomplete authentication response")
        return AuthState(
            user_id=str(user.id),
            email=str(user.email),
            access_token=str(session.access_token),
            refresh_token=str(session.refresh_token),
        )
    except Exception as exc:
        raise AuthenticationError("Unable to sign in. Check your credentials.") from exc


def restore_session(client: Any, state: AuthState) -> None:
    """Restore a persisted Streamlit session on a newly created client."""
    client.auth.set_session(state.access_token, state.refresh_token)


def is_admin(client: Any, user_id: str) -> bool:
    """Return whether the authenticated user is on the admin allow-list."""
    try:
        response = (
            client.table("admin_users")
            .select("user_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as exc:
        raise AuthenticationError("Unable to verify administrator access.") from exc


def sign_out(client: Any) -> None:
    """End the current Supabase Auth session."""
    try:
        client.auth.sign_out()
    except Exception as exc:
        raise AuthenticationError("Unable to sign out safely.") from exc
