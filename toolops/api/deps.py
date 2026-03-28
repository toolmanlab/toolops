"""FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache

from toolops.config.settings import Settings
from toolops.storage.clickhouse import ClickHouseClient


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def get_clickhouse() -> ClickHouseClient:
    """Provide a ClickHouseClient instance."""
    settings = get_settings()
    return ClickHouseClient(settings.clickhouse)
