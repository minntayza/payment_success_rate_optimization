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


def test_environment_example_documents_supabase_keys() -> None:
    example = Path(".env.example").read_text()
    assert "SUPABASE_URL=https://your-project.supabase.co" in example
    assert "SUPABASE_ANON_KEY=replace-with-your-anon-key" in example
    assert "SUPABASE_SERVICE_ROLE_KEY=local-import-only" in example


def test_supabase_setup_guide_covers_security_workflow() -> None:
    guide = Path("docs/supabase-setup.md").read_text().lower()
    for phrase in (
        "row-level security",
        "admin_users",
        "make load-supabase",
        "streamlit community cloud",
        "soft-delete",
    ):
        assert phrase in guide
