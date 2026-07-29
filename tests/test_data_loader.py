from __future__ import annotations

import pandas as pd
import pytest

from payment_dashboard.data_loader import (
    DataValidationError,
    load_transactions,
    validate_transactions,
)


def test_valid_raw_data_passes_without_gateway(sample_transactions):
    validate_transactions(sample_transactions, require_gateway=False)


def test_duplicate_transaction_id_is_rejected(sample_transactions):
    duplicated = sample_transactions.copy()
    duplicated.loc[1, "Transaction ID"] = "TX1"

    with pytest.raises(DataValidationError, match="unique"):
        validate_transactions(duplicated, require_gateway=False)


def test_invalid_status_is_rejected(sample_transactions):
    invalid = sample_transactions.copy()
    invalid.loc[0, "Transaction Status"] = "Pending"

    with pytest.raises(DataValidationError, match="Transaction Status"):
        validate_transactions(invalid, require_gateway=False)


def test_missing_gateway_is_rejected_for_prepared_data(sample_transactions):
    with pytest.raises(DataValidationError, match="Bank Gateway"):
        validate_transactions(sample_transactions, require_gateway=True)


def test_negative_latency_is_rejected(sample_transactions):
    invalid = sample_transactions.copy()
    invalid.loc[0, "Latency (ms)"] = -1

    with pytest.raises(DataValidationError, match="Latency"):
        validate_transactions(invalid, require_gateway=False)


@pytest.mark.integration
def test_load_transactions_parses_types_and_sorts_timestamps(
    sample_transactions,
    tmp_path,
):
    path = tmp_path / "transactions.csv"
    sample_transactions.to_csv(path, index=False)

    loaded = load_transactions(path, require_gateway=False)

    assert loaded["Transaction ID"].tolist() == ["TX2", "TX4", "TX1", "TX3"]
    assert pd.api.types.is_datetime64_any_dtype(loaded["Timestamp"])
    assert pd.api.types.is_numeric_dtype(loaded["Transaction Amount"])
    assert pd.api.types.is_bool_dtype(loaded["Fraud Flag"])


@pytest.mark.integration
def test_load_transactions_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.csv"

    with pytest.raises(DataValidationError, match="does not exist"):
        load_transactions(missing, require_gateway=False)
