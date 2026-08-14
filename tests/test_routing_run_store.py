"""Persistence and lineage tests for routing benchmark runs."""

import json
from pathlib import Path

import pandas as pd
import pytest

from payment_dashboard.routing_repository import PandasRoutingRepository
from payment_dashboard.routing_run_store import RoutingRunStore


def test_run_store_round_trips_artifacts_and_detects_tampering(tmp_path: Path) -> None:
    store = RoutingRunStore(tmp_path)
    contexts = pd.DataFrame(
        {
            "Transaction ID": ["T1"],
            "Timestamp": [pd.Timestamp("2025-01-01", tz="UTC")],
            "Benchmark Timestamp": [pd.Timestamp("2025-02-01", tz="UTC")],
        }
    )
    candidates = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "gateway_id": ["Gateway A"],
            "timestamp": [pd.Timestamp("2025-02-01", tz="UTC")],
            "source_timestamp": [pd.Timestamp("2025-01-01", tz="UTC")],
        }
    )
    outcomes = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "gateway_id": ["Gateway A"],
            "realized_success": [True],
        }
    )
    report = pd.DataFrame({"policy": ["milp_optimizer"], "success_rate": [1.0]})
    manifest = store.save(
        contexts=contexts,
        candidates=candidates,
        outcomes=outcomes,
        report=report,
        configuration={"seed": 42, "simulation_version": "test-v1"},
    )
    loaded = store.load(manifest.run_id)
    pd.testing.assert_frame_equal(loaded.contexts, contexts)
    pd.testing.assert_frame_equal(loaded.candidates, candidates)
    pd.testing.assert_frame_equal(loaded.outcomes, outcomes)
    pd.testing.assert_frame_equal(loaded.report, report)

    report_path = tmp_path / manifest.run_id / "report.csv"
    report_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        store.load(manifest.run_id)


def test_repository_manifest_records_synthetic_timeline(tmp_path: Path) -> None:
    count = 400
    contexts = pd.DataFrame(
        {
            "Transaction ID": [f"T{index:04d}" for index in range(count)],
            "Timestamp": pd.date_range(
                "2025-01-17T10:00:00Z", periods=count, freq="5s"
            ),
            "Transaction Amount": [100.0] * count,
            "Transaction Type": ["Transfer"] * count,
            "Device Used": ["Mobile"] * count,
            "Fraud Flag": [False] * count,
            "Latency (ms)": [20.0] * count,
            "Sender Account ID": ["SECRET"] * count,
            "Receiver Account ID": ["SECRET"] * count,
            "Geolocation (Latitude/Longitude)": ["SECRET"] * count,
        }
    )

    report = PandasRoutingRepository(tmp_path).build_report(contexts)
    manifest = json.loads(
        (tmp_path / report.run_id / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["configuration"]["timeline"] == {
        "frequency": "60s",
        "start": "2025-01-01T00:00:00Z",
        "version": "benchmark-timeline-v1",
    }
    assert manifest["configuration"]["context_columns"] == [
        "Transaction ID",
        "Timestamp",
        "Benchmark Timestamp",
        "Transaction Amount",
        "Transaction Type",
        "Device Used",
    ]
    assert manifest["configuration"]["state_version"] == "gateway-state-v3"
    persisted = pd.read_csv(tmp_path / report.run_id / "contexts.csv")
    assert persisted.columns.tolist() == manifest["configuration"]["context_columns"]
    assert "Sender Account ID" not in persisted
