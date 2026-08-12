"""Persistence and lineage tests for routing benchmark runs."""

from pathlib import Path

import pandas as pd
import pytest

from payment_dashboard.routing_run_store import RoutingRunStore


def test_run_store_round_trips_artifacts_and_detects_tampering(tmp_path: Path) -> None:
    store = RoutingRunStore(tmp_path)
    contexts = pd.DataFrame(
        {"Transaction ID": ["T1"], "Timestamp": [pd.Timestamp("2025-01-01")]}
    )
    candidates = pd.DataFrame({"transaction_id": ["T1"], "gateway_id": ["Gateway A"]})
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
