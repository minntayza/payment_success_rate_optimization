"""Opt-in Atlas contract checks that never run in the default suite."""

from __future__ import annotations

import os
import re
from typing import Any

import pytest
from pymongo import MongoClient

from payment_dashboard.dashboard_repository import DashboardFilters, PageRequest
from payment_dashboard.models import DataSource
from payment_dashboard.mongodb import MongoDashboardRepository


def _has_test_marker(value: str) -> bool:
    return "test" in re.split(r"[^a-z0-9]+", value.casefold())


def _atlas_test_target_from_env() -> tuple[str, str]:
    database_name = os.getenv("MONGODB_TEST_DATABASE")
    collection_name = os.getenv("MONGODB_TEST_COLLECTION")
    if (
        not database_name
        or not collection_name
        or not _has_test_marker(database_name)
        or not _has_test_marker(collection_name)
    ):
        raise RuntimeError(
            "Set test-specific MONGODB_TEST_DATABASE and "
            "MONGODB_TEST_COLLECTION values containing 'test'."
        )
    if database_name == os.getenv("MONGODB_DATABASE"):
        raise RuntimeError(
            "MONGODB_TEST_DATABASE must not select the application database."
        )
    return database_name, collection_name


def _fetch_live_snapshot(client_factory: Any = MongoClient):
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("Set MONGODB_URI for the live Atlas contract.")
    database_name, collection_name = _atlas_test_target_from_env()
    client = client_factory(
        uri,
        serverSelectionTimeoutMS=3_000,
        connectTimeoutMS=3_000,
        appname="payment-dashboard-contract-test",
    )
    try:
        client.admin.command("ping")
        return MongoDashboardRepository(
            client[database_name], collection_name=collection_name
        ).fetch(DashboardFilters(), PageRequest(number=1, size=1))
    finally:
        client.close()


@pytest.mark.parametrize(
    ("database_name", "collection_name"),
    [
        (None, None),
        ("payments", "dashboard_contract_test"),
        ("payments_contest", "dashboard_contract_test"),
        ("payments_contract_test", "transactions"),
    ],
)
def test_live_atlas_refuses_missing_or_unsafe_test_targets(
    monkeypatch: pytest.MonkeyPatch,
    database_name: str | None,
    collection_name: str | None,
) -> None:
    """Live verification cannot fall back to an application database target."""
    if database_name is None:
        monkeypatch.delenv("MONGODB_TEST_DATABASE", raising=False)
    else:
        monkeypatch.setenv("MONGODB_TEST_DATABASE", database_name)
    if collection_name is None:
        monkeypatch.delenv("MONGODB_TEST_COLLECTION", raising=False)
    else:
        monkeypatch.setenv("MONGODB_TEST_COLLECTION", collection_name)

    with pytest.raises(RuntimeError, match="test-specific"):
        _atlas_test_target_from_env()


def test_live_atlas_refuses_application_database_as_test_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test-marked application database still cannot be queried by this check."""
    monkeypatch.setenv("MONGODB_DATABASE", "payments_contract_test")
    monkeypatch.setenv("MONGODB_TEST_DATABASE", "payments_contract_test")
    monkeypatch.setenv("MONGODB_TEST_COLLECTION", "dashboard_contract_test")

    with pytest.raises(RuntimeError, match="application database"):
        _atlas_test_target_from_env()


class _Collection:
    def __init__(self) -> None:
        self.aggregate_calls: list[list[dict[str, object]]] = []

    def aggregate(self, pipeline: list[dict[str, object]]) -> list[object]:
        self.aggregate_calls.append(pipeline)
        return []


class _FailingCollection(_Collection):
    def aggregate(self, pipeline: list[dict[str, object]]) -> list[object]:
        super().aggregate(pipeline)
        raise RuntimeError("query failed")


class _Admin:
    def command(self, name: str) -> None:
        assert name == "ping"


class _Client:
    def __init__(self, collection_name: str) -> None:
        self.admin = _Admin()
        self.collection = _Collection()
        self.collection_name = collection_name
        self.closed = False

    def __getitem__(self, _database_name: str) -> dict[str, _Collection]:
        return {self.collection_name: self.collection}

    def close(self) -> None:
        self.closed = True


def test_live_atlas_closes_client_after_read_only_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dedicated client is closed even after a successful contract query."""
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://contract.test")
    monkeypatch.setenv("MONGODB_TEST_DATABASE", "payments_contract_test")
    monkeypatch.setenv("MONGODB_TEST_COLLECTION", "dashboard_contract_test")
    client = _Client("dashboard_contract_test")

    snapshot = _fetch_live_snapshot(lambda *_args, **_kwargs: client)

    assert snapshot.source is DataSource.LIVE
    assert client.closed is True
    assert len(client.collection.aggregate_calls) == 2


def test_live_atlas_closes_client_when_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Query failures cannot leak the dedicated live-test client."""
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://contract.test")
    monkeypatch.setenv("MONGODB_TEST_DATABASE", "payments_contract_test")
    monkeypatch.setenv("MONGODB_TEST_COLLECTION", "dashboard_contract_test")
    client = _Client("dashboard_contract_test")
    client.collection = _FailingCollection()

    with pytest.raises(RuntimeError, match="query failed"):
        _fetch_live_snapshot(lambda *_args, **_kwargs: client)

    assert client.closed is True


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_ATLAS_TESTS") != "1", reason="live Atlas disabled")
def test_live_atlas_repository_contract() -> None:
    """The configured Atlas collection returns a bounded live snapshot."""
    snapshot = _fetch_live_snapshot()

    assert snapshot.source is DataSource.LIVE
