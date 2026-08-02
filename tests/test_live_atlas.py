"""Opt-in Atlas contract checks that never run in the default suite."""

from __future__ import annotations

import os

import pytest

from payment_dashboard.dashboard_repository import DashboardFilters, PageRequest
from payment_dashboard.models import DataSource
from payment_dashboard.mongodb import (
    MongoDashboardRepository,
    create_resources_from_env,
)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_ATLAS_TESTS") != "1", reason="live Atlas disabled")
def test_live_atlas_repository_contract() -> None:
    """The configured Atlas collection returns a bounded live snapshot."""
    resources = create_resources_from_env()

    assert resources is not None
    snapshot = MongoDashboardRepository(resources.database).fetch(
        DashboardFilters(), PageRequest(number=1, size=1)
    )
    assert snapshot.source is DataSource.LIVE
