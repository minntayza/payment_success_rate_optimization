"""Opt-in AI provider contract checks that never run in the default suite."""

from __future__ import annotations

import os

import pytest

from payment_dashboard.ai_brief import generate_brief_result

MINIMAL_FACTS: dict[str, object] = {
    "transaction_count": 2,
    "success_rate": 0.5,
    "failed_count": 1,
    "average_latency_ms": 20.0,
    "p95_latency_ms": 25.0,
    "gateways": [],
    "active_alerts": [],
    "top_failure_latency_band": {"name": "Low", "failures": 1},
}


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_AI_TESTS") != "1", reason="live AI disabled")
def test_live_ai_contract() -> None:
    """Configured provider returns a validated AI-origin brief within one attempt."""
    result = generate_brief_result(
        MINIMAL_FACTS,
        timeout=10,
        attempts=1,
        max_tokens=128,
    )

    assert result.origin == "ai"
