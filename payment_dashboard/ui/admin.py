"""Administrator login and transaction-management interface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from payment_dashboard.auth import (
    AuthenticationError,
    AuthState,
    is_admin,
    restore_session,
    sign_in,
    sign_out,
)
from payment_dashboard.config import GATEWAYS
from payment_dashboard.i18n import Language, translate
from payment_dashboard.transaction_service import (
    DEVICES,
    TRANSACTION_TYPES,
    TransactionMutationError,
    TransactionValidationError,
    create_transaction,
    soft_delete_transaction,
    update_transaction,
)

AUTH_STATE_KEY = "supabase_admin_auth"


def _clear_admin_session() -> None:
    st.session_state.pop(AUTH_STATE_KEY, None)


def _row_values(row: pd.Series) -> dict[str, object]:
    values = row.to_dict()
    values.pop("Latency Band", None)
    values["PIN Code"] = str(values["PIN Code"])
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
        "PIN Code": "",
        "Bank Gateway": "Gateway A",
    }


def _choice(options: list[str], current: object) -> int:
    return options.index(str(current)) if str(current) in options else 0


def _transaction_form(prefix: str, values: dict[str, object]) -> dict[str, object]:
    stamp = pd.Timestamp(values["Timestamp"]).to_pydatetime()
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
            value=float(values["Transaction Amount"]),
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
            value=float(values["Latency (ms)"]),
            key=f"{prefix}_latency",
        )
        bandwidth = st.number_input(
            "Slice Bandwidth (Mbps)",
            min_value=0.0,
            value=float(values["Slice Bandwidth (Mbps)"]),
            key=f"{prefix}_bandwidth",
        )
        pin = st.text_input("PIN Code", str(values["PIN Code"]), key=f"{prefix}_pin")
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
        "PIN Code": pin,
        "Bank Gateway": gateway,
    }


def _render_login(client: Any, language: Language) -> None:
    with st.form("admin_login"):
        email = st.text_input(translate("admin.email", language))
        password = st.text_input(translate("admin.password", language), type="password")
        submitted = st.form_submit_button(translate("admin.login", language))
    if submitted:
        try:
            state = sign_in(client, email, password)
            if not is_admin(client, state.user_id):
                sign_out(client)
                st.error(translate("admin.not_authorized", language))
                return
            st.session_state[AUTH_STATE_KEY] = state
            st.rerun()
        except AuthenticationError as exc:
            st.error(str(exc))


def _render_manager(client: Any, frame: pd.DataFrame, language: Language) -> bool:
    changed = False
    state: AuthState = st.session_state[AUTH_STATE_KEY]
    st.caption(translate("admin.signed_in", language, email=state.email))
    if st.button(translate("admin.logout", language)):
        sign_out(client)
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
            create_transaction(client, values)
            st.success(translate("admin.created", language))
            changed = True
    ids = frame["Transaction ID"].astype(str).tolist()
    with edit_tab:
        selected = st.selectbox(translate("admin.choose", language), ids, key="edit_id")
        row = frame.loc[frame["Transaction ID"].astype(str).eq(selected)].iloc[0]
        with st.form("edit_transaction"):
            values = _transaction_form("edit", _row_values(row))
            if st.form_submit_button(translate("admin.update", language)):
                update_transaction(client, selected, values)
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
                soft_delete_transaction(client, selected)
                st.success(translate("admin.deleted", language))
                changed = True
    return changed


def render_admin_panel(
    client: Any | None,
    database_source: str,
    frame: pd.DataFrame,
    language: Language,
) -> bool:
    """Render authenticated CRUD controls and return whether data changed."""
    if database_source != "supabase" or client is None:
        st.info(translate("admin.fallback_disabled", language))
        return False
    with st.expander(translate("admin.title", language)):
        state = st.session_state.get(AUTH_STATE_KEY)
        if state is None:
            _render_login(client, language)
            return False
        try:
            restore_session(client, state)
            if not is_admin(client, state.user_id):
                _clear_admin_session()
                st.error(translate("admin.not_authorized", language))
                return False
            return _render_manager(client, frame, language)
        except (
            AuthenticationError,
            TransactionMutationError,
            TransactionValidationError,
        ) as exc:
            st.error(str(exc))
            return False
