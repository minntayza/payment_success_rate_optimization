"""Seed deterministic synthetic retail-bank customers for the local demo."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime

from dotenv import load_dotenv
from pymongo import UpdateOne

from payment_dashboard.mongodb import create_resources_from_env

CUSTOMER_COUNT = 100_000
FIRST_NAMES = ("Aung", "Thiri", "Mya", "Htet", "Su", "Zaw", "Nandar", "Khin")
LAST_NAMES = ("Min", "Aung", "Lin", "Win", "Oo", "Hlaing", "Myint", "Kyaw")


def _customer(number: int) -> dict[str, object]:
    """Return a deterministic synthetic customer record."""
    first_name = FIRST_NAMES[number % len(FIRST_NAMES)]
    last_name = LAST_NAMES[(number // 7) % len(LAST_NAMES)]
    name = f"{first_name} {last_name}"
    email = "demo@payments.local" if number == 1 else f"customer{number:06d}@demo.bank"
    checking = round(1_500 + ((number * 137) % 85_000) + 0.40, 2)
    savings = round(500 + ((number * 83) % 25_000), 2)
    password_hash = hashlib.sha256(
        os.getenv("WEB_USER_PASSWORD", "demo-user").encode()
    ).hexdigest()
    return {
        "_id": f"CUST-{number:06d}",
        "email": email,
        "password_hash": password_hash,
        "customer_name": name,
        "accounts": [
            {
                "name": "Everyday account",
                "number": f"•••• {4000 + number % 5000}",
                "balance": checking,
                "currency": "USD",
            },
            {
                "name": "Savings goal",
                "number": f"•••• {1000 + number % 5000}",
                "balance": savings,
                "currency": "USD",
            },
        ],
        "beneficiaries": [
            {
                "name": "Family transfer",
                "initials": "FT",
                "account_number": "•••• 4201",
            },
            {
                "name": "Utility payments",
                "initials": "UP",
                "account_number": "•••• 8820",
            },
        ],
        "notifications": number % 3,
        "seeded_at": datetime.now(UTC),
        "synthetic": True,
    }


def main() -> None:
    """Upsert 100,000 synthetic customer records into configured MongoDB."""
    load_dotenv()
    resources = create_resources_from_env()
    if resources is None:
        raise SystemExit("Set MONGODB_URI and MONGODB_DATABASE first.")
    collection = resources.database["customer_users"]
    collection.create_index("email", unique=True)
    for start in range(1, CUSTOMER_COUNT + 1, 1_000):
        end = min(start + 1_000, CUSTOMER_COUNT + 1)
        collection.bulk_write(
            [
                UpdateOne(
                    {"_id": f"CUST-{number:06d}"},
                    {"$set": _customer(number)},
                    upsert=True,
                )
                for number in range(start, end)
            ],
            ordered=False,
        )
    print(f"Seeded {CUSTOMER_COUNT} synthetic customers in {resources.database.name}")


if __name__ == "__main__":
    main()
