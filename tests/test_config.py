from __future__ import annotations

import inspect

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
