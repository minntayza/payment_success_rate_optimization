"""Capacity-aware benchmark routing policies."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from payment_dashboard.routing_models import (
    AllocationResult,
    BucketAllocationResult,
    ObjectiveWeights,
)


def _utility(frame: pd.DataFrame, weights: ObjectiveWeights) -> pd.Series:
    return (
        weights.success_value * frame["expected_success_probability"]
        - weights.fee_weight * frame["expected_fee"]
        - weights.latency_weight * frame["expected_latency_ms"]
    )


def _allocate(
    candidates: pd.DataFrame,
    policy_name: str,
    ranker: Callable[[pd.DataFrame, int], pd.DataFrame],
) -> AllocationResult:
    bucket_results: list[BucketAllocationResult] = []
    for time_bucket, bucket_candidates in candidates.groupby("time_bucket", sort=True):
        remaining = {
            str(gateway_id): int(group["capacity"].iloc[0])
            for gateway_id, group in bucket_candidates.groupby("gateway_id")
        }
        bucket_decisions: list[pd.Series] = []
        ordered_ids = bucket_candidates.sort_values(["timestamp", "transaction_id"])[
            "transaction_id"
        ].drop_duplicates()
        failed_id: str | None = None
        for position, transaction_id in enumerate(ordered_ids):
            options = bucket_candidates.loc[
                bucket_candidates["transaction_id"].eq(transaction_id)
            ]
            options = options.loc[options["eligible"] & options["available"]]
            options = ranker(options.copy(), position)
            selected = None
            for _, candidate in options.iterrows():
                gateway_id = str(candidate["gateway_id"])
                if remaining[gateway_id] > 0:
                    selected = candidate
                    remaining[gateway_id] -= 1
                    break
            if selected is None:
                failed_id = str(transaction_id)
                break
            bucket_decisions.append(selected)
        if failed_id is not None:
            bucket_results.append(
                BucketAllocationResult(
                    pd.Timestamp(str(time_bucket)),
                    bucket_candidates.iloc[0:0].copy(),
                    len(ordered_ids),
                    tuple(ordered_ids.astype(str)),
                    False,
                    f"No feasible route for {failed_id}",
                )
            )
            continue
        bucket_frame = pd.DataFrame(bucket_decisions).reset_index(drop=True)
        usage = bucket_frame.groupby("gateway_id").size()
        capacities = bucket_candidates.groupby("gateway_id")["capacity"].first()
        binding = tuple(
            f"capacity:{gateway_id}"
            for gateway_id, count in usage.items()
            if int(count) == int(capacities[str(gateway_id)])
        )
        bucket_results.append(
            BucketAllocationResult(
                pd.Timestamp(str(time_bucket)),
                bucket_frame,
                len(ordered_ids),
                (),
                True,
                None,
                binding,
            )
        )
    feasible_frames = [
        result.decisions for result in bucket_results if result.is_feasible
    ]
    frame = (
        pd.concat(feasible_frames, ignore_index=True)
        if feasible_frames
        else candidates.iloc[0:0].copy()
    )
    objective = float(_utility(frame, ObjectiveWeights()).sum())
    feasible = all(result.is_feasible for result in bucket_results)
    return AllocationResult(
        policy_name,
        frame,
        objective,
        feasible,
        None if feasible else "one or more buckets are infeasible",
        tuple(bucket_results),
    )


def route_random(candidates: pd.DataFrame, seed: int = 42) -> AllocationResult:
    rng = np.random.default_rng(seed)
    return _allocate(
        candidates,
        "uniform_random",
        lambda frame, _: frame.iloc[rng.permutation(len(frame))],
    )


def route_round_robin(candidates: pd.DataFrame) -> AllocationResult:
    def rank(frame: pd.DataFrame, position: int) -> pd.DataFrame:
        ordered = frame.sort_values("gateway_id").reset_index(drop=True)
        return (
            pd.concat(
                [
                    ordered.iloc[position % len(ordered) :],
                    ordered.iloc[: position % len(ordered)],
                ]
            )
            if len(ordered)
            else ordered
        )

    return _allocate(candidates, "round_robin", rank)


def route_best_static(candidates: pd.DataFrame, gateway_id: str) -> AllocationResult:
    return _allocate(
        candidates,
        "best_static",
        lambda frame, _: (
            frame.assign(_rank=frame["gateway_id"].ne(gateway_id))
            .sort_values(["_rank", "gateway_id"])
            .drop(columns="_rank")
        ),
    )


def route_greedy_success(candidates: pd.DataFrame) -> AllocationResult:
    return _allocate(
        candidates,
        "greedy_success",
        lambda frame, _: frame.sort_values(
            ["expected_success_probability", "gateway_id"], ascending=[False, True]
        ),
    )
