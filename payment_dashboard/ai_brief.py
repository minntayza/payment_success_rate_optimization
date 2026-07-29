"""Aggregate dashboard facts and generate an operations brief locally."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import pandas as pd

from payment_dashboard.analytics import (
    failure_breakdown,
    gateway_summary,
    summary_metrics,
)


def _top_failure(
    frame: pd.DataFrame,
    dimension: str,
) -> dict[str, object] | None:
    breakdown = failure_breakdown(frame, dimension)
    if breakdown.empty:
        return None
    row = breakdown.iloc[0]
    return {"name": str(row[dimension]), "failures": int(row["failed_count"])}


def build_brief_facts(
    frame: pd.DataFrame,
    alerts: pd.DataFrame,
) -> dict[str, object]:
    """Return model-safe aggregate facts for the current dashboard view."""
    if frame.empty:
        return {
            "transaction_count": 0,
            "success_rate": 0.0,
            "average_latency_ms": 0.0,
            "gateways": [],
            "active_alerts": [],
            "top_failure_transaction_type": None,
            "top_failure_device": None,
        }

    metrics = summary_metrics(frame)
    gateways = [
        {
            "name": str(row["Bank Gateway"]),
            "transactions": int(row["transaction_count"]),
            "success_rate": float(row["success_rate"]),
        }
        for _, row in gateway_summary(frame).iterrows()
    ]
    active_alerts = sorted(
        alerts.loc[alerts["is_alert"], "Bank Gateway"].astype(str).tolist()
    )
    return {
        "transaction_count": int(metrics["transaction_count"]),
        "success_rate": float(metrics["success_rate"]),
        "average_latency_ms": float(metrics["average_latency_ms"]),
        "gateways": gateways,
        "active_alerts": active_alerts,
        "top_failure_transaction_type": _top_failure(frame, "Transaction Type"),
        "top_failure_device": _top_failure(frame, "Device Used"),
    }


def facts_fingerprint(facts: Mapping[str, object]) -> str:
    """Return a deterministic fingerprint for aggregate model inputs."""
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
