"""Generate public gateway candidates and separately held evaluation outcomes."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from payment_dashboard.routing_config import (
    BENCHMARK_TIMELINE_FREQUENCY,
    BENCHMARK_TIMELINE_START,
    BENCHMARK_TIMESTAMP_COLUMN,
    GATEWAY_PROFILES,
    ROUTING_SIMULATION_VERSION,
    gateway_state,
)
from payment_dashboard.routing_models import RoutingBenchmark


def _stable_uniform(seed: int, transaction_id: str, gateway_id: str) -> float:
    key = f"{ROUTING_SIMULATION_VERSION}\x1f{seed}\x1f{transaction_id}\x1f{gateway_id}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def add_benchmark_timestamps(contexts: pd.DataFrame) -> pd.DataFrame:
    """Add a deterministic synthetic timeline without replacing source time."""
    ordered = contexts.sort_values(
        ["Timestamp", "Transaction ID"], kind="stable"
    ).copy()
    ordered["Timestamp"] = pd.to_datetime(ordered["Timestamp"], utc=True)
    ordered[BENCHMARK_TIMESTAMP_COLUMN] = pd.date_range(
        start=BENCHMARK_TIMELINE_START,
        periods=len(ordered),
        freq=BENCHMARK_TIMELINE_FREQUENCY,
    )
    return ordered


def generate_routing_benchmark(
    contexts: pd.DataFrame, seed: int = 42
) -> RoutingBenchmark:
    ordered = add_benchmark_timestamps(contexts)
    rows: list[dict[str, object]] = []
    for _, transaction in ordered.iterrows():
        amount = float(transaction["Transaction Amount"])
        benchmark_timestamp = transaction[BENCHMARK_TIMESTAMP_COLUMN]
        hour = benchmark_timestamp.hour
        time_bucket = benchmark_timestamp.floor("h")
        for profile in GATEWAY_PROFILES:
            state = gateway_state(time_bucket, profile.gateway_id)
            adjustment = 0.0
            if profile.gateway_id == "Gateway B" and 0 <= hour < 6:
                adjustment -= 0.09
            if (
                profile.gateway_id == "Gateway C"
                and transaction["Device Used"] == "Mobile"
            ):
                eligible_amount = min(amount, 2_500.0)
                adjustment += 0.35 * eligible_amount / 2_500.0
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
                    "timestamp": benchmark_timestamp,
                    "source_timestamp": transaction["Timestamp"],
                    "time_bucket": time_bucket,
                    "gateway_id": profile.gateway_id,
                    "eligible": eligible,
                    "available": state.available,
                    "capacity": state.capacity,
                    "expected_success_probability": probability,
                    "expected_fee": fee,
                    "expected_latency_ms": latency,
                    "operational_state": state.operational_state,
                    "is_degraded": state.operational_state == "degraded",
                    "state_version": state.state_version,
                    "simulation_version": ROUTING_SIMULATION_VERSION,
                }
            )
    candidates = pd.DataFrame.from_records(rows)
    outcomes = candidates[["transaction_id", "gateway_id"]].copy()
    outcomes["realized_success"] = (
        np.fromiter(
            (
                _stable_uniform(seed, str(row.transaction_id), str(row.gateway_id))
                for row in candidates[["transaction_id", "gateway_id"]].itertuples(
                    index=False
                )
            ),
            dtype=float,
            count=len(candidates),
        )
        < candidates["expected_success_probability"].to_numpy()
    )
    return RoutingBenchmark(ordered, candidates, outcomes, ROUTING_SIMULATION_VERSION)
