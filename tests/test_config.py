from __future__ import annotations

import inspect
from pathlib import Path

from payment_dashboard import alerting, config, data_loader, prepare_data


def test_runtime_modules_consume_authoritative_config_constants() -> None:
    assert data_loader.GATEWAYS is config.GATEWAYS
    assert data_loader.REQUIRED_COLUMNS is config.REQUIRED_COLUMNS
    assert data_loader.STATUSES is config.STATUSES
    assert prepare_data.GATEWAYS is config.GATEWAYS
    assert (
        inspect.signature(prepare_data.assign_gateways).parameters["seed"].default
        == config.DEFAULT_SEED
    )
    alert_parameters = inspect.signature(alerting.evaluate_alerts).parameters
    assert alert_parameters["window_size"].default == config.ALERT_WINDOW_SIZE
    assert alert_parameters["threshold"].default == config.ALERT_THRESHOLD


def test_environment_example_documents_mongodb_keys() -> None:
    example = Path(".env.example").read_text()
    assert "MONGODB_URI=mongodb+srv://" in example
    assert "MONGODB_DATABASE=payment_success_demo" in example
    assert "ADMIN_PASSWORD_HASH=pbkdf2_sha256$" in example
    assert "SUPABASE_" not in example


def test_mongodb_setup_guide_covers_security_workflow() -> None:
    guide = Path("docs/mongodb-atlas-setup.md").read_text().lower()
    for phrase in (
        "database user",
        "admin_password_hash",
        "make load-mongodb",
        "streamlit community cloud",
        "soft-delete",
    ):
        assert phrase in guide
