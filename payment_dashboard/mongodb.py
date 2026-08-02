"""MongoDB Atlas adapter for the dashboard's DataFrame contract."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal

import pandas as pd
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from payment_dashboard.analytics import add_latency_band
from payment_dashboard.config import (
    ALERT_THRESHOLD,
    ALERT_WINDOW_SIZE,
    FAILED_STATUS,
    GATEWAYS,
    P95_QUANTILE,
    SUCCESS_STATUS,
)
from payment_dashboard.dashboard_repository import DashboardFilters, PageRequest
from payment_dashboard.data_loader import validate_transactions
from payment_dashboard.models import DashboardSnapshot, DataSource

LOGGER = logging.getLogger(__name__)
LEGACY_SIMULATION_VERSION = "legacy-v0"

COLUMN_MAP = {
    "transaction_id": "Transaction ID",
    "sender_account_id": "Sender Account ID",
    "receiver_account_id": "Receiver Account ID",
    "transaction_amount": "Transaction Amount",
    "transaction_type": "Transaction Type",
    "transaction_timestamp": "Timestamp",
    "transaction_status": "Transaction Status",
    "source_transaction_status": "Source Transaction Status",
    "simulation_version": "Simulation Version",
    "fraud_flag": "Fraud Flag",
    "geolocation": "Geolocation (Latitude/Longitude)",
    "device_used": "Device Used",
    "network_slice_id": "Network Slice ID",
    "latency_ms": "Latency (ms)",
    "slice_bandwidth_mbps": "Slice Bandwidth (Mbps)",
    "pin_code": "PIN Code",
    "bank_gateway": "Bank Gateway",
}


@dataclass(frozen=True, slots=True)
class MongoResources:
    client: Any
    database: Any


@dataclass(frozen=True, slots=True)
class DatabaseResult:
    frame: pd.DataFrame
    source: Literal["mongodb", "fallback"]
    message: str | None = None


def create_resources_from_env() -> MongoResources | None:
    """Connect to configured Atlas resources with short failure timeouts."""
    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DATABASE")
    if not uri or not database_name:
        return None
    try:
        from pymongo import MongoClient
    except ImportError:
        LOGGER.warning("PyMongo dependency is unavailable")
        return None
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=3_000,
        connectTimeoutMS=3_000,
        appname="payment-success-monitor",
    )
    client.admin.command("ping")
    return MongoResources(client, client[database_name])


def ensure_indexes(database: Any) -> None:
    """Create the indexes required by imports and dashboard queries."""
    collection = database["transactions"]
    collection.create_index([("transaction_id", 1)], unique=True)
    collection.create_index([("is_deleted", 1), ("transaction_timestamp", -1)])
    collection.create_index(
        [
            ("is_deleted", 1),
            ("transaction_status", 1),
            ("transaction_timestamp", -1),
        ]
    )
    collection.create_index(
        [
            ("is_deleted", 1),
            ("device_used", 1),
            ("transaction_timestamp", -1),
        ]
    )
    collection.create_index(
        [
            ("is_deleted", 1),
            ("bank_gateway", 1),
            ("transaction_status", 1),
            ("transaction_timestamp", -1),
        ]
    )
    collection.create_index(
        [
            ("is_deleted", 1),
            ("transaction_type", 1),
            ("device_used", 1),
            ("transaction_timestamp", -1),
        ]
    )


def classify_mongodb_error(exc: Exception) -> str:
    """Map a MongoDB exception to a fixed diagnostic category."""
    if isinstance(exc, ConfigurationError):
        return "configuration"
    if isinstance(
        exc,
        (ExecutionTimeout, NetworkTimeout, ServerSelectionTimeoutError),
    ):
        return "timeout"
    if isinstance(exc, ConnectionFailure):
        return "connection"
    if isinstance(exc, OperationFailure):
        return "query"
    return "unexpected"


@dataclass(frozen=True, slots=True)
class MongoDashboardRepository:
    """Live dashboard repository backed by bounded MongoDB aggregations."""

    database: Any

    def fetch(
        self,
        filters: DashboardFilters,
        page: PageRequest,
    ) -> DashboardSnapshot:
        """Return aggregate dashboard data plus one bounded transaction page."""
        collection = self.database["transactions"]
        display_result = _aggregate_one(
            collection,
            _display_dashboard_pipeline(filters, page),
        )
        history_result = _aggregate_one(collection, _history_pipeline())
        result = {**display_result, **history_result}
        transactions = _transactions_frame(result.get("transactions", []))
        return DashboardSnapshot(
            metrics=_metrics(result.get("metrics", [])),
            gateway_summary=_records_frame(
                result.get("gateway_summary", []),
                [
                    "Bank Gateway",
                    "transaction_count",
                    "success_rate",
                    "average_latency_ms",
                ],
            ),
            trend=_trend_frame(result.get("trend", [])),
            failure_summary=_records_frame(
                result.get("failure_summary", []),
                ["Latency Band", "failed_count"],
            ),
            alerts=_alerts_frame(
                result.get("alerts", []),
            ),
            transactions=transactions,
            total_transactions=_total_count(result.get("total_count", [])),
            source=DataSource.LIVE,
            simulation_version=_metadata_version(result.get("metadata", [])),
            diagnostic=None,
        )


def _aggregate_one(
    collection: Any,
    pipeline: list[dict[str, object]],
) -> dict[str, object]:
    return next(iter(collection.aggregate(pipeline)), {})


def _display_dashboard_pipeline(
    filters: DashboardFilters,
    page: PageRequest,
) -> list[dict[str, object]]:
    """Build the indexable filtered aggregation for display data."""
    match = {"is_deleted": {"$ne": True}, **_display_match(filters)}
    return [
        {"$match": match},
        {
            "$facet": {
                "metrics": _metrics_pipeline(),
                "gateway_summary": _gateway_pipeline(),
                "trend": _trend_pipeline(),
                "failure_summary": _failure_pipeline(),
                "transactions": [
                    {
                        "$sort": {
                            "transaction_timestamp": -1,
                            "transaction_id": 1,
                        }
                    },
                    {"$skip": (page.number - 1) * page.size},
                    {"$limit": page.size},
                    {"$project": {"_id": 0}},
                ],
                "total_count": [{"$count": "count"}],
            }
        },
    ]


def _history_pipeline() -> list[dict[str, object]]:
    """Build the active-only aggregation for alerts and source metadata."""
    return [
        {"$match": {"is_deleted": {"$ne": True}}},
        {
            "$facet": {
                "alerts": _alerts_pipeline(),
                "metadata": _metadata_pipeline(),
            }
        },
    ]


def _display_match(
    filters: DashboardFilters,
) -> dict[str, object]:
    match: dict[str, object] = {}
    for field, values in (
        ("bank_gateway", filters.gateways),
        ("transaction_type", filters.transaction_types),
        ("device_used", filters.devices),
        ("transaction_status", filters.statuses),
    ):
        if values:
            if not all(isinstance(value, str) for value in values):
                raise ValueError(f"{field} filters must contain strings")
            match[field] = {"$in": list(values)}
    timestamp: dict[str, datetime] = {}
    if filters.start is not None:
        timestamp["$gte"] = datetime.combine(filters.start, time.min)
    if filters.end is not None:
        timestamp["$lt"] = datetime.combine(filters.end + timedelta(days=1), time.min)
    if timestamp:
        match["transaction_timestamp"] = timestamp
    return match


def _metrics_pipeline() -> list[dict[str, object]]:
    unbounded_window = {"documents": ["unbounded", "unbounded"]}
    return [
        {
            "$setWindowFields": {
                "sortBy": {"latency_ms": 1, "transaction_id": 1},
                "output": {
                    "rank": {"$documentNumber": {}},
                    "transaction_count": {
                        "$count": {},
                        "window": unbounded_window,
                    },
                    "success_count": {
                        "$sum": {"$cond": [_status_is(SUCCESS_STATUS), 1, 0]},
                        "window": unbounded_window,
                    },
                    "failed_count": {
                        "$sum": {"$cond": [_status_is(FAILED_STATUS), 1, 0]},
                        "window": unbounded_window,
                    },
                    "average_latency_ms": {
                        "$avg": "$latency_ms",
                        "window": unbounded_window,
                    },
                },
            }
        },
        {
            "$set": {
                "quantile_position": {
                    "$multiply": [
                        {"$subtract": ["$transaction_count", 1]},
                        P95_QUANTILE,
                    ]
                }
            }
        },
        {
            "$set": {
                "lower_rank": {"$add": [{"$floor": "$quantile_position"}, 1]},
                "upper_rank": {"$add": [{"$ceil": "$quantile_position"}, 1]},
                "quantile_fraction": {
                    "$subtract": [
                        "$quantile_position",
                        {"$floor": "$quantile_position"},
                    ]
                },
            }
        },
        {
            "$match": {
                "$expr": {
                    "$or": [
                        {"$eq": ["$rank", "$lower_rank"]},
                        {"$eq": ["$rank", "$upper_rank"]},
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "transaction_count": {"$first": "$transaction_count"},
                "success_count": {"$first": "$success_count"},
                "failed_count": {"$first": "$failed_count"},
                "average_latency_ms": {"$first": "$average_latency_ms"},
                "lower_latency_ms": {"$min": "$latency_ms"},
                "upper_latency_ms": {"$max": "$latency_ms"},
                "quantile_fraction": {"$first": "$quantile_fraction"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "transaction_count": 1,
                "success_rate": {
                    "$cond": [
                        {"$gt": ["$transaction_count", 0]},
                        {"$divide": ["$success_count", "$transaction_count"]},
                        0.0,
                    ]
                },
                "failed_count": 1,
                "average_latency_ms": {"$ifNull": ["$average_latency_ms", 0.0]},
                "p95_latency_ms": {
                    "$add": [
                        "$lower_latency_ms",
                        {
                            "$multiply": [
                                "$quantile_fraction",
                                {
                                    "$subtract": [
                                        "$upper_latency_ms",
                                        "$lower_latency_ms",
                                    ]
                                },
                            ]
                        },
                    ]
                },
            }
        },
    ]


def _gateway_pipeline() -> list[dict[str, object]]:
    return [
        {
            "$group": {
                "_id": "$bank_gateway",
                "transaction_count": {"$sum": 1},
                "success_count": {
                    "$sum": {"$cond": [_status_is(SUCCESS_STATUS), 1, 0]}
                },
                "average_latency_ms": {"$avg": "$latency_ms"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "Bank Gateway": "$_id",
                "transaction_count": 1,
                "success_rate": {"$divide": ["$success_count", "$transaction_count"]},
                "average_latency_ms": 1,
            }
        },
        {"$sort": {"Bank Gateway": 1}},
    ]


def _trend_pipeline() -> list[dict[str, object]]:
    return [
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$transaction_timestamp",
                        "unit": "minute",
                        "binSize": 15,
                    }
                },
                "transaction_count": {"$sum": 1},
                "success_count": {
                    "$sum": {"$cond": [_status_is(SUCCESS_STATUS), 1, 0]}
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "Timestamp": "$_id",
                "success_rate": {"$divide": ["$success_count", "$transaction_count"]},
                "transaction_count": 1,
            }
        },
        {"$sort": {"Timestamp": 1}},
    ]


def _failure_pipeline() -> list[dict[str, object]]:
    return [
        {"$match": {"transaction_status": FAILED_STATUS}},
        {
            "$project": {
                "latency_band": {
                    "$switch": {
                        "branches": [
                            {"case": {"$lte": ["$latency_ms", 5]}, "then": "0-5 ms"},
                            {
                                "case": {"$lte": ["$latency_ms", 10]},
                                "then": "6-10 ms",
                            },
                            {
                                "case": {"$lte": ["$latency_ms", 15]},
                                "then": "11-15 ms",
                            },
                        ],
                        "default": "16+ ms",
                    }
                }
            }
        },
        {"$group": {"_id": "$latency_band", "failed_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "Latency Band": "$_id", "failed_count": 1}},
        {"$sort": {"failed_count": -1, "Latency Band": 1}},
    ]


def _alerts_pipeline() -> list[dict[str, object]]:
    return [
        {
            "$setWindowFields": {
                "partitionBy": "$bank_gateway",
                "sortBy": {"transaction_timestamp": -1, "transaction_id": 1},
                "output": {"recency_rank": {"$documentNumber": {}}},
            }
        },
        {
            "$group": {
                "_id": "$bank_gateway",
                "transaction_count": {"$sum": 1},
                "success_count": {
                    "$sum": {"$cond": [_status_is(SUCCESS_STATUS), 1, 0]}
                },
                "rolling_count": {
                    "$sum": {
                        "$cond": [
                            {"$lte": ["$recency_rank", ALERT_WINDOW_SIZE]},
                            1,
                            0,
                        ]
                    }
                },
                "rolling_success_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$lte": [
                                            "$recency_rank",
                                            ALERT_WINDOW_SIZE,
                                        ]
                                    },
                                    _status_is(SUCCESS_STATUS),
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {
            "$set": {
                "baseline_rate": {"$divide": ["$success_count", "$transaction_count"]},
                "has_sufficient_history": {
                    "$gte": ["$rolling_count", ALERT_WINDOW_SIZE]
                },
            }
        },
        {
            "$set": {
                "rolling_rate": {
                    "$cond": [
                        "$has_sufficient_history",
                        {"$divide": ["$rolling_success_count", "$rolling_count"]},
                        None,
                    ]
                }
            }
        },
        {
            "$set": {
                "drop": {
                    "$cond": [
                        "$has_sufficient_history",
                        {
                            "$round": [
                                {"$subtract": ["$baseline_rate", "$rolling_rate"]},
                                12,
                            ]
                        },
                        None,
                    ]
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "Bank Gateway": "$_id",
                "baseline_rate": 1,
                "rolling_rate": 1,
                "drop": 1,
                "has_sufficient_history": 1,
                "is_alert": {
                    "$and": [
                        "$has_sufficient_history",
                        {"$gte": ["$drop", ALERT_THRESHOLD]},
                    ]
                },
            }
        },
        {"$sort": {"Bank Gateway": 1}},
    ]


def _metadata_pipeline() -> list[dict[str, object]]:
    return [
        {"$sort": {"transaction_timestamp": 1, "transaction_id": 1}},
        {"$limit": 1},
        {
            "$project": {
                "_id": 0,
                "simulation_version": {
                    "$ifNull": ["$simulation_version", LEGACY_SIMULATION_VERSION]
                },
            }
        },
    ]


def _status_is(status: str) -> dict[str, list[str]]:
    return {"$eq": ["$transaction_status", status]}


def _metrics(records: object) -> dict[str, int | float]:
    defaults: dict[str, int | float] = {
        "transaction_count": 0,
        "success_rate": 0.0,
        "failed_count": 0,
        "average_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
    }
    if isinstance(records, list) and records and isinstance(records[0], dict):
        defaults.update(
            {key: value for key, value in records[0].items() if key in defaults}
        )
    return defaults


def _records_frame(records: object, columns: list[str]) -> pd.DataFrame:
    if not isinstance(records, list):
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records, columns=columns)


def _alerts_frame(records: object) -> pd.DataFrame:
    columns = [
        "Bank Gateway",
        "baseline_rate",
        "rolling_rate",
        "drop",
        "has_sufficient_history",
        "is_alert",
    ]
    frame = _records_frame(records, columns)
    frame = frame.set_index("Bank Gateway").reindex(GATEWAYS).reset_index()
    for column in ("has_sufficient_history", "is_alert"):
        frame[column] = frame[column].astype("boolean").fillna(False).astype(bool)
    return frame


def _trend_frame(records: object) -> pd.DataFrame:
    frame = _records_frame(
        records,
        ["Timestamp", "success_rate", "transaction_count"],
    )
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"])
    return frame


def _transactions_frame(records: object) -> pd.DataFrame:
    if not isinstance(records, list) or not records:
        frame = pd.DataFrame(
            {column: pd.Series(dtype="object") for column in COLUMN_MAP.values()}
        )
        frame["Timestamp"] = pd.Series(dtype="datetime64[ns]")
        frame["Latency (ms)"] = pd.Series(dtype="float64")
        return add_latency_band(frame)
    frame = documents_to_frame(records).sort_values(
        ["Timestamp", "Transaction ID"],
        ascending=[False, True],
        kind="stable",
    )
    return add_latency_band(frame.reset_index(drop=True))


def _total_count(records: object) -> int:
    if isinstance(records, list) and records and isinstance(records[0], dict):
        return int(records[0].get("count", 0))
    return 0


def _metadata_version(records: object) -> str:
    if isinstance(records, list) and records and isinstance(records[0], dict):
        value = records[0].get("simulation_version")
        if value is not None:
            return str(value)
    return LEGACY_SIMULATION_VERSION


def documents_to_frame(documents: list[dict[str, object]]) -> pd.DataFrame:
    """Convert MongoDB documents to the established dashboard schema."""
    frame = pd.DataFrame(documents)
    if "source_transaction_status" not in frame:
        frame["source_transaction_status"] = frame["transaction_status"]
    else:
        frame["source_transaction_status"] = frame["source_transaction_status"].fillna(
            frame["transaction_status"]
        )
    if "simulation_version" not in frame:
        frame["simulation_version"] = LEGACY_SIMULATION_VERSION
    else:
        frame["simulation_version"] = frame["simulation_version"].fillna(
            LEGACY_SIMULATION_VERSION
        )
    frame = frame[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    frame["PIN Code"] = frame["PIN Code"].astype("string")
    validate_transactions(frame, require_gateway=True)
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], utc=True).dt.tz_localize(
        None
    )
    frame["Transaction Amount"] = pd.to_numeric(frame["Transaction Amount"])
    frame["Latency (ms)"] = pd.to_numeric(frame["Latency (ms)"])
    frame["Fraud Flag"] = frame["Fraud Flag"].astype("boolean")
    return frame.sort_values("Timestamp", kind="stable").reset_index(drop=True)


def load_dashboard_transactions(
    fallback: Callable[[], pd.DataFrame],
) -> DatabaseResult:
    """Compatibility loader backed by one bounded live transaction page."""
    try:
        resources = create_resources_from_env()
        if resources is None:
            return DatabaseResult(
                fallback(),
                "fallback",
                "database.fallback_not_configured",
            )
        ensure_indexes(resources.database)
        snapshot = MongoDashboardRepository(resources.database).fetch(
            DashboardFilters(),
            PageRequest(number=1, size=100),
        )
        return DatabaseResult(snapshot.transactions, "mongodb")
    except (ConfigurationError, ConnectionFailure, OperationFailure) as exc:
        LOGGER.warning("MongoDB read failed: %s", type(exc).__name__)
        return DatabaseResult(fallback(), "fallback", "database.fallback_unavailable")
