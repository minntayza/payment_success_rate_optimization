from __future__ import annotations

from payment_dashboard.config import FAILED_STATUS, SUCCESS_STATUS
from payment_dashboard.customer_payments import (
    apply_balance,
    decide_outcome,
    demo_cards,
    last_four,
    payment_activity,
    reset_demo_customer,
)


def test_gateway_a_always_succeeds() -> None:
    for _ in range(20):
        status, latency = decide_outcome("Gateway A")
        assert status == SUCCESS_STATUS
        assert latency > 0


def test_unknown_gateway_is_rejected() -> None:
    try:
        decide_outcome("Gateway Z")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_successful_payment_debits_everyday_account() -> None:
    accounts = [
        {
            "name": "Everyday",
            "number": "•••• 4821",
            "balance": 100.0,
            "currency": "USD",
        },
        {"name": "Savings", "number": "•••• 1184", "balance": 50.0, "currency": "USD"},
    ]
    updated = apply_balance(accounts, 25.5, True)
    assert updated[0]["balance"] == 74.5
    assert updated[1]["balance"] == 50.0
    assert accounts[0]["balance"] == 100.0


def test_failed_payment_leaves_balance_unchanged() -> None:
    accounts = [
        {"name": "Everyday", "number": "•••• 4821", "balance": 100.0, "currency": "USD"}
    ]
    updated = apply_balance(accounts, 25.5, False)
    assert updated[0]["balance"] == 100.0


def test_overspend_is_rejected_before_gateway() -> None:
    accounts = [
        {"name": "Everyday", "number": "•••• 4821", "balance": 10.0, "currency": "USD"}
    ]
    try:
        apply_balance(accounts, 10.01, True)
    except ValueError as exc:
        assert "Insufficient" in str(exc)
        return
    raise AssertionError("expected ValueError")


def test_demo_cards_use_test_visa_pan_and_track_balance() -> None:
    cards = demo_cards(
        "Su Myint",
        [
            {
                "name": "Everyday account",
                "number": "•••• 4821",
                "balance": 88.4,
                "currency": "USD",
            }
        ],
    )
    assert cards[0]["network"] == "Visa"
    assert cards[0]["pan"] == "4111 1111 1111 4821"
    assert cards[0]["available"] == 88.4
    assert last_four("•••• 4821") == "4821"


def test_activity_zeroes_amount_when_gateway_declines() -> None:
    declined = payment_activity(
        reference="abc",
        recipient="Alex",
        amount=20.0,
        gateway="Gateway D",
        status=FAILED_STATUS,
    )
    approved = payment_activity(
        reference="def",
        recipient="Alex",
        amount=20.0,
        gateway="Gateway A",
        status=SUCCESS_STATUS,
    )
    assert declined["amount"] == 0
    assert approved["amount"] == -20.0


def test_reset_demo_customer_restores_opening_balance() -> None:
    reset_demo_customer()
    from payment_dashboard.customer_payments import DEMO_CUSTOMER

    DEMO_CUSTOMER["accounts"][0]["balance"] = 1.0
    reset_demo_customer()
    assert DEMO_CUSTOMER["accounts"][0]["balance"] == 12_580.40
