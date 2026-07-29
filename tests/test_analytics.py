from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from payment_dashboard.analytics import (
    add_latency_band,
    apply_filters,
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)


def prepared_fixture(sample_transactions):
    frame = sample_transactions.copy()
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"])
    frame["Bank Gateway"] = ["Gateway A", "Gateway A", "Gateway B", "Gateway B"]
    return frame


def test_latency_bands_use_documented_boundaries(sample_transactions):
    result = add_latency_band(prepared_fixture(sample_transactions))

    assert result["Latency Band"].astype("string").tolist() == [
        "0-5 ms",
        "11-15 ms",
        "6-10 ms",
        "16+ ms",
    ]


def test_summary_metrics(sample_transactions):
    metrics = summary_metrics(prepared_fixture(sample_transactions))

    assert metrics["p95_latency_ms"] == pytest.approx(18.8)
    assert metrics | {"p95_latency_ms": 18.8} == {
        "transaction_count": 4,
        "success_rate": 0.5,
        "failed_count": 2,
        "average_latency_ms": 11.0,
        "p95_latency_ms": 18.8,
    }


def test_summary_metrics_handles_empty_frame(sample_transactions):
    metrics = summary_metrics(prepared_fixture(sample_transactions).iloc[0:0])

    assert metrics == {
        "transaction_count": 0,
        "success_rate": 0.0,
        "failed_count": 0,
        "average_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
    }


def test_gateway_summary(sample_transactions):
    result = gateway_summary(prepared_fixture(sample_transactions)).set_index(
        "Bank Gateway"
    )

    assert result.loc["Gateway A", "transaction_count"] == 2
    assert result.loc["Gateway A", "success_rate"] == 0.5
    assert result.loc["Gateway B", "average_latency_ms"] == 14.0


def test_filters_can_return_empty_frame(sample_transactions):
    result = apply_filters(
        prepared_fixture(sample_transactions),
        gateways=["Gateway D"],
        transaction_types=[],
        devices=[],
        statuses=[],
        start=None,
        end=None,
    )

    assert result.empty


def test_filters_apply_categories_and_date_range(sample_transactions):
    frame = prepared_fixture(sample_transactions)
    frame.loc[0, "Timestamp"] = pd.Timestamp("2025-01-18 10:03:00")

    result = apply_filters(
        frame,
        gateways=["Gateway A"],
        transaction_types=["Deposit"],
        devices=["Desktop"],
        statuses=["Failed"],
        start=date(2025, 1, 17),
        end=date(2025, 1, 17),
    )

    assert result["Transaction ID"].tolist() == ["TX2"]


def test_failure_breakdown_counts_only_failures(sample_transactions):
    frame = add_latency_band(prepared_fixture(sample_transactions))
    result = failure_breakdown(frame, dimension="Latency Band")

    assert result["failed_count"].sum() == 2
    assert set(result["Latency Band"].astype("string")) == {"11-15 ms", "16+ ms"}


def test_success_rate_series_aggregates_time_buckets(sample_transactions):
    result = success_rate_series(
        prepared_fixture(sample_transactions),
        frequency="15min",
    )

    assert len(result) == 1
    assert result.iloc[0]["success_rate"] == 0.5
    assert result.iloc[0]["transaction_count"] == 4


def test_success_rate_series_handles_empty_frame(sample_transactions):
    result = success_rate_series(prepared_fixture(sample_transactions).iloc[0:0])

    assert list(result.columns) == [
        "Timestamp",
        "success_rate",
        "transaction_count",
    ]
    assert result.empty
