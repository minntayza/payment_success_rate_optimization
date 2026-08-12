"""Contract tests for the MongoDB dashboard repository."""

from __future__ import annotations

import warnings
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pytest
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    ExecutionTimeout,
    OperationFailure,
)

from payment_dashboard import mongodb
from payment_dashboard.analytics import (
    add_latency_band,
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)
from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)
from payment_dashboard.models import DataSource


def _document(
    transaction_id: str,
    *,
    timestamp: datetime | None = None,
    status: str = "Success",
    gateway: str = "Gateway A",
    latency: float = 12,
    simulation_version: str | None = "controlled-v1",
    is_deleted: bool = False,
) -> dict[str, object]:
    document: dict[str, object] = {
        "transaction_id": transaction_id,
        "sender_account_id": "S1",
        "receiver_account_id": "R1",
        "transaction_amount": 25.5,
        "transaction_type": "Transfer",
        "transaction_timestamp": timestamp or datetime(2025, 1, 17, 10, 0),
        "transaction_status": status,
        "source_transaction_status": "Success",
        "fraud_flag": False,
        "geolocation": "16.8,96.1",
        "device_used": "Mobile",
        "network_slice_id": "Slice1",
        "latency_ms": latency,
        "slice_bandwidth_mbps": 100,
        "pin_code": "0123",
        "bank_gateway": gateway,
        "is_deleted": is_deleted,
    }
    if simulation_version is not None:
        document["simulation_version"] = simulation_version
    return document


def _matches(document: dict[str, object], match: dict[str, object]) -> bool:
    for field, condition in match.items():
        value = document.get(field)
        if not isinstance(condition, dict):
            if value != condition:
                return False
            continue
        if "$ne" in condition and value == condition["$ne"]:
            return False
        if "$in" in condition and value not in condition["$in"]:
            return False
        if "$gte" in condition and value < condition["$gte"]:
            return False
        if "$lt" in condition and value >= condition["$lt"]:
            return False
    return True


def _frame(documents: list[dict[str, object]]) -> pd.DataFrame:
    if documents:
        return add_latency_band(mongodb.documents_to_frame(documents))
    frame = pd.DataFrame(
        {column: pd.Series(dtype="object") for column in mongodb.COLUMN_MAP.values()}
    )
    frame["Timestamp"] = pd.Series(dtype="datetime64[ns]")
    frame["Latency (ms)"] = pd.Series(dtype="float64")
    return add_latency_band(frame)


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return frame.to_dict(orient="records")


def _branch_match(branch: list[dict[str, Any]]) -> dict[str, object]:
    if branch and "$match" in branch[0]:
        return branch[0]["$match"]
    return {}


def _metadata(
    documents: list[dict[str, object]],
    branch: list[dict[str, Any]],
) -> list[dict[str, object]]:
    selected = list(documents)
    for stage in branch:
        if "$match" in stage:
            selected = [item for item in selected if _matches(item, stage["$match"])]
        elif "$sort" in stage:
            fields = list(stage["$sort"])
            selected.sort(key=lambda item: tuple(item.get(field) for field in fields))
        elif "$limit" in stage:
            selected = selected[: stage["$limit"]]
    if not selected:
        return []
    return [
        {
            "simulation_version": selected[0].get(
                "simulation_version", mongodb.LEGACY_SIMULATION_VERSION
            )
        }
    ]


class SemanticCollection:
    """Apply the repository's query boundary to controlled in-memory documents."""

    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents
        self.aggregate_calls: list[list[dict[str, Any]]] = []
        self.created_indexes: list[tuple[tuple[str, int], ...]] = []
        self.find_called = False

    def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.aggregate_calls.append(pipeline)
        matched = [
            item for item in self.documents if _matches(item, pipeline[0]["$match"])
        ]
        facet = pipeline[1]["$facet"]
        result: dict[str, object] = {}
        if "transactions" in facet:
            display_match = _branch_match(facet["transactions"])
            display = [item for item in matched if _matches(item, display_match)]
            display_frame = _frame(display)
            page_branch = facet["transactions"]
            display.sort(
                key=lambda item: (
                    -item["transaction_timestamp"].timestamp(),
                    item["transaction_id"],
                )
            )
            offset = next(stage["$skip"] for stage in page_branch if "$skip" in stage)
            limit = next(stage["$limit"] for stage in page_branch if "$limit" in stage)
            result.update(
                {
                    "metrics": [summary_metrics(display_frame)] if display else [],
                    "gateway_summary": _records(gateway_summary(display_frame)),
                    "trend": _records(success_rate_series(display_frame)),
                    "failure_summary": _records(
                        failure_breakdown(display_frame, dimension="Latency Band")
                    ),
                    "transactions": display[offset : offset + limit],
                    "total_count": [{"count": len(display)}] if display else [],
                }
            )
        if "alerts" in facet:
            alert_match = _branch_match(facet["alerts"])
            history = [item for item in matched if _matches(item, alert_match)]
            result.update(
                {
                    "alerts": _alert_records(history, facet["alerts"]),
                    "metadata": _metadata(matched, facet["metadata"]),
                }
            )
        return [result]

    def find(self, *_args: object, **_kwargs: object) -> None:
        self.find_called = True
        raise AssertionError("dashboard repository must not use find")

    def create_index(self, keys: list[tuple[str, int]], **_options: object) -> None:
        self.created_indexes.append(tuple(keys))


