"""Shared fixtures for ToolOps tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from toolops.config.settings import ClickHouseSettings, Settings
from toolops.storage.clickhouse import ClickHouseClient


@pytest.fixture
def settings() -> Settings:
    """Provide default test settings."""
    return Settings()


@pytest.fixture
def ch_settings() -> ClickHouseSettings:
    """Provide default ClickHouse test settings."""
    return ClickHouseSettings()


@pytest.fixture
def mock_ch_client(ch_settings: ClickHouseSettings) -> ClickHouseClient:
    """Provide a ClickHouseClient with mocked underlying driver."""
    client = ClickHouseClient(ch_settings)
    mock_driver = MagicMock()
    mock_driver.query.return_value = MagicMock(
        column_names=["timestamp", "service", "metric_name", "metric_value", "labels"],
        result_rows=[],
    )
    with patch.object(client, "_client", mock_driver):
        yield client  # type: ignore[misc]
