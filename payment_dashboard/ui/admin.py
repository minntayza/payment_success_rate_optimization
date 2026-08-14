"""Administrator login and transaction-management interface."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from payment_dashboard.admin_auth import (
    clear_login_failures,
    hash_fingerprint,
    login_allowed,
    record_failed_login,
    verify_password,
)
from payment_dashboard.config import GATEWAYS
from payment_dashboard.i18n import Language, translate
from payment_dashboard.models import DataSource
from payment_dashboard.transaction_service import (
    DEVICES,
    TRANSACTION_TYPES,
    AuthenticatedPrincipal,
    TransactionMutationError,
    TransactionValidationError,
    create_transaction,
    soft_delete_transaction,
    update_transaction,
)

AUTH_STATE_KEY = "mongodb_admin_auth"
AUTH_SESSION_DURATION = timedelta(minutes=30)


def _clear_admin_session() -> None:
    st.session_state.pop(AUTH_STATE_KEY, None)


def _login_allowed(database: Any, password_hash: str) -> bool:
    return login_allowed(database, hash_fingerprint(password_hash))


def _record_failed_login(database: Any, password_hash: str) -> None:
    record_failed_login(database, hash_fingerprint(password_hash))


def _is_authenticated(password_hash: str) -> bool:
    state = st.session_state.get(AUTH_STATE_KEY)
    fingerprint = hash_fingerprint(password_hash)
    if not isinstance(state, dict) or state.get("fingerprint") != fingerprint:
        _clear_admin_session()
        return False
    expires_value = state.get("expires_at")
    if not isinstance(expires_value, (str, datetime)):
        _clear_admin_session()
        return False
    expires_at = pd.Timestamp(expires_value)
    if pd.isna(expires_at) or expires_at.to_pydatetime() <= datetime.now(UTC):
        _clear_admin_session()
        return False
    return state.get("authenticated") is True


def _principal() -> AuthenticatedPrincipal:
    state = st.session_state[AUTH_STATE_KEY]
    return AuthenticatedPrincipal(
        subject=str(state["subject"]),
        role=str(state["role"]),
        authenticated_at=pd.Timestamp(state["authenticated_at"]).to_pydatetime(),
    )


def _row_values(row: pd.Series) -> dict[str, object]:
    values = {str(key): value for key, value in row.to_dict().items()}
    values.pop("Latency Band", None)
    values.pop("PIN Code", None)
    values["Fraud Flag"] = bool(values["Fraud Flag"])
    return values


def _defaults() -> dict[str, object]:
    return {
        "Transaction ID": "",
        "Sender Account ID": "",
        "Receiver Account ID": "",
        "Transaction Amount": 0.0,
        "Transaction Type": "Transfer",
        "Timestamp": datetime.now().replace(second=0, microsecond=0),
        "Transaction Status": "Success",
        "Fraud Flag": False,
        "Geolocation (Latitude/Longitude)": "",
        "Device Used": "Mobile",
        "Network Slice ID": "",
        "Latency (ms)": 0.0,
        "Slice Bandwidth (Mbps)": 0.0,
        "Bank Gateway": "Gateway A",
    }


def _choice(options: list[str], current: object) -> int:
    return options.index(str(current)) if str(current) in options else 0


def _transaction_form(prefix: str, values: dict[str, object]) -> dict[str, object]:
    stamp = pd.Timestamp(str(values["Timestamp"])).to_pydatetime()
    left, right = st.columns(2)
    with left:
        transaction_id = st.text_input(
            "Transaction ID", str(values["Transaction ID"]), key=f"{prefix}_id"
        )
        sender = st.text_input(
            "Sender Account ID",
            str(values["Sender Account ID"]),
            key=f"{prefix}_sender",
        )
        receiver = st.text_input(
            "Receiver Account ID",
            str(values["Receiver Account ID"]),
            key=f"{prefix}_receiver",
        )
        amount = st.number_input(
            "Transaction Amount",
            min_value=0.0,
            value=float(str(values["Transaction Amount"])),
            key=f"{prefix}_amount",
        )
        transaction_type = st.selectbox(
            "Transaction Type",
            sorted(TRANSACTION_TYPES),
            index=_choice(sorted(TRANSACTION_TYPES), values["Transaction Type"]),
            key=f"{prefix}_type",
        )
        status = st.selectbox(
            "Transaction Status",
            ["Success", "Failed"],
            index=_choice(["Success", "Failed"], values["Transaction Status"]),
            key=f"{prefix}_status",
        )
        fraud = st.checkbox(
            "Fraud Flag", value=bool(values["Fraud Flag"]), key=f"{prefix}_fraud"
        )
    with right:
        selected_date = st.date_input("Date", value=stamp.date(), key=f"{prefix}_date")
        selected_time = st.time_input("Time", value=stamp.time(), key=f"{prefix}_time")
        geolocation = st.text_input(
            "Geolocation",
            str(values["Geolocation (Latitude/Longitude)"]),
            key=f"{prefix}_geo",
        )
        device = st.selectbox(
            "Device Used",
            sorted(DEVICES),
            index=_choice(sorted(DEVICES), values["Device Used"]),
            key=f"{prefix}_device",
        )
        network_slice = st.text_input(
            "Network Slice ID",
            str(values["Network Slice ID"]),
            key=f"{prefix}_slice",
        )
        latency = st.number_input(
            "Latency (ms)",
            min_value=0.0,
            value=float(str(values["Latency (ms)"])),
            key=f"{prefix}_latency",
        )
        bandwidth = st.number_input(
            "Slice Bandwidth (Mbps)",
            min_value=0.0,
            value=float(str(values["Slice Bandwidth (Mbps)"])),
            key=f"{prefix}_bandwidth",
        )
        gateway = st.selectbox(
            "Bank Gateway",
            list(GATEWAYS),
            index=_choice(list(GATEWAYS), values["Bank Gateway"]),
            key=f"{prefix}_gateway",
        )
    return {
        "Transaction ID": transaction_id,
        "Sender Account ID": sender,
        "Receiver Account ID": receiver,
        "Transaction Amount": amount,
        "Transaction Type": transaction_type,
        "Timestamp": datetime.combine(selected_date, selected_time),
        "Transaction Status": status,
        "Fraud Flag": fraud,
        "Geolocation (Latitude/Longitude)": geolocation,
        "Device Used": device,
        "Network Slice ID": network_slice,
        "Latency (ms)": latency,
        "Slice Bandwidth (Mbps)": bandwidth,
        "Bank Gateway": gateway,
    }


def _render_login(database: Any, password_hash: str, language: Language) -> None:
    if not _login_allowed(database, password_hash):
        st.error("Too many failed login attempts. Try again in five minutes.")
        return
    with st.form("admin_login"):
        password = st.text_input(translate("admin.password", language), type="password")
        submitted = st.form_submit_button(translate("admin.login", language))
    if submitted:
        if verify_password(password, password_hash):
            clear_login_failures(database, hash_fingerprint(password_hash))
            st.session_state[AUTH_STATE_KEY] = {
                "authenticated": True,
                "fingerprint": hash_fingerprint(password_hash),
                "subject": os.getenv("ADMIN_SUBJECT", "shared-demo-admin"),
                "role": "administrator",
                "authenticated_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + AUTH_SESSION_DURATION).isoformat(),
            }
            st.rerun()
        else:
            _record_failed_login(database, password_hash)
            st.error(translate("admin.login_failed", language))


def _render_manager(
    database: Any,
    frame: pd.DataFrame,
    language: Language,
    principal: AuthenticatedPrincipal,
) -> bool:
    changed = False
    st.caption(translate("admin.signed_in", language, email="Administrator"))
    if st.button(translate("admin.logout", language)):
        _clear_admin_session()
        st.rerun()
    add_tab, edit_tab, delete_tab = st.tabs(
        [
            translate("admin.add", language),
            translate("admin.edit", language),
            translate("admin.delete", language),
        ]
    )
    with add_tab, st.form("add_transaction"):
        values = _transaction_form("add", _defaults())
        if st.form_submit_button(translate("admin.save", language)):
            create_transaction(database, values, principal)
            st.success(translate("admin.created", language))
            changed = True
    ids = frame["Transaction ID"].astype(str).tolist()
    if not ids:
        with edit_tab:
            st.info(translate("admin.no_transactions_edit", language))
        with delete_tab:
            st.info(translate("admin.no_transactions_delete", language))
        return changed
    with edit_tab:
        selected = st.selectbox(
            translate("admin.choose", language),
            ids,
            key="edit_transaction_selector",
        )
        row = frame.loc[frame["Transaction ID"].astype(str).eq(selected)].iloc[0]
        with st.form("edit_transaction"):
            values = _transaction_form("edit", _row_values(row))
            if st.form_submit_button(translate("admin.update", language)):
                update_transaction(database, selected, values, principal)
                st.success(translate("admin.updated", language))
                changed = True
    with delete_tab, st.form("delete_transaction"):
        selected = st.selectbox(
            translate("admin.choose", language), ids, key="delete_id"
        )
        confirmed = st.checkbox(translate("admin.confirm_delete", language))
        if st.form_submit_button(translate("admin.delete", language)):
            if not confirmed:
                st.warning(translate("admin.confirm_required", language))
            else:
                soft_delete_transaction(database, selected, principal)
                st.success(translate("admin.deleted", language))
                changed = True
    return changed


def render_admin_panel(
    database: Any | None,
    database_source: str | DataSource,
    frame: pd.DataFrame,
    language: Language,
    password_hash: str | None = None,
) -> bool:
    """Render authenticated CRUD controls and return whether data changed."""
    live_source = database_source in ("mongodb", DataSource.LIVE)
    if not live_source or database is None or not password_hash:
        st.info(translate("admin.fallback_disabled", language))
        return False
    with st.expander(translate("admin.title", language)):
        if not _is_authenticated(password_hash):
            _render_login(database, password_hash, language)
            return False
        try:
            return _render_manager(database, frame, language, _principal())
        except (TransactionMutationError, TransactionValidationError) as exc:
            st.error(str(exc))
            return False
