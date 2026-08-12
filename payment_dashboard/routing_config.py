"""Versioned assumptions for the synthetic routing benchmark."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

ROUTING_SIMULATION_VERSION = "routing-benchmark-v1"
ROUTING_STATE_VERSION = "gateway-state-v1"


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
    available: bool
    capacity: int
    success_adjustment: float
    latency_multiplier: float
    state_version: str


GATEWAY_PROFILES = (
    GatewayProfile("Gateway A", 0.94, 0.40, 0.018, 85, 80),
    GatewayProfile("Gateway B", 0.90, 0.22, 0.014, 42, 120),
    GatewayProfile("Gateway C", 0.87, 0.10, 0.010, 65, 100),
    GatewayProfile("Gateway D", 0.86, 0.28, 0.012, 105, 150),
)

DEFAULT_WEIGHT_GRID = (
    (100.0, 0.5, 0.005),
    (100.0, 1.0, 0.01),
    (100.0, 2.0, 0.02),
)

GATEWAY_INCIDENT_HOURS_UTC: dict[str, frozenset[int]] = {
    "Gateway A": frozenset({4, 10, 16, 22}),
    "Gateway B": frozenset(),
    "Gateway C": frozenset({7, 19}),
    "Gateway D": frozenset(),
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
    degraded = utc_bucket.hour in GATEWAY_INCIDENT_HOURS_UTC[gateway_id]
    return GatewayState(
        available=not degraded,
        capacity=profile.hourly_capacity,
        success_adjustment=-0.20 if degraded else 0.0,
        latency_multiplier=2.0 if degraded else 1.0,
        state_version=ROUTING_STATE_VERSION,
    )
