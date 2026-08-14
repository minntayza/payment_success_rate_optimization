"""Versioned assumptions for the synthetic routing benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

ROUTING_SIMULATION_VERSION = "routing-benchmark-v4"
ROUTING_STATE_VERSION = "gateway-state-v3"
ROUTING_TIMELINE_VERSION = "benchmark-timeline-v1"
BENCHMARK_TIMESTAMP_COLUMN = "Benchmark Timestamp"
BENCHMARK_TIMELINE_START = "2025-01-01T00:00:00Z"
BENCHMARK_TIMELINE_FREQUENCY = "60s"


@dataclass(frozen=True, slots=True)
class GatewayProfile:
    gateway_id: str
    base_success: float
    fixed_fee: float
    percentage_fee: float
    base_latency_ms: float
    hourly_capacity: int


@dataclass(frozen=True, slots=True)
class GatewayState:
    operational_state: Literal["normal", "degraded", "unavailable"]
    available: bool
    capacity: int
    success_adjustment: float
    latency_multiplier: float
    state_version: str


GATEWAY_PROFILES = (
    GatewayProfile("Gateway A", 0.94, 0.40, 0.018, 85, 25),
    GatewayProfile("Gateway B", 0.90, 0.22, 0.014, 42, 37),
    GatewayProfile("Gateway C", 0.87, 0.10, 0.010, 65, 10),
    GatewayProfile("Gateway D", 0.86, 0.28, 0.012, 105, 47),
)

DEFAULT_WEIGHT_GRID = (
    (100.0, 0.5, 0.005),
    (100.0, 1.0, 0.01),
    (100.0, 2.0, 0.02),
)

GATEWAY_UNAVAILABLE_HOURS_UTC: dict[str, frozenset[int]] = {
    "Gateway A": frozenset({4, 10, 16, 22}),
    "Gateway B": frozenset(),
    "Gateway C": frozenset({7, 19}),
    "Gateway D": frozenset(),
}

GATEWAY_DEGRADED_HOURS_UTC: dict[str, frozenset[int]] = {
    "Gateway A": frozenset({3, 9, 15, 21}),
    "Gateway B": frozenset({2, 14}),
    "Gateway C": frozenset({1, 13}),
    "Gateway D": frozenset({6, 18}),
}


def gateway_state(bucket: pd.Timestamp, gateway_id: str) -> GatewayState:
    """Return stable, versioned gateway state for one complete UTC hour."""
    profiles = {profile.gateway_id: profile for profile in GATEWAY_PROFILES}
    try:
        profile = profiles[gateway_id]
    except KeyError as exc:
        raise ValueError(f"Unknown gateway: {gateway_id}") from exc
    utc_bucket = pd.Timestamp(bucket)
    if utc_bucket.tzinfo is None:
        utc_bucket = utc_bucket.tz_localize("UTC")
    else:
        utc_bucket = utc_bucket.tz_convert("UTC")
    unavailable = utc_bucket.hour in GATEWAY_UNAVAILABLE_HOURS_UTC[gateway_id]
    degraded = utc_bucket.hour in GATEWAY_DEGRADED_HOURS_UTC[gateway_id]
    operational_state: Literal["normal", "degraded", "unavailable"] = (
        "unavailable" if unavailable else "degraded" if degraded else "normal"
    )
    return GatewayState(
        operational_state=operational_state,
        available=not unavailable,
        capacity=(
            0
            if unavailable
            else max(1, int(profile.hourly_capacity * 0.6))
            if degraded
            else profile.hourly_capacity
        ),
        success_adjustment=-0.08 if degraded else -0.20 if unavailable else 0.0,
        latency_multiplier=1.5 if degraded else 2.0 if unavailable else 1.0,
        state_version=ROUTING_STATE_VERSION,
    )
