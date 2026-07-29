"""Integration tests exercising the full data → analytics → alerting pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.analytics import (
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)
from payment_dashboard.app import build_dashboard_state
from payment_dashboard.data_loader import load_transactions
from payment_dashboard.prepare_data import assign_gateways


@pytest.mark.integration
def test_language_toggle_preserves_filters_and_translates_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared_path = tmp_path / "prepared_transactions.csv"
    prepared = _make_transactions(200)
    prepared["Timestamp"] = pd.date_range(
        "2025-06-01",
        periods=len(prepared),
        freq="30min",
    )
    prepared.to_csv(prepared_path, index=False)
    monkeypatch.setenv("PAYMENT_DATA_PATH", str(prepared_path))

    app_path = Path(__file__).parents[1] / "payment_dashboard" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)
    english_gateway_options = app.sidebar.multiselect[0].options

    assert app.title[0].value == "Payment Success Monitor"
    assert not app.exception

    app.sidebar.slider[0].set_value(120)
    app.sidebar.multiselect[0].set_value(["Gateway A"])
    app.sidebar.multiselect[1].set_value(["Transfer"])
    app.sidebar.multiselect[2].set_value(["Mobile"])
    app.sidebar.multiselect[3].set_value(["Success"])
    app.sidebar.date_input[0].set_value((date(2025, 6, 2), date(2025, 6, 3)))
    app.run(timeout=10)

    assert app.sidebar.slider[0].value == 120

    app.toggle[0].set_value(True).run(timeout=10)

    assert app.title[0].value == "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်"
    assert not app.exception
    assert app.sidebar.multiselect[0].options == english_gateway_options
    assert app.sidebar.slider[0].value == 120
    assert app.sidebar.multiselect[0].value == ["Gateway A"]
    assert app.sidebar.multiselect[1].value == ["Transfer"]
    assert app.sidebar.multiselect[2].value == ["Mobile"]
    assert app.sidebar.multiselect[3].value == ["Success"]
    assert app.sidebar.date_input[0].value == (
        date(2025, 6, 2),
        date(2025, 6, 3),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transactions(n: int = 200, seed: int = 99) -> pd.DataFrame:
    """Build a realistic transaction frame with gateway labels."""
    rng = pd.date_range("2025-06-01", periods=n, freq="min")
    # 70% success, 30% failure — scales to any n
    success_count = int(n * 0.7)
    fail_count = n - success_count
    statuses = ["Success"] * success_count + ["Failed"] * fail_count
    types = (
        ["Transfer"] * max(1, n // 3)
        + ["Deposit"] * max(1, n // 3)
        + ["Withdrawal"] * (n - 2 * max(1, n // 3))
    )
    devices = (
        ["Mobile"] * max(1, n // 2)
        + ["Desktop"] * max(1, n // 3)
        + ["Tablet"] * (n - max(1, n // 2) - max(1, n // 3))
    )
    fraud_count = min(5, n)
    frame = pd.DataFrame(
        {
            "Transaction ID": [f"ITX{i}" for i in range(n)],
            "Sender Account ID": [f"S{i}" for i in range(n)],
            "Receiver Account ID": [f"R{i}" for i in range(n)],
            "Transaction Amount": [100.0 + i for i in range(n)],
            "Transaction Type": types[:n],
            "Timestamp": rng[:n],
            "Transaction Status": statuses[:n],
            "Fraud Flag": [False] * (n - fraud_count) + [True] * fraud_count,
            "Geolocation (Latitude/Longitude)": [f"geo{i}" for i in range(n)],
            "Device Used": devices[:n],
            "Network Slice ID": [f"Slice{i % 4}" for i in range(n)],
            "Latency (ms)": [5 + (i % 30) for i in range(n)],
            "Slice Bandwidth (Mbps)": [100] * n,
            "PIN Code": [f"{1000 + i}" for i in range(n)],
        }
    )
    return assign_gateways(frame, seed=seed)


# ---------------------------------------------------------------------------
# Full pipeline tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullPipeline:
    """End-to-end: load → filter → alert → state."""

    def test_build_dashboard_state_returns_typed_dataclass(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        assert len(state.replay_frame) == 200
        assert len(state.display_frame) == 200
        assert "Latency Band" in state.display_frame.columns
        assert len(state.alerts) == 4  # one per gateway

    def test_replay_slice_is_chronological_prefix(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=100,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        assert len(state.replay_frame) == 100
        # Replay frame should be the first 100 rows of the sorted data
        pd.testing.assert_frame_equal(
            state.replay_frame.reset_index(drop=True),
            full.iloc[:100].reset_index(drop=True),
        )

    def test_filters_narrow_display_without_affecting_alerts(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=["Gateway A"],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        # Display filtered to Gateway A only
        assert set(state.display_frame["Bank Gateway"]) <= {"Gateway A"}
        # Alerts still cover all gateways (unfiltered)
        assert len(state.alerts) == 4

    def test_date_range_filter(self):
        full = _make_transactions(200)
        # Build a frame spanning multiple days so date filter actually cuts rows
        full["Timestamp"] = pd.date_range(
            "2025-06-01",
            periods=200,
            freq="30min",
        )
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=date(2025, 6, 2),
            end=None,
        )
        assert (state.display_frame["Timestamp"].dt.date >= date(2025, 6, 2)).all()
        assert len(state.display_frame) < 200


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEdgeCases:
    """Boundary conditions and degenerate inputs."""

    def test_all_successes_no_alerts(self):
        n = 100
        frame = pd.DataFrame(
            {
                "Transaction ID": [f"S{i}" for i in range(n)],
                "Bank Gateway": ["Gateway A"] * n,
                "Transaction Status": ["Success"] * n,
                "Latency (ms)": [5.0] * n,
                "Timestamp": pd.date_range("2025-01-01", periods=n, freq="min"),
            }
        )
        alerts = evaluate_alerts(frame, frame)
        row = alerts.iloc[0]
        assert row["baseline_rate"] == 1.0
        assert row["rolling_rate"] == 1.0
        assert row["drop"] == 0.0
        assert not row["is_alert"]

    def test_all_failures_triggers_alert(self):
        """Baseline has some success; rolling window is all failures → alert."""
        n = 100
        # Full dataset: 70% success → baseline ~0.7
        full = pd.DataFrame(
            {
                "Transaction ID": [f"F{i}" for i in range(n)],
                "Bank Gateway": ["Gateway A"] * n,
                "Transaction Status": ["Success"] * 70 + ["Failed"] * 30,
                "Latency (ms)": [5.0] * n,
                "Timestamp": pd.date_range("2025-01-01", periods=n, freq="min"),
            }
        )
        # Replay: all failures → rolling 0%
        replay = pd.DataFrame(
            {
                "Transaction ID": [f"R{i}" for i in range(n)],
                "Bank Gateway": ["Gateway A"] * n,
                "Transaction Status": ["Failed"] * n,
                "Latency (ms)": [5.0] * n,
                "Timestamp": pd.date_range("2025-01-02", periods=n, freq="min"),
            }
        )
        alerts = evaluate_alerts(full, replay)
        row = alerts.iloc[0]
        assert row["baseline_rate"] == 0.7
        assert row["rolling_rate"] == 0.0
        assert row["drop"] == 0.7
        assert row["is_alert"]

    def test_single_transaction_insufficient_history(self):
        frame = pd.DataFrame(
            {
                "Transaction ID": ["TX1"],
                "Bank Gateway": ["Gateway A"],
                "Transaction Status": ["Success"],
                "Latency (ms)": [5.0],
                "Timestamp": pd.to_datetime(["2025-01-01"]),
            }
        )
        alerts = evaluate_alerts(frame, frame)
        row = alerts.iloc[0]
        assert not row["has_sufficient_history"]
        assert pd.isna(row["rolling_rate"])
        assert not row["is_alert"]

    def test_empty_display_frame_shows_no_crash(self):
        full = _make_transactions(100)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=100,
            gateways=["Gateway Z"],  # non-existent gateway
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        assert state.display_frame.empty
        # Alerts should still be computed
        assert len(state.alerts) == 4


# ---------------------------------------------------------------------------
# Analytics pipeline
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAnalyticsPipeline:
    """Verify analytics functions compose correctly on larger data."""

    def test_summary_metrics_on_full_pipeline_output(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        metrics = summary_metrics(state.display_frame)
        assert metrics["transaction_count"] == 200
        assert 0.0 <= metrics["success_rate"] <= 1.0
        assert metrics["failed_count"] >= 0
        assert metrics["average_latency_ms"] > 0

    def test_failure_breakdown_on_pipeline_output(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        for dimension in ("Transaction Type", "Device Used", "Latency Band"):
            result = failure_breakdown(state.display_frame, dimension=dimension)
            assert not result.empty
            assert "failed_count" in result.columns

    def test_success_trend_on_pipeline_output(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        series = success_rate_series(state.display_frame)
        assert not series.empty
        assert "success_rate" in series.columns
        assert "transaction_count" in series.columns

    def test_gateway_summary_on_pipeline_output(self):
        full = _make_transactions(200)
        state = build_dashboard_state(
            full_frame=full,
            replay_count=200,
            gateways=[],
            transaction_types=[],
            devices=[],
            statuses=[],
            start=None,
            end=None,
        )
        summary = gateway_summary(state.display_frame)
        assert len(summary) == 4
        assert set(summary["Bank Gateway"]) == {
            "Gateway A",
            "Gateway B",
            "Gateway C",
            "Gateway D",
        }


# ---------------------------------------------------------------------------
# Data loader integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDataLoaderIntegration:
    """Test load_transactions with real CSV I/O."""

    def test_round_trip_csv(self, sample_transactions, tmp_path):
        path = tmp_path / "round_trip.csv"
        sample_transactions.to_csv(path, index=False)

        loaded = load_transactions(path, require_gateway=False)

        assert len(loaded) == 4
        assert loaded["Transaction ID"].tolist() == ["TX2", "TX4", "TX1", "TX3"]
        assert pd.api.types.is_datetime64_any_dtype(loaded["Timestamp"])

    def test_prepare_and_load_round_trip(self, sample_transactions, tmp_path):
        from payment_dashboard.prepare_data import prepare_file

        source = tmp_path / "source.csv"
        output = tmp_path / "prepared.csv"
        sample_transactions.to_csv(source, index=False)

        prepare_file(source, output, seed=42)
        loaded = load_transactions(output, require_gateway=True)

        assert len(loaded) == 4
        assert "Bank Gateway" in loaded.columns
        assert (
            loaded["Bank Gateway"]
            .isin(["Gateway A", "Gateway B", "Gateway C", "Gateway D"])
            .all()
        )
