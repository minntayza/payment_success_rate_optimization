"""Mixed-integer optimizer for synthetic gateway allocation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from payment_dashboard.routing_models import (
    AllocationResult,
    BucketAllocationResult,
    ObjectiveWeights,
)


def _optimize_bucket(
    candidates: pd.DataFrame,
    weights: ObjectiveWeights,
    fee_ceiling: float | None,
) -> BucketAllocationResult:
    bucket = pd.Timestamp(candidates["time_bucket"].iloc[0])
    ordered = candidates.sort_values(
        ["transaction_id", "gateway_id"], kind="stable"
    ).reset_index(drop=True)
    transaction_ids = tuple(ordered["transaction_id"].astype(str).unique())
    utility = (
        weights.success_value * ordered["expected_success_probability"]
        - weights.fee_weight * ordered["expected_fee"]
        - weights.latency_weight * ordered["expected_latency_ms"]
    ).to_numpy(float)
    transaction_groups = list(
        ordered.groupby("transaction_id", sort=False).indices.values()
    )
    capacity_groups = list(ordered.groupby("gateway_id", sort=False).indices.items())
    row_count = (
        len(transaction_groups)
        + len(capacity_groups)
        + (1 if fee_ceiling is not None else 0)
    )
    matrix = lil_matrix((row_count, len(ordered)), dtype=float)
    lower = np.full(row_count, -np.inf)
    upper = np.full(row_count, np.inf)
    row = 0
    for indices in transaction_groups:
        matrix[row, indices] = 1
        lower[row] = upper[row] = 1
        row += 1
    for _, indices in capacity_groups:
        matrix[row, indices] = 1
        upper[row] = float(str(ordered.loc[indices[0], "capacity"]))
        row += 1
    if fee_ceiling is not None:
        matrix[row, :] = ordered["expected_fee"].to_numpy(float)
        upper[row] = fee_ceiling
    allowed = (ordered["eligible"] & ordered["available"]).astype(float).to_numpy()
    result = milp(
        c=-utility + np.arange(len(ordered)) * 1e-10,
        integrality=np.ones(len(ordered), dtype=np.int32),
        bounds=Bounds(np.zeros(len(ordered)), allowed),
        constraints=LinearConstraint(matrix.tocsr(), lower, upper),
        options={"time_limit": 20},
    )
    if not result.success or result.x is None:
        diagnostic = (
            "infeasible" if result.status == 2 else f"solver failure: {result.message}"
        )
        return BucketAllocationResult(
            bucket,
            ordered.iloc[0:0].copy(),
            len(transaction_ids),
            transaction_ids,
            False,
            diagnostic,
        )
    decisions = ordered.loc[result.x >= 0.5].copy().reset_index(drop=True)
    if (
        len(decisions) != len(transaction_ids)
        or not decisions["transaction_id"].is_unique
    ):
        return BucketAllocationResult(
            bucket,
            ordered.iloc[0:0].copy(),
            len(transaction_ids),
            transaction_ids,
            False,
            "invalid solver allocation",
        )
    usage = decisions.groupby("gateway_id").size()
    capacities = ordered.groupby("gateway_id")["capacity"].first()
    binding = tuple(
        f"capacity:{gateway_id}"
        for gateway_id, count in usage.items()
        if int(count) == int(capacities[str(gateway_id)])
    )
    if fee_ceiling is not None and np.isclose(
        decisions["expected_fee"].sum(), fee_ceiling
    ):
        binding += ("fee_ceiling",)
    return BucketAllocationResult(
        bucket, decisions, len(transaction_ids), (), True, None, binding
    )


def optimize_routes(
    candidates: pd.DataFrame,
    weights: ObjectiveWeights,
    fee_ceiling: float | None = None,
) -> AllocationResult:
    bucket_results = tuple(
        _optimize_bucket(bucket_candidates, weights, fee_ceiling)
        for _, bucket_candidates in candidates.groupby("time_bucket", sort=True)
    )
    feasible_frames = [
        bucket.decisions for bucket in bucket_results if bucket.is_feasible
    ]
    decisions = (
        pd.concat(feasible_frames, ignore_index=True)
        if feasible_frames
        else candidates.iloc[0:0].copy()
    )
    objective = float(
        (
            weights.success_value * decisions["expected_success_probability"]
            - weights.fee_weight * decisions["expected_fee"]
            - weights.latency_weight * decisions["expected_latency_ms"]
        ).sum()
    )
    feasible = all(bucket.is_feasible for bucket in bucket_results)
    diagnostic = None if feasible else "one or more buckets are infeasible"
    return AllocationResult(
        "milp_optimizer",
        decisions,
        objective,
        feasible,
        diagnostic,
        bucket_results,
    )
