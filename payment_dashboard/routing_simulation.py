"""Generate public gateway candidates and separately held evaluation outcomes."""

from __future__ import annotations

import numpy as np
import pandas as pd

from payment_dashboard.routing_config import (
    GATEWAY_PROFILES,
    ROUTING_SIMULATION_VERSION,
    gateway_state,
)
from payment_dashboard.routing_models import RoutingBenchmark


def generate_routing_benchmark(
    contexts: pd.DataFrame, seed: int = 42
) -> RoutingBenchmark:
    ordered = contexts.sort_values(
        ["Timestamp", "Transaction ID"], kind="stable"
    ).copy()
    ordered["Timestamp"] = pd.to_datetime(ordered["Timestamp"], utc=True)
    rows: list[dict[str, object]] = []
    for _, transaction in ordered.iterrows():
        amount = float(transaction["Transaction Amount"])
        hour = transaction["Timestamp"].hour
        time_bucket = transaction["Timestamp"].floor("h")
        for profile in GATEWAY_PROFILES:
            state = gateway_state(time_bucket, profile.gateway_id)
            adjustment = 0.0
            if profile.gateway_id == "Gateway B" and 0 <= hour < 6:
                adjustment -= 0.09
            if (
                profile.gateway_id == "Gateway C"
                and transaction["Device Used"] == "Mobile"
            ):
                adjustment += 0.10
            if (
                profile.gateway_id == "Gateway D"
                and transaction["Transaction Type"] == "Transfer"
                and amount >= 500
            ):
                adjustment += 0.12
            if profile.gateway_id == "Gateway A" and amount > 1500:
                adjustment -= 0.06
            probability = float(
                np.clip(
                    profile.base_success + adjustment + state.success_adjustment,
                    0.50,
                    0.99,
                )
            )
            fee = profile.fixed_fee + amount * profile.percentage_fee / 100
            latency = profile.base_latency_ms * state.latency_multiplier
            eligible = not (profile.gateway_id == "Gateway C" and amount > 2500)
            rows.append(
                {
                    "transaction_id": str(transaction["Transaction ID"]),
                    "timestamp": transaction["Timestamp"],
                    "time_bucket": time_bucket,
                    "gateway_id": profile.gateway_id,
                    "eligible": eligible,
                    "available": state.available,
                    "capacity": state.capacity,
                    "expected_success_probability": probability,
                    "expected_fee": fee,
                    "expected_latency_ms": latency,
                    "is_degraded": not state.available,
                    "state_version": state.state_version,
                    "simulation_version": ROUTING_SIMULATION_VERSION,
                }
            )
    candidates = pd.DataFrame.from_records(rows)
    rng = np.random.default_rng(seed)
    outcomes = candidates[["transaction_id", "gateway_id"]].copy()
    outcomes["realized_success"] = (
        rng.random(len(candidates))
        < candidates["expected_success_probability"].to_numpy()
    )
    return RoutingBenchmark(ordered, candidates, outcomes, ROUTING_SIMULATION_VERSION)
