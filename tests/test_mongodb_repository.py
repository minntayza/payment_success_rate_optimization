"""Contract tests for the MongoDB dashboard repository."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    ExecutionTimeout,
    OperationFailure,
)

from payment_dashboard import mongodb
from payment_dashboard.dashboard_repository import DashboardFilters, PageRequest
from payment_dashboard.models import DataSource


def _document(number: int) -> dict[str, object]:
    return {
        "transaction_id": f"TX-{number:03d}",
        "sender_account_id": "S1",
        "receiver_account_id": "R1",
        "transaction_amount": 25.5,
        "transaction_type": "Transfer",
        "transaction_timestamp": datetime(2025, 1, 17, 10, 0),
        "transaction_status": "Failed",
        "source_transaction_status": "Success",
        "simulation_version": "controlled-v1",
        "fraud_flag": False,
        "geolocation": "16.8,96.1",
        "device_used": "Mobile",
        "network_slice_id": "Slice1",
        "latency_ms": 12,
        "slice_bandwidth_mbps": 100,
        "pin_code": "0123",
        "bank_gateway": "Gateway A",
        "is_deleted": False,
    }


class Collection:
    """A bounded aggregate boundary double, not a Mongo implementation."""

    def __init__(self) -> None:
        self.aggregate_calls: list[list[dict[str, Any]]] = []
        self.created_indexes: list[tuple[tuple[str, int], ...]] = []
        self.find_called = False
        self.documents = [_document(number) for number in range(1, 76)]

    def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.aggregate_calls.append(pipeline)
        facet = next(stage["$facet"] for stage in pipeline if "$facet" in stage)
        page_pipeline = facet["transactions"]
        offset = next(stage["$skip"] for stage in page_pipeline if "$skip" in stage)
        limit = next(stage["$limit"] for stage in page_pipeline if "$limit" in stage)
        return [
            {
                "metrics": [
                    {
                        "transaction_count": 75,
                        "success_rate": 0.0,
                        "failed_count": 75,
                        "average_latency_ms": 12.0,
                        "p95_latency_ms": 12.0,
                    }
                ],
                "gateway_summary": [
                    {
                        "Bank Gateway": "Gateway A",
                        "transaction_count": 75,
                        "success_rate": 0.0,
                        "average_latency_ms": 12.0,
                    }
                ],
                "trend": [
                    {
                        "Timestamp": datetime(2025, 1, 17, 10, 0),
                        "success_rate": 0.0,
                        "transaction_count": 75,
                    }
                ],
                "failure_summary": [{"Latency Band": "11-15 ms", "failed_count": 75}],
                "alerts": [],
                "transactions": self.documents[offset : offset + limit],
                "total_count": [{"count": 75}],
                "metadata": [{"simulation_version": "controlled-v1"}],
            }
        ]

    def find(self, *_args: object, **_kwargs: object) -> None:
        self.find_called = True
        raise AssertionError("dashboard repository must not use find")

    def create_index(self, keys: list[tuple[str, int]], **_options: object) -> None:
        self.created_indexes.append(tuple(keys))


class Database(dict[str, Collection]):
    def __init__(self) -> None:
        super().__init__(transactions=Collection())


@pytest.fixture
def database() -> Database:
    return Database()


def test_mongo_repository_uses_aggregation_and_bounded_page(
    database: Database,
) -> None:
    """A live fetch cannot regress to an unbounded transaction cursor."""
    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(statuses=("Failed",)),
        PageRequest(number=2, size=50),
    )

    collection = database["transactions"]
    pipeline = collection.aggregate_calls[0]
    assert pipeline[0]["$match"] == {
        "is_deleted": {"$ne": True},
        "transaction_status": {"$in": ["Failed"]},
    }
    facet = next(stage["$facet"] for stage in pipeline if "$facet" in stage)
    assert {"$sort": {"transaction_timestamp": -1, "transaction_id": 1}} in facet[
        "transactions"
    ]
    assert {"$skip": 50} in facet["transactions"]
    assert {"$limit": 50} in facet["transactions"]
    assert snapshot.source is DataSource.LIVE
    assert collection.find_called is False
    assert len(snapshot.transactions) == 25
    assert snapshot.total_transactions == 75


def test_mongo_repository_translates_every_filter_to_match(database: Database) -> None:
    """Dropping a filter field from the Mongo match cannot leak unrelated rows."""
    mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(
            gateways=("Gateway A",),
            transaction_types=("Transfer",),
            devices=("Mobile",),
            statuses=("Failed",),
            start=date(2025, 1, 17),
            end=date(2025, 1, 18),
        ),
        PageRequest(number=1, size=1),
    )

    match = database["transactions"].aggregate_calls[0][0]["$match"]
    assert match == {
        "is_deleted": {"$ne": True},
        "bank_gateway": {"$in": ["Gateway A"]},
        "transaction_type": {"$in": ["Transfer"]},
        "device_used": {"$in": ["Mobile"]},
        "transaction_status": {"$in": ["Failed"]},
        "transaction_timestamp": {
            "$gte": datetime(2025, 1, 17),
            "$lt": datetime(2025, 1, 19),
        },
    }


def test_mongo_repository_returns_typed_snapshot_shapes(database: Database) -> None:
    """Aggregate rows must be converted to the shared dashboard contract."""
    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=1)
    )

    assert snapshot.metrics == {
        "transaction_count": 75,
        "success_rate": 0.0,
        "failed_count": 75,
        "average_latency_ms": 12.0,
        "p95_latency_ms": 12.0,
    }
    assert snapshot.transactions["Transaction ID"].tolist() == ["TX-001"]
    assert snapshot.transactions["Latency Band"].astype("string").tolist() == [
        "11-15 ms"
    ]
    assert snapshot.simulation_version == "controlled-v1"
    assert snapshot.diagnostic is None
    assert list(snapshot.gateway_summary.columns) == [
        "Bank Gateway",
        "transaction_count",
        "success_rate",
        "average_latency_ms",
    ]
    assert list(snapshot.trend.columns) == [
        "Timestamp",
        "success_rate",
        "transaction_count",
    ]
    assert list(snapshot.failure_summary.columns) == [
        "Latency Band",
        "failed_count",
    ]


def test_indexes_cover_dashboard_queries(database: Database) -> None:
    """Index drift cannot leave the active timestamp query unsupported."""
    mongodb.ensure_indexes(database)

    indexes = database["transactions"].created_indexes
    assert (("is_deleted", 1), ("transaction_timestamp", -1)) in indexes
    assert (
        ("is_deleted", 1),
        ("bank_gateway", 1),
        ("transaction_status", 1),
        ("transaction_timestamp", -1),
    ) in indexes
    assert (
        ("is_deleted", 1),
        ("transaction_type", 1),
        ("device_used", 1),
        ("transaction_timestamp", -1),
    ) in indexes


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ConfigurationError("private detail"), "configuration"),
        (ConnectionFailure("private detail"), "connection"),
        (ExecutionTimeout("private detail"), "timeout"),
        (OperationFailure("private detail"), "query"),
    ],
)
def test_mongodb_error_categories_never_expose_exception_details(
    error: Exception,
    category: str,
) -> None:
    """Diagnostics stay from a fixed safe vocabulary, not exception text."""
    assert mongodb.classify_mongodb_error(error) == category
