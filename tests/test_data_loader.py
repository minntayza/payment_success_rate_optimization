from __future__ import annotations

import re

import pandas as pd
import pytest

import payment_dashboard.data_loader as data_loader
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


@pytest.mark.parametrize("value", ["maybe", 2, -1, None])
def test_raw_validation_rejects_invalid_fraud_flags(sample_transactions, value):
    invalid = sample_transactions.copy()
    invalid["Fraud Flag"] = value

    with pytest.raises(DataValidationError, match="Fraud Flag"):
        data_loader.validate_raw_transactions(invalid)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("Transaction Type", "Refund"),
        ("Device Used", "Smart Fridge"),
        ("Transaction Amount", float("inf")),
        ("Slice Bandwidth (Mbps)", -1),
    ],
)
def test_raw_validation_rejects_invalid_domain_values(
    sample_transactions, column, value
):
    invalid = sample_transactions.copy()
    invalid.loc[0, column] = value

    with pytest.raises(DataValidationError, match=re.escape(column)):
        data_loader.validate_raw_transactions(invalid)


def test_prepared_validation_requires_simulation_metadata(sample_transactions):
    prepared = sample_transactions.drop(columns=["PIN Code"]).assign(
        **{"Bank Gateway": "Gateway A"}
    )

    with pytest.raises(DataValidationError, match="Simulation Version"):
        data_loader.validate_prepared_transactions(prepared)


def test_prepared_validation_rejects_mixed_simulation_versions(
    sample_transactions,
) -> None:
    prepared = (
        sample_transactions.iloc[:2]
        .drop(columns=["PIN Code"])
        .assign(
            **{
                "Bank Gateway": ["Gateway A", "Gateway B"],
                "Simulation Version": ["controlled-v1", "controlled-v2"],
            }
        )
    )

    with pytest.raises(DataValidationError, match="exactly one Simulation Version"):
        data_loader.validate_prepared_transactions(prepared)


def test_prepared_loader_does_not_invent_legacy_simulation_version(
    sample_transactions, tmp_path
) -> None:
    prepared = sample_transactions.drop(columns=["PIN Code"]).assign(
        **{"Bank Gateway": "Gateway A"}
    )
    path = tmp_path / "prepared.csv"
    prepared.to_csv(path, index=False)
    with pytest.raises(DataValidationError, match="Simulation Version"):
        data_loader.load_transactions(path, require_gateway=True)


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
    assert "PIN Code" not in loaded


@pytest.mark.integration
def test_load_transactions_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.csv"

    with pytest.raises(DataValidationError, match="does not exist"):
        load_transactions(missing, require_gateway=False)
