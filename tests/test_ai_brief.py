"""Tests for local AI brief facts, prompting, and Ollama transport."""

from __future__ import annotations

import json

import pandas as pd

from payment_dashboard.ai_brief import build_brief_facts, facts_fingerprint


def brief_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Transaction ID": ["TX1", "TX2", "TX3", "TX4"],
            "Timestamp": pd.to_datetime(
                [
                    "2025-01-01 10:00",
                    "2025-01-01 10:01",
                    "2025-01-01 10:02",
                    "2025-01-01 10:03",
                ]
            ),
            "Transaction Type": ["Deposit", "Transfer", "Transfer", "Withdrawal"],
            "Transaction Status": ["Success", "Failed", "Failed", "Success"],
            "Transaction Amount": [10.0, 20.0, 30.0, 40.0],
            "Device Used": ["Web", "Mobile", "Mobile", "Web"],
            "Location": ["A", "B", "C", "D"],
            "Latency (ms)": [10.0, 20.0, 30.0, 30.0],
            "Fraud Flag": [False, False, False, False],
            "Bank Gateway": ["Gateway A", "Gateway B", "Gateway B", "Gateway A"],
        }
    )


def alert_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Bank Gateway": ["Gateway A", "Gateway B"],
            "is_alert": [False, True],
        }
    )


def test_build_brief_facts_returns_only_deterministic_aggregates() -> None:
    facts = build_brief_facts(brief_transactions(), alert_snapshot())

    assert facts == {
        "transaction_count": 4,
        "success_rate": 0.5,
        "average_latency_ms": 22.5,
        "gateways": [
            {"name": "Gateway A", "transactions": 2, "success_rate": 1.0},
            {"name": "Gateway B", "transactions": 2, "success_rate": 0.0},
        ],
        "active_alerts": ["Gateway B"],
        "top_failure_transaction_type": {"name": "Transfer", "failures": 2},
        "top_failure_device": {"name": "Mobile", "failures": 2},
    }

    serialized = json.dumps(facts)
    assert "TX1" not in serialized
    assert "Timestamp" not in serialized
    assert "Transaction Amount" not in serialized


def test_empty_data_produces_safe_zero_facts() -> None:
    frame = brief_transactions().iloc[0:0]
    alerts = alert_snapshot().iloc[0:0]

    assert build_brief_facts(frame, alerts) == {
        "transaction_count": 0,
        "success_rate": 0.0,
        "average_latency_ms": 0.0,
        "gateways": [],
        "active_alerts": [],
        "top_failure_transaction_type": None,
        "top_failure_device": None,
    }


def test_facts_fingerprint_is_stable_and_changes_with_metrics() -> None:
    facts = build_brief_facts(brief_transactions(), alert_snapshot())
    same_facts = dict(reversed(list(facts.items())))
    changed_facts = {**facts, "success_rate": 0.75}

    assert facts_fingerprint(facts) == facts_fingerprint(same_facts)
    assert facts_fingerprint(facts) != facts_fingerprint(changed_facts)