class Database(dict[str, SemanticCollection]):
    def __init__(self, documents: list[dict[str, object]]) -> None:
        super().__init__(transactions=SemanticCollection(documents))


def test_repository_uses_injected_collection_name() -> None:
    """A live contract can query an isolated collection instead of production."""
    isolated = SemanticCollection([])
    database = {"dashboard_contract_test": isolated}

    snapshot = mongodb.MongoDashboardRepository(
        database, collection_name="dashboard_contract_test"
    ).fetch(DashboardFilters(), PageRequest(number=1, size=1))

    assert snapshot.source is DataSource.LIVE
    assert len(isolated.aggregate_calls) == 2


def _operators(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            key
            for name, child in value.items()
            for key in ({name} if name.startswith("$") else set()) | _operators(child)
        }
    if isinstance(value, list):
        return {operator for child in value for operator in _operators(child)}
    return set()


def _operand(value: object, operator: str, left: str) -> int | float:
    if isinstance(value, dict):
        for name, child in value.items():
            if (
                name == operator
                and isinstance(child, list)
                and len(child) == 2
                and child[0] == left
            ):
                return child[1]
            try:
                return _operand(child, operator, left)
            except LookupError:
                pass
    elif isinstance(value, list):
        for child in value:
            try:
                return _operand(child, operator, left)
            except LookupError:
                pass
    raise LookupError((operator, left))


def _alert_records(
    documents: list[dict[str, object]],
    branch: list[dict[str, Any]],
) -> list[dict[str, object]]:
    window_size = int(branch[0]["$group"]["latest_statuses"]["$topN"]["n"])
    threshold = float(_operand(branch, "$gte", "$drop"))
    rounds_drop = "$round" in _operators(branch)
    records = []
    for gateway in sorted({str(item["bank_gateway"]) for item in documents}):
        rows = sorted(
            (item for item in documents if item["bank_gateway"] == gateway),
            key=lambda item: (item["transaction_timestamp"], item["transaction_id"]),
        )
        baseline = sum(item["transaction_status"] == "Success" for item in rows) / len(
            rows
        )
        sufficient = len(rows) >= window_size
        rolling_rate = (
            sum(item["transaction_status"] == "Success" for item in rows[-window_size:])
            / window_size
            if sufficient
            else float("nan")
        )
        drop = baseline - rolling_rate if sufficient else float("nan")
        if sufficient and rounds_drop:
            drop = round(drop, 12)
        records.append(
            {
                "Bank Gateway": gateway,
                "baseline_rate": baseline,
                "rolling_rate": rolling_rate,
                "drop": drop,
                "has_sufficient_history": sufficient,
                "is_alert": sufficient and drop >= threshold,
            }
        )
    return records


def test_display_filters_precede_facet_while_history_stays_active_only() -> None:
    """Mongo can use display indexes without narrowing alerts or metadata."""
    database = Database([_document("TX-1", status="Failed")])

    mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(statuses=("Failed",)), PageRequest(number=2, size=50)
    )

    collection = database["transactions"]
    assert len(collection.aggregate_calls) == 2
    display_pipeline, history_pipeline = collection.aggregate_calls
    assert display_pipeline[0] == {
        "$match": {
            "is_deleted": False,
            "transaction_status": {"$in": ["Failed"]},
        }
    }
    assert set(display_pipeline[1]["$facet"]) == {
        "metrics",
        "gateway_summary",
        "trend",
        "failure_summary",
        "transactions",
        "total_count",
    }
    assert history_pipeline[0] == {"$match": {"is_deleted": False}}
    assert set(history_pipeline[1]["$facet"]) == {"alerts", "metadata"}
    facet = display_pipeline[1]["$facet"]
    assert {"$sort": {"transaction_timestamp": -1, "transaction_id": 1}} in facet[
        "transactions"
    ]
    assert {"$skip": 50} in facet["transactions"]
    assert {"$limit": 50} in facet["transactions"]
    assert collection.find_called is False


