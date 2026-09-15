"""HTTP interface for the payment-monitor web application.

The API delegates analytics and transaction mutations to the existing domain
modules, keeping Streamlit out of the business and security seam.
"""
# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Any, Literal

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from payment_dashboard.customer_payments import (
    DEMO_CUSTOMER,
    apply_balance,
    decide_outcome,
    demo_cards,
    ledger_values,
    next_reference,
    payment_activity,
    public_accounts,
)
from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)
from payment_dashboard.demo_data import generate_demo_transactions
from payment_dashboard.mongodb import (
    COLUMN_MAP,
    MongoDashboardRepository,
    create_resources_from_env,
)
from payment_dashboard.transaction_service import (
    AuthenticatedPrincipal,
    TransactionMutationError,
    TransactionValidationError,
    create_transaction,
    soft_delete_transaction,
    update_transaction,
    validate_transaction,
)

load_dotenv()

Role = Literal["user", "admin"]
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="Payment Success Monitor API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        item.strip()
        for item in os.getenv("WEB_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class TransactionInput(BaseModel):
    values: dict[str, object] = Field(
        ..., description="Display-name transaction fields"
    )


class DemoAuditEvent(BaseModel):
    action: str
    transaction_id: str
    actor: str
    changed_at: str


class CustomerTransfer(BaseModel):
    recipient: str = Field(min_length=2, max_length=80)
    account_number: str = Field(default="88241903", min_length=4, max_length=32)
    amount: float = Field(gt=0, le=10_000)
    note: str = Field(default="", max_length=120)
    gateway: Literal["Gateway A", "Gateway B", "Gateway C", "Gateway D"] = "Gateway A"


def _secret() -> bytes:
    value = os.getenv("WEB_AUTH_SECRET")
    if value:
        return value.encode()
    if not os.getenv("MONGODB_URI"):
        return b"local-demo-only-change-before-production"
    raise HTTPException(500, "WEB_AUTH_SECRET must be configured for live data")


def _accounts() -> dict[str, tuple[str, Role]]:
    """Return configured accounts; defaults are strictly for offline demo use."""
    live = bool(os.getenv("MONGODB_URI"))
    configured: dict[str, tuple[str, Role]] = {
        os.getenv("WEB_ADMIN_EMAIL", "admin@payments.local"): (
            os.getenv("WEB_ADMIN_PASSWORD", "demo-admin"),
            "admin",
        ),
    }
    if not live:
        configured[os.getenv("WEB_USER_EMAIL", "demo@payments.local")] = (
            os.getenv("WEB_USER_PASSWORD", "demo-user"),
            "user",
        )
    if live and "WEB_ADMIN_PASSWORD" not in os.environ:
        raise HTTPException(500, "Configure WEB_ADMIN_PASSWORD for live data")
    return configured


def _token(email: str, role: Role) -> str:
    payload = {
        "sub": email,
        "role": role,
        "exp": int((datetime.now(UTC) + timedelta(hours=8)).timestamp()),
    }
    body = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in is required")
    try:
        body, signature = credentials.credentials.rsplit(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if (
            not hmac.compare_digest(signature, expected)
            or int(payload["exp"]) < datetime.now(UTC).timestamp()
        ):
            raise ValueError
        role = payload["role"]
        if role not in ("user", "admin"):
            raise ValueError
        return AuthenticatedPrincipal(payload["sub"], role, datetime.now(UTC))
    except (KeyError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Your session is invalid or expired"
        ) from None


def _admin(
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
) -> AuthenticatedPrincipal:
    if principal.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Administrator access is required"
        )
    return principal


@lru_cache(maxsize=1)
def _demo_repository() -> PandasDashboardRepository:
    return PandasDashboardRepository(generate_demo_transactions())


DEMO_AUDIT_EVENTS: list[DemoAuditEvent] = []


def _public_activity(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Drop Mongo-only fields so the portal can JSON-encode activity."""
    cleaned: list[dict[str, object]] = []
    for item in rows:
        row = {
            key: value
            for key, value in item.items()
            if key not in {"_id", "customer_id", "created_at"}
        }
        cleaned.append(row)
    return cleaned


def _portal_payload(
    customer_name: str,
    accounts: list[dict[str, Any]],
    beneficiaries: list[dict[str, Any]],
    activity: list[dict[str, Any]],
    notifications: int,
) -> dict[str, object]:
    safe_accounts = public_accounts(accounts)
    return {
        "customer_name": customer_name,
        "accounts": safe_accounts,
        "cards": demo_cards(customer_name, safe_accounts),
        "beneficiaries": beneficiaries,
        "activity": _public_activity(activity)[:8],
        "notifications": notifications,
    }


def _demo_audit(
    action: str, transaction_id: str, principal: AuthenticatedPrincipal
) -> None:
    DEMO_AUDIT_EVENTS.insert(
        0,
        DemoAuditEvent(
            action=action,
            transaction_id=transaction_id,
            actor=principal.subject,
            changed_at=datetime.now(UTC).isoformat(),
        ),
    )


def _demo_payload(values: dict[str, object]) -> dict[str, object]:
    payload = validate_transaction(values)
    reverse_map = {database: display for database, display in COLUMN_MAP.items()}
    result = {
        reverse_map[key]: value for key, value in payload.items() if key in reverse_map
    }
    result["Source Transaction Status"] = result["Transaction Status"]
    result["Simulation Version"] = "manual-demo-v1"
    return result


def _repository() -> tuple[Any, Any | None]:
    resources = create_resources_from_env()
    if resources is None:
        return _demo_repository(), None
    return MongoDashboardRepository(resources.database), resources.database


def _filters(
    gateways: str | None,
    statuses: str | None,
    transaction_types: str | None,
    devices: str | None,
    start: date | None,
    end: date | None,
) -> DashboardFilters:
    def split(value: str | None) -> tuple[str, ...]:
        return tuple(item for item in (value or "").split(",") if item)

    return DashboardFilters(
        split(gateways),
        split(transaction_types),
        split(devices),
        split(statuses),
        start,
        end,
    )


def _records(frame: pd.DataFrame, *, private: bool) -> list[dict[str, object]]:
    safe = frame.copy()
    if not private:
        safe = safe.drop(
            columns=["Sender Account ID", "Receiver Account ID", "PIN Code"],
            errors="ignore",
        )
    safe = safe.where(pd.notna(safe), None)
    for column in safe.select_dtypes(include=["datetime", "datetimetz"]).columns:
        safe[column] = safe[column].map(
            lambda value: value.isoformat() if value is not None else None
        )
    return safe.to_dict(orient="records")


@app.get("/api/health")
def health() -> dict[str, str]:
    _, database = _repository()
    return {"status": "ok", "source": "live" if database is not None else "demo"}


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict[str, str]:
    email = request.email.strip().lower()
    account = _accounts().get(email)
    if account is None and os.getenv("MONGODB_URI"):
        customer = _live_database()["customer_users"].find_one(
            {"email": email}, {"password_hash": 1}
        )
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        if customer and secrets.compare_digest(
            str(customer.get("password_hash", "")), password_hash
        ):
            return {"access_token": _token(email, "user"), "role": "user"}
    if account is None or not secrets.compare_digest(request.password, account[0]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return {
        "access_token": _token(email, account[1]),
        "role": account[1],
    }


@app.get("/api/auth/me")
def me(
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
) -> dict[str, str]:
    return {"email": principal.subject, "role": principal.role}


@app.get("/api/customer/overview")
def customer_overview(
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
) -> dict[str, object]:
    """Return signed-in customer profile, cards, and recent activity."""
    if not os.getenv("MONGODB_URI"):
        return _portal_payload(
            str(DEMO_CUSTOMER["customer_name"]),
            list(DEMO_CUSTOMER["accounts"]),
            list(DEMO_CUSTOMER["beneficiaries"]),
            list(DEMO_CUSTOMER["activity"]),
            int(DEMO_CUSTOMER["notifications"]),
        )
    database = _live_database()
    customer = database["customer_users"].find_one({"email": principal.subject})
    if customer is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Customer profile unavailable. Run payment-seed-customers.",
        )
    activity = list(
        database["customer_activity"]
        .find({"customer_id": customer["_id"]}, {"_id": 0, "customer_id": 0})
        .sort("created_at", -1)
        .limit(8)
    )
    if not activity:
        activity = [
            {
                **item,
                "customer_id": customer["_id"],
                "created_at": datetime.now(UTC),
            }
            for item in DEMO_CUSTOMER["activity"]
        ]
        database["customer_activity"].insert_many(activity)
    return _portal_payload(
        str(customer["customer_name"]),
        list(customer["accounts"]),
        list(customer["beneficiaries"]),
        activity,
        int(customer.get("notifications", 0)),
    )


def _record_ledger_payment(
    principal: AuthenticatedPrincipal,
    values: dict[str, object],
    database: Any | None,
) -> None:
    """Best-effort write so Admin can see the customer payment."""
    if database is None:
        payload = _demo_payload(values)
        frame = _demo_frame()
        if str(payload["Transaction ID"]) not in set(frame["Transaction ID"]):
            _demo_repository().frame.loc[len(frame)] = payload
            _demo_audit("CUSTOMER_TRANSFER", str(payload["Transaction ID"]), principal)
        return
    try:
        create_transaction(database, values, principal)
    except (TransactionMutationError, TransactionValidationError):
        return


@app.post("/api/customer/transfers", status_code=status.HTTP_201_CREATED)
def customer_transfer(
    transfer: CustomerTransfer,
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
) -> dict[str, object]:
    """Route a simulated card payment through the chosen gateway."""
    status, latency_ms = decide_outcome(transfer.gateway)
    succeeded = status == "Success"
    reference = next_reference()
    activity_row = payment_activity(
        reference=reference,
        recipient=transfer.recipient,
        amount=transfer.amount,
        gateway=transfer.gateway,
        status=status,
    )
    database = None
    if os.getenv("MONGODB_URI"):
        database = _live_database()
        customer = database["customer_users"].find_one({"email": principal.subject})
        if customer is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Customer profile unavailable. Run payment-seed-customers.",
            )
        try:
            accounts = apply_balance(
                list(customer["accounts"]), transfer.amount, succeeded
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        changed = database["customer_users"].update_one(
            {"_id": customer["_id"]},
            {"$set": {"accounts": accounts}},
        )
        if changed.matched_count != 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Balance could not be updated. Refresh and retry.",
            )
        database["customer_activity"].insert_one(
            {
                **activity_row,
                "customer_id": customer["_id"],
                "created_at": datetime.now(UTC),
            }
        )
        sender_id = str(customer["_id"])
        name = str(customer["customer_name"])
        beneficiaries = list(customer["beneficiaries"])
        notifications = int(customer.get("notifications", 0))
        activity = list(
            database["customer_activity"]
            .find({"customer_id": customer["_id"]}, {"_id": 0, "customer_id": 0})
            .sort("created_at", -1)
            .limit(8)
        )
    else:
        try:
            accounts = apply_balance(
                list(DEMO_CUSTOMER["accounts"]), transfer.amount, succeeded
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        DEMO_CUSTOMER["accounts"] = accounts
        DEMO_CUSTOMER["activity"].insert(0, activity_row)
        sender_id = str(DEMO_CUSTOMER["_id"])
        name = str(DEMO_CUSTOMER["customer_name"])
        beneficiaries = list(DEMO_CUSTOMER["beneficiaries"])
        notifications = int(DEMO_CUSTOMER["notifications"])
        activity = list(DEMO_CUSTOMER["activity"])
        _demo_audit("CUSTOMER_TRANSFER", reference, principal)

    _record_ledger_payment(
        principal,
        ledger_values(
            reference=reference,
            sender_id=sender_id,
            amount=transfer.amount,
            gateway=transfer.gateway,
            status=status,
            latency_ms=latency_ms,
        ),
        database,
    )
    payload = _portal_payload(
        name,
        accounts,
        beneficiaries,
        activity,
        notifications,
    )
    return {
        **payload,
        "status": status.lower() if status == "Success" else "failed",
        "gateway": transfer.gateway,
        "latency_ms": latency_ms,
        "reference": reference,
        "available_balance": public_accounts(accounts)[0]["balance"],
        "receipt": (
            f"{transfer.gateway} approved ${transfer.amount:,.2f} to {transfer.recipient}."
            if succeeded
            else f"{transfer.gateway} declined ${transfer.amount:,.2f}. Balance unchanged."
        ),
    }


@app.get("/api/dashboard")
def dashboard(
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
    gateways: str | None = None,
    statuses: str | None = None,
    transaction_types: str | None = None,
    devices: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict[str, object]:
    repository, _ = _repository()
    try:
        snapshot = repository.fetch(
            _filters(gateways, statuses, transaction_types, devices, start, end),
            PageRequest(page, page_size),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {
        "metrics": dict(snapshot.metrics),
        "gateways": _records(snapshot.gateway_summary, private=True),
        "trend": _records(snapshot.trend, private=True),
        "alerts": _records(snapshot.alerts, private=True),
        "transactions": _records(
            snapshot.transactions, private=principal.role == "admin"
        ),
        "total_transactions": snapshot.total_transactions,
        "page": page,
        "page_size": page_size,
        "source": snapshot.source.value,
        "simulation_version": snapshot.simulation_version,
    }


def _live_database() -> Any:
    _, database = _repository()
    if database is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Transaction changes require configured MongoDB"
        )
    return database


def _demo_frame() -> pd.DataFrame:
    return _demo_repository().frame


@app.post("/api/admin/transactions", status_code=status.HTTP_201_CREATED)
def add_transaction(
    request: TransactionInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(_admin)],
) -> dict[str, str]:
    if not os.getenv("MONGODB_URI"):
        payload = _demo_payload(request.values)
        frame = _demo_frame()
        if str(payload["Transaction ID"]) in set(frame["Transaction ID"]):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Transaction ID already exists"
            )
        _demo_repository().frame.loc[len(frame)] = payload
        _demo_audit("CREATE", str(payload["Transaction ID"]), principal)
        return {"status": "created"}
    try:
        create_transaction(_live_database(), request.values, principal)
    except (TransactionMutationError, TransactionValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"status": "created"}


@app.put("/api/admin/transactions/{transaction_id}")
def edit_transaction(
    transaction_id: str,
    request: TransactionInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(_admin)],
) -> dict[str, str]:
    if not os.getenv("MONGODB_URI"):
        frame = _demo_frame()
        match = frame.index[frame["Transaction ID"] == transaction_id]
        if match.empty:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
        values = {**frame.loc[match[0]].to_dict(), **request.values}
        payload = _demo_payload(values)
        payload["Transaction ID"] = transaction_id
        for key, item in payload.items():
            frame.loc[match[0], key] = item
        _demo_audit("UPDATE", transaction_id, principal)
        return {"status": "updated"}
    try:
        database = _live_database()
        existing = database["transactions"].find_one(
            {"transaction_id": transaction_id, "is_deleted": False}
        )
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
        values = {
            display: existing[storage]
            for storage, display in COLUMN_MAP.items()
            if storage in existing
        }
        values.update(request.values)
        values["Transaction ID"] = transaction_id
        update_transaction(database, transaction_id, values, principal)
    except (TransactionMutationError, TransactionValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"status": "updated"}


@app.delete("/api/admin/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: str, principal: Annotated[AuthenticatedPrincipal, Depends(_admin)]
) -> dict[str, str]:
    if not os.getenv("MONGODB_URI"):
        frame = _demo_frame()
        match = frame.index[frame["Transaction ID"] == transaction_id]
        if match.empty:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
        frame.drop(index=match[0], inplace=True)
        _demo_audit("DELETE", transaction_id, principal)
        return {"status": "deleted"}
    try:
        soft_delete_transaction(_live_database(), transaction_id, principal)
    except (TransactionMutationError, TransactionValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"status": "deleted"}


@app.get("/api/admin/audit")
def audit_log(
    principal: Annotated[AuthenticatedPrincipal, Depends(_admin)],
) -> list[dict[str, object]]:
    if not os.getenv("MONGODB_URI"):
        return [event.model_dump() for event in DEMO_AUDIT_EVENTS[:30]]
    database = _live_database()
    documents = (
        database["transaction_audit_log"]
        .find({}, {"_id": 0, "old_document": 0, "new_document": 0})
        .sort("changed_at", -1)
        .limit(30)
    )
    del principal
    return _records(pd.DataFrame(documents), private=True)


@app.post("/api/admin/demo/reset")
def reset_demo(
    principal: Annotated[AuthenticatedPrincipal, Depends(_admin)],
) -> dict[str, str]:
    if os.getenv("MONGODB_URI"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Demo reset is unavailable for live data"
        )
    repository = _demo_repository()
    repository.frame.drop(repository.frame.index, inplace=True)
    fresh = generate_demo_transactions()
    for _, row in fresh.iterrows():
        repository.frame.loc[len(repository.frame)] = row
    DEMO_AUDIT_EVENTS.clear()
    _demo_audit("RESET", "demo-dataset", principal)
    return {"status": "reset"}


def run() -> None:
    """Start the development API server."""
    import uvicorn

    uvicorn.run("payment_dashboard.api:app", host="0.0.0.0", port=8000, reload=True)
