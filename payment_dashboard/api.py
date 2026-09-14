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
from uuid import uuid4

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

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
    account_number: str = Field(min_length=4, max_length=32)
    amount: float = Field(gt=0, le=10_000)
    note: str = Field(default="", max_length=120)


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
DEMO_CUSTOMER_BALANCE = 12_580.40
DEMO_CUSTOMER_ACTIVITY: list[dict[str, object]] = [
    {
        "id": "txn-1001",
        "name": "Fresh Mart",
        "category": "Card payment",
        "amount": -42.50,
        "date": "Today",
        "icon": "🛒",
    },
    {
        "id": "txn-1002",
        "name": "Monthly salary",
        "category": "Income",
        "amount": 2_450.00,
        "date": "Yesterday",
        "icon": "↓",
    },
    {
        "id": "txn-1003",
        "name": "Electricity bill",
        "category": "Bills",
        "amount": -31.80,
        "date": "12 Sep",
        "icon": "⚡",
    },
]


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
    """Return signed-in customer profile from MongoDB."""
    seed = {
        "customer_name": "Mia Aung",
        "accounts": [
            {
                "name": "Everyday account",
                "number": "•••• 4821",
                "balance": DEMO_CUSTOMER_BALANCE,
                "currency": "USD",
            },
            {
                "name": "Savings goal",
                "number": "•••• 1184",
                "balance": 5_200.00,
                "currency": "USD",
            },
        ],
        "beneficiaries": [
            {"name": "Alex Morgan", "initials": "AM", "account_number": "•••• 8852"},
            {"name": "Noah Williams", "initials": "NW", "account_number": "•••• 1239"},
            {"name": "Aye Chan", "initials": "AC", "account_number": "•••• 4301"},
        ],
        "activity": DEMO_CUSTOMER_ACTIVITY[:8],
        "notifications": 2,
    }
    if not os.getenv("MONGODB_URI"):
        return seed
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
            for item in seed["activity"]
        ]
        database["customer_activity"].insert_many(activity)
        for item in activity:
            item.pop("customer_id", None)
            item.pop("created_at", None)
    return {
        "customer_name": customer["customer_name"],
        "accounts": customer["accounts"],
        "beneficiaries": customer["beneficiaries"],
        "activity": activity,
        "notifications": customer["notifications"],
    }


@app.post("/api/customer/transfers", status_code=status.HTTP_201_CREATED)
def customer_transfer(
    transfer: CustomerTransfer,
    principal: Annotated[AuthenticatedPrincipal, Depends(_principal)],
) -> dict[str, object]:
    """Record a simulated customer transfer for local customer-portal testing."""
    global DEMO_CUSTOMER_BALANCE
    if os.getenv("MONGODB_URI"):
        database = _live_database()
        customer = database["customer_users"].find_one({"email": principal.subject})
        if customer is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Customer profile unavailable. Run payment-seed-customers.",
            )
        balance = float(customer["accounts"][0]["balance"])
        if transfer.amount > balance:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Insufficient available balance",
            )
        reference = str(uuid4())
        changed = database["customer_users"].update_one(
            {"_id": customer["_id"], "accounts.0.balance": {"$gte": transfer.amount}},
            {"$inc": {"accounts.0.balance": -transfer.amount}},
        )
        if changed.modified_count != 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Balance changed. Refresh and retry transfer.",
            )
        database["customer_activity"].insert_one(
            {
                "id": reference,
                "customer_id": customer["_id"],
                "name": transfer.recipient,
                "category": transfer.note or "Bank transfer",
                "amount": -transfer.amount,
                "date": "Just now",
                "icon": "↗",
                "created_at": datetime.now(UTC),
            }
        )
        return {
            "status": "scheduled",
            "reference": reference,
            "available_balance": balance - transfer.amount,
        }
    if transfer.amount > DEMO_CUSTOMER_BALANCE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Insufficient available balance"
        )
    DEMO_CUSTOMER_BALANCE -= transfer.amount
    activity = {
        "id": str(uuid4()),
        "name": transfer.recipient,
        "category": transfer.note or "Bank transfer",
        "amount": -transfer.amount,
        "date": "Just now",
        "icon": "↗",
    }
    DEMO_CUSTOMER_ACTIVITY.insert(0, activity)
    _demo_audit("CUSTOMER_TRANSFER", str(activity["id"]), principal)
    return {
        "status": "scheduled",
        "reference": activity["id"],
        "available_balance": DEMO_CUSTOMER_BALANCE,
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