def test_filtered_page_preserves_timestamp_descending_id_ascending_order() -> None:
    """Frame conversion cannot reverse the stable order produced by MongoDB."""
    later = datetime(2025, 1, 17, 11, 0)
    earlier = datetime(2025, 1, 17, 10, 0)
    database = Database(
        [
            _document("TX-B", timestamp=later),
            _document("TX-C", timestamp=earlier),
            _document("TX-A", timestamp=later),
        ]
    )

    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=3)
    )

    assert snapshot.transactions["Transaction ID"].tolist() == [
        "TX-A",
        "TX-B",
        "TX-C",
    ]


def test_soft_deleted_documents_are_excluded_from_every_result() -> None:
    """A soft-deleted row cannot contribute to counts, pages, or history."""
    database = Database(
        [
            _document("TX-ACTIVE"),
            _document("TX-DELETED", status="Failed", is_deleted=True),
        ]
    )

    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=10)
    )

    assert snapshot.total_transactions == 1
    assert snapshot.metrics["transaction_count"] == 1
    assert snapshot.transactions["Transaction ID"].tolist() == ["TX-ACTIVE"]
    gateway_a = snapshot.alerts.set_index("Bank Gateway").loc["Gateway A"]
    assert gateway_a["baseline_rate"] == 1.0


def test_alerts_use_full_active_history_and_include_configured_gateways() -> None:
    """Display status filters cannot alter an exact-threshold alert decision."""
    start = datetime(2025, 1, 17)
    documents = [
        _document(f"TX-{number:03d}", timestamp=start + timedelta(minutes=number))
        for number in range(50)
    ]
    documents.extend(
        _document(
            f"TX-{number:03d}",
            timestamp=start + timedelta(minutes=number),
            status="Success" if number < 90 else "Failed",
        )
        for number in range(50, 100)
    )
    database = Database(documents)

    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(statuses=("Failed",)), PageRequest(number=1, size=10)
    )

    assert snapshot.total_transactions == 10
    assert snapshot.alerts["Bank Gateway"].tolist() == [
        "Gateway A",
        "Gateway B",
        "Gateway C",
        "Gateway D",
    ]
    gateway_a = snapshot.alerts.set_index("Bank Gateway").loc["Gateway A"]
    assert gateway_a["drop"] == 0.1
    assert bool(gateway_a["is_alert"]) is True


def test_alert_cutoff_prefers_highest_transaction_ids_when_timestamps_tie() -> None:
    timestamp = datetime(2025, 1, 17, 10, 0)
    documents = [
        _document(
            f"TX-{number:03d}",
            timestamp=timestamp,
            status="Success" if number < 10 else "Failed",
        )
        for number in range(60)
    ]
    database = Database(documents)

    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=10)
    )

    gateway_a = snapshot.alerts.set_index("Bank Gateway").loc["Gateway A"]
    assert gateway_a["rolling_rate"] == 0.0
    alert_pipeline = database["transactions"].aggregate_calls[1][1]["$facet"]["alerts"]
    assert "$documentNumber" not in _operators(alert_pipeline)
    assert alert_pipeline[0]["$group"]["latest_statuses"]["$topN"] == {
        "sortBy": {"transaction_timestamp": -1, "transaction_id": -1},
        "output": "$transaction_status",
        "n": mongodb.ALERT_WINDOW_SIZE,
    }


def test_alert_pipeline_excludes_recent_window_and_requires_reference_minimum() -> None:
    pipeline = mongodb._alerts_pipeline()
    serialized = repr(pipeline)
    assert "baseline_success_count" in serialized
    assert "baseline_count" in serialized
    assert "$subtract" in serialized
    assert str(mongodb.ALERT_BASELINE_MIN_SIZE) in serialized


def test_document_number_window_uses_atlas_compatible_single_sort_key() -> None:
    """Atlas rejects $documentNumber when sortBy has multiple fields."""
    database = Database([_document("TX-1")])

    mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=1)
    )

    metrics = database["transactions"].aggregate_calls[0][1]["$facet"]["metrics"]
    document_number_windows = [
        stage["$setWindowFields"]
        for stage in metrics
        if "$setWindowFields" in stage
        and "$documentNumber" in _operators(stage["$setWindowFields"])
    ]
    assert document_number_windows
    assert all(len(window["sortBy"]) == 1 for window in document_number_windows)


