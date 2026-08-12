"""Typed contracts for the synthetic routing benchmark."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    success_value: float = 100.0
    fee_weight: float = 1.0
    latency_weight: float = 0.01

    def __post_init__(self) -> None:
        if min(self.success_value, self.fee_weight, self.latency_weight) < 0:
            raise ValueError("Objective weights must be non-negative")


@dataclass(frozen=True, slots=True)
class RoutingBenchmark:
    contexts: pd.DataFrame
    candidates: pd.DataFrame
    potential_outcomes: pd.DataFrame
    simulation_version: str

    def __post_init__(self) -> None:
        candidates = self.candidates.copy(deep=True)
        outcomes = self.potential_outcomes.copy(deep=True)
        contexts = self.contexts.copy(deep=True)
        if "realized_success" in candidates:
            raise ValueError("Policy candidates must not contain realized_success")
        candidate_key = ["transaction_id", "gateway_id"]
        if candidates.duplicated(candidate_key).any():
            raise ValueError("Routing candidate keys must be unique")
        if outcomes.duplicated(candidate_key).any():
            raise ValueError("Potential outcome keys must be unique")
        if set(map(tuple, candidates[candidate_key].to_numpy())) != set(
            map(tuple, outcomes[candidate_key].to_numpy())
        ):
            raise ValueError("Candidate and outcome keys must match exactly")
        counts = candidates.groupby("transaction_id")["gateway_id"].nunique()
        if counts.empty or not counts.eq(4).all():
            raise ValueError("Every transaction must have four candidate gateways")
        if not candidates["expected_success_probability"].between(0, 1).all():
            raise ValueError("Expected success probabilities must be within [0, 1]")
        if (candidates[["expected_fee", "expected_latency_ms"]] < 0).any().any():
            raise ValueError("Expected fees and latency must be non-negative")
        if (candidates["capacity"] <= 0).any():
            raise ValueError("Gateway capacity must be positive")
        object.__setattr__(self, "contexts", contexts)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "potential_outcomes", outcomes)


@dataclass(frozen=True, slots=True)
class BucketAllocationResult:
    time_bucket: pd.Timestamp
    decisions: pd.DataFrame
    transaction_count: int
    unassigned_ids: tuple[str, ...]
    is_feasible: bool
    diagnostic: str | None = None
    binding_constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AllocationResult:
    policy_name: str
    decisions: pd.DataFrame
    objective_value: float
    is_feasible: bool
    diagnostic: str | None = None
    bucket_results: tuple[BucketAllocationResult, ...] = ()

    @property
    def infeasible_bucket_count(self) -> int:
        return sum(not bucket.is_feasible for bucket in self.bucket_results)

    @property
    def unassigned_count(self) -> int:
        return sum(len(bucket.unassigned_ids) for bucket in self.bucket_results)

    @property
    def capacity_binding_bucket_count(self) -> int:
        return sum(bool(bucket.binding_constraints) for bucket in self.bucket_results)


@dataclass(frozen=True, slots=True)
class PolicyMetrics:
    transaction_count: int
    assigned_count: int
    unassigned_count: int
    successful_count: int
    success_rate: float
    total_fee: float
    cost_per_success: float | None
    average_latency_ms: float
    p95_latency_ms: float
    expected_utility: float
    realized_utility: float
    capacity_violation_count: int
    eligibility_violation_count: int
    availability_violation_count: int
    feasible_bucket_count: int
    infeasible_bucket_count: int
    degraded_transaction_count: int
    degraded_success_rate: float | None
    normal_success_rate: float | None


@dataclass(frozen=True, slots=True)
class WeightSelection:
    selected: ObjectiveWeights
    validation_scores: tuple[tuple[ObjectiveWeights, float], ...]


@dataclass(frozen=True, slots=True)
class OptimizationReport:
    metrics: dict[str, PolicyMetrics]
    decisions: dict[str, pd.DataFrame]
    comparison: pd.DataFrame
    split_boundaries: dict[str, tuple[pd.Timestamp, pd.Timestamp]]
    weights: ObjectiveWeights
    simulation_version: str
    capacity_binding_bucket_count: int = 0
    infeasible_bucket_count: int = 0
    unassigned_count: int = 0
    weight_selection: WeightSelection | None = None
    confidence_intervals: Mapping[str, object] | None = None
    run_id: str = "unpersisted"
    source_label: str = "independent local benchmark"
