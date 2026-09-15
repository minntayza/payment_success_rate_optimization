"""Simulated customer-card payments for the academic demo."""

from __future__ import annotations

import copy
import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from payment_dashboard.config import (
    FAILED_STATUS,
    GATEWAY_BASE_SUCCESS_RATES,
    GATEWAYS,
    SUCCESS_STATUS,
)

DEMO_PREFERRED_GATEWAY = "Gateway A"
VISA_TEST_BIN = "4111 1111 1111"
MASTERCARD_TEST_BIN = "5555 5555 5555"


def last_four(number: str) -> str:
    """Return the last four digits from a masked or full account number."""
    digits = "".join(character for character in number if character.isdigit())
    return (digits or number)[-4:]


def public_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return JSON-safe account balances."""
    return [
        {
            **account,
            "balance": round(float(account["balance"]), 2),
            "currency": str(account.get("currency", "USD")),
        }
        for account in accounts
    ]


def demo_cards(
    customer_name: str, accounts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build Visa/Mastercard test cards linked to the customer's accounts."""
    cards: list[dict[str, Any]] = []
    for index, account in enumerate(public_accounts(accounts)):
        network = "Visa" if index == 0 else "Mastercard"
        prefix = VISA_TEST_BIN if network == "Visa" else MASTERCARD_TEST_BIN
        last4 = last_four(str(account["number"]))
        cards.append(
            {
                "network": network,
                "product": "Debit" if index == 0 else "Savings",
                "pan": f"{prefix} {last4}",
                "holder": customer_name,
                "expires": "09/28",
                "cvv": "•••",
                "linked": account["name"],
                "available": account["balance"],
                "currency": account["currency"],
            }
        )
    return cards


def decide_outcome(gateway: str) -> tuple[str, int]:
    """Return Success/Failed and a simulated latency for one gateway attempt.

    Gateway A always succeeds so a teacher can demonstrate the best route.
    Other gateways use the documented base success rates.
    """
    if gateway not in GATEWAYS:
        raise ValueError(f"Unknown gateway: {gateway}")
    latency_ms = (
        14 if gateway == DEMO_PREFERRED_GATEWAY else 22 + GATEWAYS.index(gateway)
    )
    if gateway == DEMO_PREFERRED_GATEWAY:
        return SUCCESS_STATUS, latency_ms
    succeeded = random.random() < GATEWAY_BASE_SUCCESS_RATES[gateway]
    return (SUCCESS_STATUS if succeeded else FAILED_STATUS), latency_ms


def apply_balance(
    accounts: list[dict[str, Any]], amount: float, succeeded: bool
) -> list[dict[str, Any]]:
    """Debit the everyday account only when the gateway reports success."""
    updated = copy.deepcopy(accounts)
    if not updated:
        raise ValueError("Customer has no accounts")
    available = round(float(updated[0]["balance"]), 2)
    if amount > available:
        raise ValueError("Insufficient available balance")
    if succeeded:
        updated[0]["balance"] = round(available - amount, 2)
    return updated


def payment_activity(
    *,
    reference: str,
    recipient: str,
    amount: float,
    gateway: str,
    status: str,
) -> dict[str, Any]:
    """Return a customer-activity row for the portal feed."""
    succeeded = status == SUCCESS_STATUS
    return {
        "id": reference,
        "name": recipient,
        "category": f"{gateway} · {status}",
        "amount": -amount if succeeded else 0,
        "date": "Just now",
        "icon": "✓" if succeeded else "!",
    }


def ledger_values(
    *,
    reference: str,
    sender_id: str,
    amount: float,
    gateway: str,
    status: str,
    latency_ms: int,
) -> dict[str, object]:
    """Return UI-format fields for the shared transaction ledger."""
    now = datetime.now(UTC)
    return {
        "Transaction ID": f"PAY-{reference[:8].upper()}",
        "Sender Account ID": sender_id,
        "Receiver Account ID": "EXT-PAYEE",
        "Transaction Amount": amount,
        "Transaction Type": "Transfer",
        "Timestamp": now.isoformat(),
        "Transaction Status": status,
        "Fraud Flag": False,
        "Geolocation (Latitude/Longitude)": "Yangon",
        "Device Used": "Desktop",
        "Network Slice ID": "Slice-1",
        "Latency (ms)": latency_ms,
        "Slice Bandwidth (Mbps)": 200.0,
        "Bank Gateway": gateway,
    }


def new_demo_customer() -> dict[str, Any]:
    """Return a mutable in-memory customer used when MongoDB is unset."""
    return {
        "customer_name": "Mia Aung",
        "_id": "CUST-DEMO",
        "accounts": [
            {
                "name": "Everyday account",
                "number": "•••• 4821",
                "balance": 12_580.40,
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
            {
                "name": "Alex Morgan",
                "initials": "AM",
                "account_number": "88241903",
            },
            {
                "name": "Noah Williams",
                "initials": "NW",
                "account_number": "12398821",
            },
            {
                "name": "Aye Chan",
                "initials": "AC",
                "account_number": "43018820",
            },
        ],
        "activity": [
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
        ],
        "notifications": 2,
    }


DEMO_CUSTOMER: dict[str, Any] = new_demo_customer()


def reset_demo_customer() -> None:
    """Restore the in-memory demo customer after tests or demo reset."""
    DEMO_CUSTOMER.clear()
    DEMO_CUSTOMER.update(new_demo_customer())


def next_reference() -> str:
    """Return a unique payment reference."""
    return str(uuid4())
