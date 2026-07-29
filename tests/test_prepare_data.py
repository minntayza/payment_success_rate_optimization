from __future__ import annotations

import pandas as pd

from payment_dashboard.prepare_data import assign_gateways, prepare_file


def test_assignment_is_reproducible(sample_transactions):
    first = assign_gateways(sample_transactions, seed=42)
    second = assign_gateways(sample_transactions, seed=42)

    assert first["Bank Gateway"].tolist() == second["Bank Gateway"].tolist()


def test_assignment_preserves_source_data(sample_transactions):
    prepared = assign_gateways(sample_transactions, seed=42)

    pd.testing.assert_frame_equal(
        prepared.drop(columns=["Bank Gateway"]),
        sample_transactions.sort_values("Timestamp", kind="stable").reset_index(drop=True),
        check_dtype=False,
    )


def test_all_gateway_labels_are_valid(sample_transactions):
    prepared = assign_gateways(sample_transactions, seed=42)

    assert set(prepared["Bank Gateway"]).issubset(
        {"Gateway A", "Gateway B", "Gateway C", "Gateway D"}
    )


def test_distribution_is_reasonably_uniform():
    frame = pd.DataFrame(
        {
            "Transaction ID": [f"TX{i}" for i in range(1000)],
            "Timestamp": pd.date_range("2025-01-01", periods=1000, freq="min"),
        }
    )

    prepared = assign_gateways(frame, seed=20260728)
    counts = prepared["Bank Gateway"].value_counts()

    assert counts.between(200, 300).all()


def test_prepare_file_writes_valid_enriched_copy(sample_transactions, tmp_path):
    source_path = tmp_path / "source.csv"
    output_path = tmp_path / "processed" / "prepared.csv"
    sample_transactions.to_csv(source_path, index=False)

    prepare_file(source_path, output_path, seed=42)

    written = pd.read_csv(output_path)
    assert len(written) == len(sample_transactions)
    assert "Bank Gateway" in written
    original_statuses = sample_transactions.set_index("Transaction ID")[
        "Transaction Status"
    ].sort_index()
    written_statuses = written.set_index("Transaction ID")[
        "Transaction Status"
    ].sort_index()
    pd.testing.assert_series_equal(
        written_statuses,
        original_statuses,
        check_names=False,
    )