def test_metadata_is_deterministic_and_independent_of_display_filters() -> None:
    """The oldest active source version wins even when that row is filtered out."""
    database = Database(
        [
            _document(
                "TX-NEW",
                timestamp=datetime(2025, 1, 18),
                status="Failed",
                simulation_version="controlled-v1",
            ),
            _document(
                "TX-OLD",
                timestamp=datetime(2025, 1, 17),
                status="Success",
                simulation_version=None,
            ),
        ]
    )

    snapshot = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(statuses=("Failed",)), PageRequest(number=1, size=10)
    )

    assert snapshot.transactions["Transaction ID"].tolist() == ["TX-NEW"]
    assert snapshot.simulation_version == "legacy-v0"
    metadata = database["transactions"].aggregate_calls[1][1]["$facet"]["metadata"]
    assert metadata[0] == {"$sort": {"transaction_timestamp": 1, "transaction_id": 1}}


def test_empty_live_result_returns_complete_bounded_snapshot() -> None:
    """An empty active collection still returns every typed snapshot field."""
    snapshot = mongodb.MongoDashboardRepository(Database([])).fetch(
        DashboardFilters(), PageRequest(number=1, size=10)
    )

    assert snapshot.source is DataSource.LIVE
    assert snapshot.total_transactions == 0
    assert snapshot.metrics == {
        "transaction_count": 0,
        "success_rate": 0.0,
        "failed_count": 0,
        "average_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
    }
    assert snapshot.transactions.empty
    assert snapshot.simulation_version == "legacy-v0"
    assert snapshot.alerts["Bank Gateway"].tolist() == [
        "Gateway A",
        "Gateway B",
        "Gateway C",
        "Gateway D",
    ]


def test_missing_gateway_alert_rows_do_not_emit_dtype_warnings() -> None:
    """Filling bounded configured-gateway rows must preserve boolean dtype cleanly."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        snapshot = mongodb.MongoDashboardRepository(
            Database([_document("TX-1")])
        ).fetch(DashboardFilters(), PageRequest(number=1, size=1))

    assert snapshot.alerts["is_alert"].dtype == bool


def test_mongo_p95_matches_pandas_exact_linear_quantile() -> None:
    """Live p95 cannot drift from the exact shared repository definition."""
    latencies = [1, 2, 3, 4, 100]
    documents = [
        _document(f"TX-{index}", latency=latency)
        for index, latency in enumerate(latencies)
    ]
    database = Database(documents)
    frame = mongodb.documents_to_frame(documents)

    live = mongodb.MongoDashboardRepository(database).fetch(
        DashboardFilters(), PageRequest(number=1, size=5)
    )
    demo = PandasDashboardRepository(frame).fetch(
        DashboardFilters(), PageRequest(number=1, size=5)
    )

    assert live.metrics["p95_latency_ms"] == pytest.approx(80.8)
    assert live.metrics["p95_latency_ms"] == demo.metrics["p95_latency_ms"]
    metrics = database["transactions"].aggregate_calls[0][1]["$facet"]["metrics"]
    assert "$percentile" not in _operators(metrics)
    assert "$setWindowFields" in _operators(metrics)


def test_date_and_dimension_filters_share_one_display_match() -> None:
    """Every selectable filter is applied identically to all display facets."""
    database = Database([_document("TX-1")])
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

    display_match = database["transactions"].aggregate_calls[0][0]["$match"]
    assert display_match == {
        "is_deleted": False,
        "bank_gateway": {"$in": ["Gateway A"]},
        "transaction_type": {"$in": ["Transfer"]},
        "device_used": {"$in": ["Mobile"]},
        "transaction_status": {"$in": ["Failed"]},
        "transaction_timestamp": {
            "$gte": datetime(2025, 1, 17),
            "$lt": datetime(2025, 1, 19),
        },
    }


def test_indexes_cover_independently_selectable_filters() -> None:
    """Status-only and device-only queries must have usable index prefixes."""
    database = Database([])
    mongodb.ensure_indexes(database)

    indexes = database["transactions"].created_indexes
    assert (("is_deleted", 1), ("transaction_timestamp", -1)) in indexes
    assert (
        ("is_deleted", 1),
        ("transaction_status", 1),
        ("transaction_timestamp", -1),
    ) in indexes
    assert (
        ("is_deleted", 1),
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
